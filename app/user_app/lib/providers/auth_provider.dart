import 'package:firebase_auth/firebase_auth.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../services/auth_service.dart';
import '../models/user_profile.dart';

final authServiceProvider = Provider<AuthService>((ref) => AuthService());

final firebaseUserProvider = StreamProvider<User?>((ref) {
  return ref.watch(authServiceProvider).authStateChanges;
});

final userProfileProvider = StreamProvider<UserProfile?>((ref) {
  final user = ref.watch(firebaseUserProvider).value;
  if (user == null) return const Stream.empty();
  return ref.watch(authServiceProvider).watchUserProfile(user.uid);
});

final isLoggedInProvider = Provider<bool>((ref) {
  final user = ref.watch(firebaseUserProvider);
  return user.maybeWhen(data: (u) => u != null, orElse: () => false);
});

final savedDealIdsProvider = StreamProvider<Set<String>>((ref) {
  final user = ref.watch(firebaseUserProvider).value;
  if (user == null) return Stream.value({});
  return ref.watch(authServiceProvider).watchSavedDealIds(user.uid);
});

class AuthNotifier extends StateNotifier<AsyncValue<void>> {
  AuthNotifier(this._authService) : super(const AsyncValue.data(null));

  final AuthService _authService;

  Future<bool> signInWithEmail(String email, String password) async {
    state = const AsyncValue.loading();
    try {
      await _authService.signInWithEmail(email, password);
      state = const AsyncValue.data(null);
      return true;
    } catch (e, st) {
      state = AsyncValue.error(e, st);
      return false;
    }
  }

  Future<bool> registerWithEmail(String email, String password) async {
    state = const AsyncValue.loading();
    try {
      await _authService.registerWithEmail(email, password);
      state = const AsyncValue.data(null);
      return true;
    } catch (e, st) {
      state = AsyncValue.error(e, st);
      return false;
    }
  }

  Future<bool> signInWithGoogle() async {
    state = const AsyncValue.loading();
    try {
      final result = await _authService.signInWithGoogle();
      state = const AsyncValue.data(null);
      return result != null;
    } catch (e, st) {
      state = AsyncValue.error(e, st);
      return false;
    }
  }

  Future<bool> signInWithApple() async {
    state = const AsyncValue.loading();
    try {
      final result = await _authService.signInWithApple();
      state = const AsyncValue.data(null);
      return result != null;
    } catch (e, st) {
      state = AsyncValue.error(e, st);
      return false;
    }
  }

  Future<void> signOut() async {
    await _authService.signOut();
    state = const AsyncValue.data(null);
  }

  Future<bool> sendPasswordReset(String email) async {
    try {
      await _authService.sendPasswordResetEmail(email);
      return true;
    } catch (_) {
      return false;
    }
  }

  String? getFirebaseErrorMessage(Object error) {
    if (error is FirebaseAuthException) {
      switch (error.code) {
        case 'user-not-found':
        case 'wrong-password':
        case 'invalid-credential':
          return 'Incorrect email or password.';
        case 'email-already-in-use':
          return 'This email is already registered.';
        case 'weak-password':
          return 'Password must be at least 6 characters.';
        case 'invalid-email':
          return 'Please enter a valid email address.';
        case 'too-many-requests':
          return 'Too many attempts. Please wait a few minutes.';
        case 'network-request-failed':
          return 'No internet connection.';
        default:
          return error.message;
      }
    }
    return 'Something went wrong. Please try again.';
  }
}

final authNotifierProvider =
    StateNotifierProvider<AuthNotifier, AsyncValue<void>>(
  (ref) => AuthNotifier(ref.watch(authServiceProvider)),
);
