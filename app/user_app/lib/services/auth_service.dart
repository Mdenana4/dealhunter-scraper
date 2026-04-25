import 'package:firebase_auth/firebase_auth.dart';
import 'package:google_sign_in/google_sign_in.dart';
import 'package:sign_in_with_apple/sign_in_with_apple.dart';
import 'package:cloud_firestore/cloud_firestore.dart';
import '../models/user_profile.dart';
import '../models/membership.dart';
import 'dart:math';

class AuthService {
  final FirebaseAuth _auth = FirebaseAuth.instance;
  final FirebaseFirestore _db = FirebaseFirestore.instance;
  final GoogleSignIn _googleSignIn = GoogleSignIn();

  User? get currentUser => _auth.currentUser;
  Stream<User?> get authStateChanges => _auth.authStateChanges();

  // ─── Email / Password ─────────────────────────────────────────────────────

  Future<UserCredential> signInWithEmail(String email, String password) =>
      _auth.signInWithEmailAndPassword(email: email, password: password);

  Future<UserCredential> registerWithEmail(String email, String password) async {
    final cred = await _auth.createUserWithEmailAndPassword(
        email: email, password: password);
    await _createUserProfile(cred.user!);
    return cred;
  }

  Future<void> sendEmailVerification() async =>
      _auth.currentUser?.sendEmailVerification();

  Future<void> sendPasswordResetEmail(String email) =>
      _auth.sendPasswordResetEmail(email: email);

  Future<void> updatePassword(String newPassword) =>
      _auth.currentUser!.updatePassword(newPassword);

  // ─── Google Sign-In ───────────────────────────────────────────────────────

  Future<UserCredential?> signInWithGoogle() async {
    final googleUser = await _googleSignIn.signIn();
    if (googleUser == null) return null;

    final googleAuth = await googleUser.authentication;
    final credential = GoogleAuthProvider.credential(
      accessToken: googleAuth.accessToken,
      idToken: googleAuth.idToken,
    );
    final cred = await _auth.signInWithCredential(credential);
    if (cred.additionalUserInfo?.isNewUser == true) {
      await _createUserProfile(cred.user!);
    }
    return cred;
  }

  // ─── Apple Sign-In ────────────────────────────────────────────────────────

  Future<UserCredential?> signInWithApple() async {
    final appleCredential = await SignInWithApple.getAppleIDCredential(
      scopes: [
        AppleIDAuthorizationScopes.email,
        AppleIDAuthorizationScopes.fullName,
      ],
    );
    final oauthCredential = OAuthProvider('apple.com').credential(
      idToken: appleCredential.identityToken,
      accessToken: appleCredential.authorizationCode,
    );
    final cred = await _auth.signInWithCredential(oauthCredential);
    if (cred.additionalUserInfo?.isNewUser == true) {
      await _createUserProfile(cred.user!, displayName:
          '${appleCredential.givenName ?? ''} ${appleCredential.familyName ?? ''}'.trim());
    }
    return cred;
  }

  // ─── OTP / Phone ──────────────────────────────────────────────────────────

  Future<void> verifyPhoneNumber({
    required String phoneNumber,
    required void Function(PhoneAuthCredential) onVerified,
    required void Function(FirebaseAuthException) onFailed,
    required void Function(String, int?) onCodeSent,
  }) => _auth.verifyPhoneNumber(
    phoneNumber: phoneNumber,
    verificationCompleted: onVerified,
    verificationFailed: onFailed,
    codeSent: onCodeSent,
    codeAutoRetrievalTimeout: (_) {},
  );

  Future<UserCredential> signInWithPhoneCredential(
      String verificationId, String smsCode) async {
    final credential = PhoneAuthProvider.credential(
        verificationId: verificationId, smsCode: smsCode);
    final cred = await _auth.signInWithCredential(credential);
    if (cred.additionalUserInfo?.isNewUser == true) {
      await _createUserProfile(cred.user!);
    }
    return cred;
  }

  // ─── Sign Out ─────────────────────────────────────────────────────────────

  Future<void> signOut() async {
    await _googleSignIn.signOut();
    await _auth.signOut();
  }

  // ─── User Profile (Firestore) ─────────────────────────────────────────────

  Future<void> _createUserProfile(User user, {String? displayName}) async {
    final ref = _db.collection('users').doc(user.uid);
    final existing = await ref.get();
    if (existing.exists) return;

    final referralCode = _generateReferralCode(user.uid);
    await ref.set({
      'email': user.email,
      'display_name': displayName ?? user.displayName,
      'photo_url': user.photoURL,
      'phone': user.phoneNumber,
      'membership': Membership().toMap(),
      'notifications': const NotificationPreferences().toMap(),
      'preferences': const AppPreferences().toMap(),
      'stats': {},
      'referral_code': referralCode,
      'referred_by': null,
      'created_at': DateTime.now().toIso8601String(),
      'last_login_at': DateTime.now().toIso8601String(),
    });
  }

  Future<UserProfile?> getUserProfile(String uid) async {
    final doc = await _db.collection('users').doc(uid).get();
    if (!doc.exists || doc.data() == null) return null;
    return UserProfile.fromMap(uid, doc.data()!);
  }

  Stream<UserProfile?> watchUserProfile(String uid) =>
      _db.collection('users').doc(uid).snapshots().map((doc) {
        if (!doc.exists || doc.data() == null) return null;
        return UserProfile.fromMap(uid, doc.data()!);
      });

  Future<void> updateUserProfile(String uid, Map<String, dynamic> data) async {
    data['last_login_at'] = DateTime.now().toIso8601String();
    await _db.collection('users').doc(uid).update(data);
  }

  Future<void> updateNotificationPreferences(
      String uid, NotificationPreferences prefs) async {
    await _db.collection('users').doc(uid).update({
      'notifications': prefs.toMap(),
    });
  }

  Future<void> updateAppPreferences(String uid, AppPreferences prefs) async {
    await _db.collection('users').doc(uid).update({
      'preferences': prefs.toMap(),
    });
  }

  // ─── Saved Deals ──────────────────────────────────────────────────────────

  Future<void> saveDeal(String uid, String dealId) async {
    await _db.collection('users').doc(uid)
        .collection('saved_deals').doc(dealId).set({
      'saved_at': DateTime.now().toIso8601String(),
      'deal_id': dealId,
    });
    await _db.collection('users').doc(uid).update({
      'stats.deals_saved': FieldValue.increment(1),
    });
  }

  Future<void> unsaveDeal(String uid, String dealId) async {
    await _db.collection('users').doc(uid)
        .collection('saved_deals').doc(dealId).delete();
  }

  Future<Set<String>> getSavedDealIds(String uid) async {
    final snap = await _db.collection('users').doc(uid)
        .collection('saved_deals').get();
    return snap.docs.map((d) => d.id).toSet();
  }

  Stream<Set<String>> watchSavedDealIds(String uid) =>
      _db.collection('users').doc(uid).collection('saved_deals').snapshots()
          .map((snap) => snap.docs.map((d) => d.id).toSet());

  // ─── Utility ──────────────────────────────────────────────────────────────

  String _generateReferralCode(String uid) {
    const chars = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789';
    final rng = Random(uid.hashCode);
    return List.generate(8, (_) => chars[rng.nextInt(chars.length)]).join();
  }
}
