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
  // TODO: Replace with your actual Firebase configuration

  static const String apiKey = 'AIzaSy...'; // Your API Key
  static const String appId = 'YOUR_APP_ID'; // Your App ID
  static const String messagingSenderId = 'YOUR_MESSAGING_SENDER_ID'; // FCM Sender ID
  static const String projectId = 'dealhunter-admin'; // Your Project ID
  static const String authDomain = 'dealhunter-admin.firebaseapp.com'; // Your Auth Domain
  static const String databaseUrl = 'https://dealhunter-admin.firebaseio.com'; // Your Database URL
  static const String storageBucket = 'dealhunter-admin.appspot.com'; // Your Storage Bucket

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
  ///     databaseUrl: FirebaseConfig.databaseUrl,
  ///     storageBucket: FirebaseConfig.storageBucket,
  ///   ),
  /// );
  /// ```
}
