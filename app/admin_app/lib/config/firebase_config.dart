// lib/config/firebase_config.dart

/// Firebase configuration for DealHunter Admin App
///
/// To get these values:
/// 1. Go to Firebase Console
/// 2. Select your project
/// 3. Click Settings (gear icon) > Project Settings
/// 4. Under "Your apps", find your Android/iOS app
/// 5. Copy the configuration values
///
/// For iOS: Download GoogleService-Info.plist
/// For Android: Download google-services.json

class FirebaseConfig {
  // Production Firebase Configuration - dealhunter-admin-prod
  // Generated: 2026-04-16

  static const String apiKey = 'AIzaSyCc6Sn-xHVzGal-M_8IE59mN63_t15eRwo';
  static const String appId = '1:97738565887:android:7340590dc772bbfaae04ca';
  static const String messagingSenderId = '97738565887';
  static const String projectId = 'dealhunter-admin-prod';
  static const String authDomain = 'dealhunter-admin-prod.firebaseapp.com';
  static const String storageBucket = 'dealhunter-admin-prod.firebasestorage.app';

  /// Initialize Firebase in main.dart:
  ///
  /// ```dart
  /// await Firebase.initializeApp(
  ///   options: FirebaseOptions(
  ///     apiKey: FirebaseConfig.apiKey,
  ///     appId: FirebaseConfig.appId,
  ///     messagingSenderId: FirebaseConfig.messagingSenderId,
  ///     projectId: FirebaseConfig.projectId,
  ///     authDomain: FirebaseConfig.authDomain,
  ///     storageBucket: FirebaseConfig.storageBucket,
  ///   ),
  /// );
  /// ```
}
