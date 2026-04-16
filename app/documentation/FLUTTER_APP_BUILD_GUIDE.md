# Flutter App Build - Complete Implementation Guide

**Status:** Starting Now  
**Timeline:** 4-5 weeks  
**Target:** iOS + Android + Admin App  
**Date:** 2026-04-16

---

## 📁 PROJECT SETUP

### Step 1: Create Flutter Projects

```bash
# Create main user app
flutter create dealhunter_user

# Create admin app
flutter create dealhunter_admin

# Navigate to user app
cd dealhunter_user
```

### Step 2: Update pubspec.yaml (User App)

```yaml
name: dealhunter_user
description: DealHunter Egypt - Deal finder app
publish_to: 'none'

version: 1.0.0+1

environment:
  sdk: '>=3.0.0 <4.0.0'

dependencies:
  flutter:
    sdk: flutter

  # State Management
  riverpod: ^2.4.0
  flutter_riverpod: ^2.4.0

  # Firebase
  firebase_core: ^2.24.0
  firebase_auth: ^4.10.0
  firebase_messaging: ^14.6.0
  cloud_firestore: ^4.13.0

  # Networking
  dio: ^5.3.0
  retrofit: ^4.1.0
  json_serializable: ^6.7.0

  # UI
  google_fonts: ^6.0.0
  intl: ^0.19.0

  # Payments
  stripe_flutter: ^8.0.0

  # Navigation
  go_router: ^12.0.0

  # Storage
  shared_preferences: ^2.2.0
  hive: ^2.2.0
  hive_flutter: ^1.1.0

  # Utils
  uuid: ^4.0.0
  cached_network_image: ^3.3.0

dev_dependencies:
  flutter_test:
    sdk: flutter
  flutter_lints: ^2.0.0
  build_runner: ^2.4.0
  retrofit_generator: ^8.0.0
  json_serializable: ^6.7.0

flutter:
  uses-material-design: true

  assets:
    - assets/images/
    - assets/logos/

  fonts:
    - family: Poppins
      fonts:
        - asset: assets/fonts/Poppins-Regular.ttf
        - asset: assets/fonts/Poppins-Bold.ttf
          weight: 700
```

### Step 3: Install Dependencies

```bash
flutter pub get
flutter pub run build_runner build --delete-conflicting-outputs
```

---

## 🏗️ PROJECT STRUCTURE

```
dealhunter_user/
├── lib/
│   ├── main.dart
│   ├── config/
│   │   ├── firebase_config.dart
│   │   ├── api_config.dart
│   │   └── theme.dart
│   ├── models/
│   │   ├── user.dart
│   │   ├── deal.dart
│   │   ├── tier.dart
│   │   ├── group.dart
│   │   └── notification.dart
│   ├── services/
│   │   ├── api_client.dart
│   │   ├── auth_service.dart
│   │   ├── firebase_service.dart
│   │   ├── payment_service.dart
│   │   └── notification_service.dart
│   ├── providers/
│   │   ├── auth_provider.dart
│   │   ├── deals_provider.dart
│   │   ├── user_provider.dart
│   │   ├── groups_provider.dart
│   │   └── notifications_provider.dart
│   ├── screens/
│   │   ├── auth/
│   │   │   ├── login_screen.dart
│   │   │   ├── signup_screen.dart
│   │   │   └── password_reset_screen.dart
│   │   ├── home/
│   │   │   ├── home_screen.dart
│   │   │   ├── deal_detail_screen.dart
│   │   │   └── deal_filters_screen.dart
│   │   ├── membership/
│   │   │   ├── membership_screen.dart
│   │   │   └── tier_upgrade_screen.dart
│   │   ├── social/
│   │   │   ├── groups_screen.dart
│   │   │   ├── referrals_screen.dart
│   │   │   └── notifications_screen.dart
│   │   └── profile/
│   │       ├── profile_screen.dart
│   │       └── settings_screen.dart
│   ├── widgets/
│   │   ├── deal_card.dart
│   │   ├── tier_badge.dart
│   │   ├── loading_shimmer.dart
│   │   └── custom_button.dart
│   └── utils/
│       ├── constants.dart
│       ├── extensions.dart
│       └── formatters.dart
├── assets/
│   ├── images/
│   ├── logos/
│   └── fonts/
├── android/
├── ios/
└── pubspec.yaml
```

---

## 🔐 CORE FILES - PART 1: CONFIGURATION

### lib/config/firebase_config.dart

```dart
import 'package:firebase_core/firebase_core.dart';
import 'firebase_options.dart';

class FirebaseConfig {
  static Future<void> initialize() async {
    await Firebase.initializeApp(
      options: DefaultFirebaseOptions.currentPlatform,
    );
  }
}
```

### lib/config/firebase_options.dart

```dart
import 'package:firebase_core/firebase_core.dart';

class DefaultFirebaseOptions {
  static FirebaseOptions get currentPlatform {
    return const FirebaseOptions(
      apiKey: "AIzaSyCM7irklt9VLM7NrIXovI3oZQ9wkoodywU",
      authDomain: "dealhunter-egypt-70d29.firebaseapp.com",
      projectId: "dealhunter-egypt-70d29",
      storageBucket: "dealhunter-egypt-70d29.appspot.com",
      messagingSenderId: "477835366168",
      appId: "1:477835366168:ios:YOUR_IOS_APP_ID",
      iosBundleId: "com.dealhunter.egypt",
      androidClientId: "YOUR_ANDROID_CLIENT_ID.apps.googleusercontent.com",
    );
  }
}
```

### lib/config/api_config.dart

```dart
class ApiConfig {
  static const String baseUrl = 'https://dealhunter-scraper.onrender.com/api/v1';
  static const String stripePublishableKey = 'pk_test_YOUR_KEY';
  static const Duration connectTimeout = Duration(seconds: 10);
  static const Duration receiveTimeout = Duration(seconds: 10);
}
```

### lib/config/theme.dart

```dart
import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';

class AppTheme {
  static const Color primaryColor = Color(0xFFE24B4A);
  static const Color backgroundColor = Color(0xFFF4F5F7);
  static const Color textDark = Color(0xFF222222);
  static const Color textLight = Color(0xFF666666);
  static const Color borderColor = Color(0xFFDDDDDD);

  static ThemeData get lightTheme {
    return ThemeData(
      useMaterial3: true,
      colorScheme: ColorScheme.fromSeed(
        seedColor: primaryColor,
        brightness: Brightness.light,
      ),
      textTheme: GoogleFonts.poppinsTextTheme(),
      appBarTheme: AppBarTheme(
        backgroundColor: Colors.white,
        elevation: 0,
        centerTitle: true,
        titleTextStyle: GoogleFonts.poppins(
          fontSize: 18,
          fontWeight: FontWeight.w600,
          color: textDark,
        ),
      ),
    );
  }
}
```

---

## 🔐 CORE FILES - PART 2: MODELS

### lib/models/user.dart

```dart
class User {
  final String uid;
  final String email;
  final String name;
  final String tier; // 'free', 'trial', 'premium', 'vip'
  final int dailyDealLimit;
  final int dealsViewedToday;
  final String? referralCode;
  final DateTime createdAt;
  final DateTime? lastLogin;

  User({
    required this.uid,
    required this.email,
    required this.name,
    required this.tier,
    required this.dailyDealLimit,
    required this.dealsViewedToday,
    this.referralCode,
    required this.createdAt,
    this.lastLogin,
  });

  bool get canViewMoreDeals => dealsViewedToday < dailyDealLimit;
  int get remainingDeals => dailyDealLimit - dealsViewedToday;

  factory User.fromJson(Map<String, dynamic> json) {
    return User(
      uid: json['uid'] ?? '',
      email: json['email'] ?? '',
      name: json['name'] ?? '',
      tier: json['tier'] ?? 'free',
      dailyDealLimit: json['daily_deal_limit'] ?? 50,
      dealsViewedToday: json['deals_viewed_today'] ?? 0,
      referralCode: json['referral_code'],
      createdAt: DateTime.parse(json['created_at'] ?? DateTime.now().toIso8601String()),
      lastLogin: json['last_login'] != null ? DateTime.parse(json['last_login']) : null,
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'uid': uid,
      'email': email,
      'name': name,
      'tier': tier,
      'daily_deal_limit': dailyDealLimit,
      'deals_viewed_today': dealsViewedToday,
      'referral_code': referralCode,
      'created_at': createdAt.toIso8601String(),
      'last_login': lastLogin?.toIso8601String(),
    };
  }
}
```

### lib/models/deal.dart

```dart
class Deal {
  final String id;
  final String title;
  final double currentPrice;
  final double originalPrice;
  final int discountPercent;
  final String? imageUrl;
  final String? productUrl;
  final String site; // 'amazon_eg', 'jumia_eg', 'noon_eg'
  final String siteDisplay; // 'Amazon Egypt', 'Jumia Egypt', etc
  final String? category;
  final double? rating;
  final int? reviewCount;
  final String? verdict; // 'GENUINE', 'SUSPICIOUS', 'FAKE'
  final DateTime? timestamp;
  final bool verified;
  final bool hidden;

  Deal({
    required this.id,
    required this.title,
    required this.currentPrice,
    required this.originalPrice,
    required this.discountPercent,
    this.imageUrl,
    this.productUrl,
    required this.site,
    required this.siteDisplay,
    this.category,
    this.rating,
    this.reviewCount,
    this.verdict,
    this.timestamp,
    required this.verified,
    required this.hidden,
  });

  factory Deal.fromJson(Map<String, dynamic> json) {
    return Deal(
      id: json['id'] ?? '',
      title: json['title'] ?? 'Unknown',
      currentPrice: (json['current_price'] ?? 0).toDouble(),
      originalPrice: (json['original_price'] ?? 0).toDouble(),
      discountPercent: json['discount_percent'] ?? 0,
      imageUrl: json['image_url'],
      productUrl: json['product_url'],
      site: json['site'] ?? 'unknown',
      siteDisplay: json['site_display'] ?? 'Unknown',
      category: json['category'],
      rating: json['rating']?.toDouble(),
      reviewCount: json['review_count'],
      verdict: json['verdict'],
      timestamp: json['timestamp'] != null ? DateTime.parse(json['timestamp']) : null,
      verified: json['verified'] ?? false,
      hidden: json['hidden'] ?? false,
    );
  }
}
```

### lib/models/tier.dart

```dart
class Tier {
  final String name;
  final int dailyLimit;
  final double price;
  final List<String> features;
  final String currency;

  Tier({
    required this.name,
    required this.dailyLimit,
    required this.price,
    required this.features,
    this.currency = 'USD',
  });

  factory Tier.fromJson(Map<String, dynamic> json) {
    return Tier(
      name: json['name'] ?? '',
      dailyLimit: json['daily_limit'] ?? 0,
      price: (json['price'] ?? 0).toDouble(),
      features: List<String>.from(json['features'] ?? []),
      currency: json['currency'] ?? 'USD',
    );
  }
}
```

### lib/models/group.dart

```dart
class UserGroup {
  final String id;
  final String name;
  final String adminEmail;
  final int memberCount;
  final String? tier;
  final int dailyBudget;
  final String description;
  final DateTime createdAt;

  UserGroup({
    required this.id,
    required this.name,
    required this.adminEmail,
    required this.memberCount,
    this.tier,
    required this.dailyBudget,
    required this.description,
    required this.createdAt,
  });

  factory UserGroup.fromJson(Map<String, dynamic> json) {
    return UserGroup(
      id: json['id'] ?? '',
      name: json['name'] ?? '',
      adminEmail: json['admin_email'] ?? '',
      memberCount: json['member_count'] ?? 0,
      tier: json['tier'],
      dailyBudget: json['daily_budget'] ?? 0,
      description: json['description'] ?? '',
      createdAt: DateTime.parse(json['created_at'] ?? DateTime.now().toIso8601String()),
    );
  }
}
```

---

## 🌐 CORE FILES - PART 3: API CLIENT

### lib/services/api_client.dart

```dart
import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../config/api_config.dart';

class ApiClient {
  late final Dio _dio;
  String? _authToken;

  ApiClient() {
    _dio = Dio(BaseOptions(
      baseUrl: ApiConfig.baseUrl,
      connectTimeout: ApiConfig.connectTimeout,
      receiveTimeout: ApiConfig.receiveTimeout,
    ));

    _dio.interceptors.add(
      InterceptorsWrapper(
        onRequest: (options, handler) {
          if (_authToken != null) {
            options.headers['Authorization'] = 'Bearer $_authToken';
          }
          return handler.next(options);
        },
        onError: (error, handler) {
          print('API Error: ${error.message}');
          return handler.next(error);
        },
      ),
    );
  }

  void setToken(String token) {
    _authToken = token;
  }

  void clearToken() {
    _authToken = null;
  }

  // Authentication
  Future<Map<String, dynamic>> login(String email, String password) async {
    final response = await _dio.post(
      '/auth/login',
      data: {'email': email, 'password': password},
    );
    return response.data;
  }

  Future<Map<String, dynamic>> signup(String email, String password, String name) async {
    final response = await _dio.post(
      '/auth/register',
      data: {'email': email, 'password': password, 'name': name},
    );
    return response.data;
  }

  // Users
  Future<Map<String, dynamic>> getUserProfile() async {
    final response = await _dio.get('/user/me');
    return response.data;
  }

  Future<void> updateUserProfile(String name) async {
    await _dio.put('/users/me', data: {'name': name});
  }

  // Deals
  Future<List<dynamic>> getDeals({
    int limit = 50,
    String? category,
    String? site,
  }) async {
    final response = await _dio.get(
      '/deals',
      queryParameters: {
        'limit': limit,
        if (category != null) 'category': category,
        if (site != null) 'site': site,
      },
    );
    return response.data['deals'] ?? [];
  }

  Future<void> logDealClick(String dealId) async {
    await _dio.post('/deals/$dealId/click');
  }

  // Tiers
  Future<List<dynamic>> getTiers() async {
    final response = await _dio.get('/tiers');
    return response.data['tiers'] ?? [];
  }

  Future<Map<String, dynamic>> getCurrentSubscription() async {
    final response = await _dio.get('/subscriptions/current');
    return response.data;
  }

  // Payments
  Future<Map<String, dynamic>> createStripeCheckout(String tier) async {
    final response = await _dio.post(
      '/subscriptions/checkout',
      data: {'tier': tier},
    );
    return response.data;
  }

  // Groups
  Future<List<dynamic>> getUserGroups() async {
    final response = await _dio.get('/user/groups');
    return response.data['groups'] ?? [];
  }

  Future<Map<String, dynamic>> createGroup(String name, List<String> members) async {
    final response = await _dio.post(
      '/user-groups',
      data: {'name': name, 'members': members},
    );
    return response.data;
  }

  // Referrals
  Future<String> getReferralCode() async {
    final response = await _dio.get('/user/referral-code');
    return response.data['code'] ?? '';
  }

  Future<Map<String, dynamic>> getReferralStatus() async {
    final response = await _dio.get('/user/referral-status');
    return response.data;
  }

  // Notifications
  Future<List<dynamic>> getNotifications() async {
    final response = await _dio.get('/user/notifications');
    return response.data['notifications'] ?? [];
  }

  Future<void> markNotificationAsRead(String notificationId) async {
    await _dio.post('/notifications/$notificationId/read');
  }
}

// Riverpod provider
final apiClientProvider = Provider<ApiClient>((ref) {
  return ApiClient();
});
```

---

## 🔐 CORE FILES - PART 4: AUTHENTICATION SERVICE

### lib/services/auth_service.dart

```dart
import 'package:firebase_auth/firebase_auth.dart' as firebase_auth;
import 'package:flutter/foundation.dart';
import 'package:shared_preferences/shared_preferences.dart';

class AuthService extends ChangeNotifier {
  final firebase_auth.FirebaseAuth _auth = firebase_auth.FirebaseAuth.instance;
  firebase_auth.User? _user;
  String? _idToken;

  firebase_auth.User? get user => _user;
  String? get idToken => _idToken;
  bool get isAuthenticated => _user != null;

  AuthService() {
    _auth.authStateChanges().listen((firebase_auth.User? user) {
      _user = user;
      notifyListeners();
    });
  }

  Future<void> signup(String email, String password, String name) async {
    try {
      final userCredential = await _auth.createUserWithEmailAndPassword(
        email: email,
        password: password,
      );
      
      await userCredential.user?.updateDisplayName(name);
      _user = userCredential.user;
      _idToken = await userCredential.user?.getIdToken();
      
      // Save token
      await _saveToken(_idToken!);
      notifyListeners();
    } catch (e) {
      rethrow;
    }
  }

  Future<void> login(String email, String password) async {
    try {
      final userCredential = await _auth.signInWithEmailAndPassword(
        email: email,
        password: password,
      );
      
      _user = userCredential.user;
      _idToken = await userCredential.user?.getIdToken();
      
      // Save token
      await _saveToken(_idToken!);
      notifyListeners();
    } catch (e) {
      rethrow;
    }
  }

  Future<void> logout() async {
    try {
      await _auth.signOut();
      _user = null;
      _idToken = null;
      
      // Clear token
      final prefs = await SharedPreferences.getInstance();
      await prefs.remove('idToken');
      
      notifyListeners();
    } catch (e) {
      rethrow;
    }
  }

  Future<void> resetPassword(String email) async {
    try {
      await _auth.sendPasswordResetEmail(email: email);
    } catch (e) {
      rethrow;
    }
  }

  Future<String> _saveToken(String token) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString('idToken', token);
    return token;
  }

  Future<String?> getSavedToken() async {
    final prefs = await SharedPreferences.getInstance();
    return prefs.getString('idToken');
  }
}
```

---

## ✅ NEXT STEPS

I've created the **foundation files**. In the next section, I'll build:

1. ✅ **Authentication Screens** (Login, Signup, Password Reset)
2. ✅ **Home Screen** (Deal Feed with filters)
3. ✅ **Deal Detail Screen**
4. ✅ **Membership Screen** (with Stripe integration)
5. ✅ **Groups & Referrals**
6. ✅ **Settings & Profile**
7. ✅ **Admin App** (full variant)
8. ✅ **State Management** (Riverpod providers)
9. ✅ **Firebase Messaging** (Push notifications)
10. ✅ **App Store submission** guide

---

## 🚀 TO GET STARTED:

1. Create Flutter project: `flutter create dealhunter_user`
2. Copy the files above into the `lib/` folder
3. Run `flutter pub get`
4. Run `flutter pub run build_runner build`
5. Start the app: `flutter run`

---

**Shall I continue with the authentication screens and full app implementation?** 🎯

I can provide:
- Complete login/signup screens
- Deal feed screen
- Membership/payment screens
- Full admin app variant
- Push notification setup
- Firebase integration
- App store submission guide

Just confirm and I'll build the complete working app! 🚀
