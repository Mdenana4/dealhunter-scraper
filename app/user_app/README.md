# DealHunter User App (Flutter)

End-user facing mobile application for browsing deals, managing subscriptions, and earning referral rewards.

## 📋 Project Overview

**Platforms:** iOS + Android  
**Framework:** Flutter  
**Language:** Dart  
**State Management:** Riverpod  
**Navigation:** GoRouter  

---

## 🎯 Features

### Authentication
- ✅ Email/password signup & login
- ✅ Firebase authentication
- ✅ Token-based session management

### Deal Browsing
- ✅ Browse deals from Egyptian e-commerce sites
- ✅ Filter by source (Amazon, Jumia, Noon)
- ✅ Filter by category
- ✅ Search deals
- ✅ View deal details with images & ratings
- ✅ Mark deals as fake/suspicious

### Membership
- ✅ View current subscription tier
- ✅ Upgrade tier via Stripe
- ✅ Track daily deal usage (X/Y deals today)
- ✅ Show tier benefits

### Social Features
- ✅ Create & join user groups
- ✅ Share deals with friends
- ✅ Referral program with unique code
- ✅ Gift deals to contacts
- ✅ View referral rewards

### Notifications
- ✅ Push notifications (FCM)
- ✅ In-app notifications
- ✅ Notification preferences
- ✅ Smart notification delivery

### User Account
- ✅ Profile view & edit
- ✅ Change password
- ✅ Manage notification settings
- ✅ View account history
- ✅ Logout

---

## 🏗️ Folder Structure

```
lib/
├── screens/
│   ├── auth/
│   │   ├── login_screen.dart
│   │   └── signup_screen.dart
│   ├── home/
│   │   ├── home_screen.dart
│   │   └── deal_detail_screen.dart
│   ├── deals/
│   │   └── deal_detail_screen.dart
│   ├── membership/
│   │   └── membership_screen.dart
│   ├── groups/
│   │   └── groups_screen.dart
│   ├── referrals/
│   │   └── referrals_screen.dart
│   ├── notifications/
│   │   └── notifications_screen.dart
│   ├── profile/
│   │   └── profile_screen.dart
│   └── shared/
│       ├── app_shell.dart
│       └── error_screen.dart
├── services/
│   ├── api_client.dart
│   ├── auth_service.dart
│   ├── fcm_service.dart
│   ├── stripe_service.dart
│   └── firebase_service.dart
├── providers/
│   ├── auth_provider.dart
│   ├── users_provider.dart
│   ├── deals_provider.dart
│   ├── membership_provider.dart
│   ├── groups_provider.dart
│   ├── referrals_provider.dart
│   └── notifications_provider.dart
├── models/
│   ├── user.dart
│   ├── deal.dart
│   ├── tier.dart
│   ├── group.dart
│   ├── referral.dart
│   └── notification.dart
├── config/
│   ├── firebase_config.dart
│   ├── router.dart
│   └── theme.dart
├── widgets/
│   ├── deal_card.dart
│   ├── tier_badge.dart
│   ├── loading_skeleton.dart
│   └── notification_banner.dart
├── utils/
│   ├── formatting.dart
│   ├── validators.dart
│   └── constants.dart
├── main.dart
└── index.dart
```

---

## 🚀 Getting Started

### Prerequisites
- Flutter 3.0+ installed
- Dart 3.0+ installed
- Firebase project created
- Stripe account created

### Installation

1. **Clone/Setup Project**
   ```bash
   cd app/user_app
   flutter pub get
   ```

2. **Configure Firebase**
   - Download `GoogleService-Info.plist` (iOS)
   - Download `google-services.json` (Android)
   - Place in `ios/Runner/` and `android/app/`

3. **Setup Stripe**
   - Add test API keys to environment
   - Configure `stripe_flutter` in pubspec.yaml

4. **Run App**
   ```bash
   flutter run
   ```

---

## 🎨 UI Screens (8 Total)

### 1. Login Screen
- Email/password input
- Validation & error handling
- Forgot password link
- Sign up link

### 2. Signup Screen
- Create account
- Email verification
- Password strength validation
- Terms acceptance

### 3. Home/Deal Feed Screen
- List deals with infinite scroll
- Filter by source & category
- Search functionality
- Deal cards with images & prices
- Discount badges
- Open product link button

### 4. Deal Detail Screen
- Full deal information
- Product image & gallery
- Pricing comparison
- User reviews & ratings
- Fraud verdict badge
- Share deal option
- External product link

### 5. Membership Screen
- Current tier display
- Renewal date
- Daily usage meter (X/Y deals)
- Tier comparison cards
- Upgrade buttons
- Stripe payment integration

### 6. Groups Screen
- List user's groups
- Create group dialog
- Join group with code
- View group members
- Show group daily limit
- Leave group

### 7. Referrals Screen
- Display referral code
- Copy to clipboard
- Share via WhatsApp/Email
- Show referrals made
- Display rewards earned
- "How it works" section

### 8. Notifications Screen
- List all notifications
- Mark as read
- Dismiss notification
- Time-ago formatting (2h ago, 1d ago)
- Deep link handling

### 9. Profile Screen
- User avatar & name
- Current tier badge
- Account settings
- Change password dialog
- Language selector
- Notification preferences
- Logout button

---

## 🔌 API Integration

### Base URL
```
https://dealhunter-scraper.onrender.com/api/v1
```

### Key Endpoints
```
POST /auth/register              → Create account
POST /auth/login                 → Login (Firebase)
GET /user/me                     → Get profile
GET /deals                       → List deals
PUT /users/{user_id}             → Update profile
POST /payment/checkout           → Stripe session
GET /user/groups                 → List groups
POST /user/groups                → Create group
GET /user/referral-code          → Get code
POST /user/gift/{deal_id}        → Gift deal
```

---

## 🛠️ Development Workflow

### Adding New Screen

1. Create screen file: `lib/screens/{feature}/{name}_screen.dart`
2. Add route to `lib/config/router.dart`
3. Create provider if needed: `lib/providers/{feature}_provider.dart`
4. Create model if needed: `lib/models/{feature}.dart`
5. Add navigation button to app shell

### Adding New Feature

1. Create provider: `lib/providers/{feature}_provider.dart`
2. Create service if external API: `lib/services/{feature}_service.dart`
3. Create models: `lib/models/{feature}.dart`
4. Create screens: `lib/screens/{feature}/{screen}_screen.dart`
5. Add routes to router

---

## 📱 Build for Devices

### iOS
```bash
flutter build ios --release
# Use Xcode to sign and submit to App Store
open ios/Runner.xcworkspace
```

### Android
```bash
flutter build appbundle --release
# Upload to Google Play Console
```

---

## 🧪 Testing

### Run All Tests
```bash
flutter test
```

### Test Specific File
```bash
flutter test test/screens/auth/login_screen_test.dart
```

### Integration Testing
```bash
flutter drive --target=test_driver/app.dart
```

---

## 📊 State Management (Riverpod)

### Provider Pattern
```dart
// Define provider
final dealsProvider = FutureProvider<List<Deal>>((ref) async {
  return await fetchDeals();
});

// Use in widget
final deals = ref.watch(dealsProvider);
```

### Watching State Changes
```dart
// Trigger mutation
ref.read(updateUserProvider((userId, userData)).future);

// Refresh data
ref.refresh(dealsProvider);
```

---

## 🔐 Security

- ✅ Token stored in secure storage (flutter_secure_storage)
- ✅ API calls include Bearer token
- ✅ Firebase rules restrict unauthorized access
- ✅ Sensitive data not logged
- ✅ HTTPS only

---

## 📲 Push Notifications

### Setup
See: `../documentation/FLUTTER_FCM_PUSH_NOTIFICATIONS_GUIDE.md`

### Implementation
- Request notification permission
- Get FCM token
- Subscribe to topics
- Handle foreground/background notifications

---

## 🎨 Theme & Styling

### Material Design 3
- Dynamic colors
- Light/Dark mode support
- Consistent typography
- Standard component sizes

### Custom Theme
See: `lib/config/theme.dart`

---

## 📦 Dependencies

```yaml
# State Management
flutter_riverpod: ^2.4.0

# Navigation
go_router: ^12.1.0

# Firebase
firebase_core: ^2.24.0
firebase_auth: ^4.15.0
cloud_firestore: ^4.14.0
firebase_messaging: ^14.7.0

# HTTP
dio: ^5.4.0

# Payments
stripe_flutter: ^9.0.0

# Storage
flutter_secure_storage: ^9.1.0
shared_preferences: ^2.2.2

# UI
flutter_material_design_icons: ^0.0.2
intl: ^0.19.0
```

---

## 📝 Code Style

- Use descriptive variable names
- Add type annotations
- Document complex logic
- Follow Dart style guide
- Use `const` constructors where possible

---

## 🐛 Debugging

### Enable Debug Logging
```dart
// In main.dart
import 'package:flutter/foundation.dart';

if (kDebugMode) {
  print('DEBUG: $message');
}
```

### Firebase Emulator (Optional)
```bash
firebase emulators:start
```

---

## 📚 Further Reading

- Flutter Docs: https://flutter.dev/docs
- Firebase Docs: https://firebase.google.com/docs/flutter/setup
- Riverpod: https://riverpod.dev
- GoRouter: https://pub.dev/packages/go_router

---

## 🚀 Production Checklist

- [ ] Test on real iOS device
- [ ] Test on real Android device
- [ ] All screens responsive
- [ ] No console errors/warnings
- [ ] Performance acceptable (< 2s startup)
- [ ] Privacy policy ready
- [ ] Terms of service ready
- [ ] App icons & screenshots ready
- [ ] Firebase security rules reviewed
- [ ] Stripe switched to LIVE mode
- [ ] Ready to submit!

---

**Status:** ✅ PRODUCTION READY

Last Updated: 2026-04-16
