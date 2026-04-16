# DealHunter Mobile App

Complete Flutter application for DealHunter - Deal aggregation platform for Egyptian e-commerce.

## 📁 Folder Structure

```
app/
├── user_app/                    ← Flutter app for end users
│   ├── lib/
│   │   ├── screens/             ← UI screens (8 total)
│   │   ├── services/            ← Firebase, API, Stripe
│   │   ├── providers/           ← Riverpod state management
│   │   ├── models/              ← Data models
│   │   ├── config/              ← Theme, router, Firebase
│   │   ├── widgets/             ← Reusable components
│   │   └── utils/               ← Helpers, formatting
│   ├── ios/                     ← iOS configuration
│   ├── android/                 ← Android configuration
│   ├── pubspec.yaml
│   └── README.md
│
├── admin_app/                   ← Flutter app for admins
│   ├── lib/
│   │   ├── screens/             ← Admin UI (10+ screens)
│   │   ├── services/            ← Auth, permissions, API
│   │   ├── providers/           ← Riverpod state
│   │   ├── models/              ← Admin models
│   │   ├── config/              ← Theme, router, Firebase
│   │   ├── widgets/             ← Admin components
│   │   └── utils/               ← Admin utilities
│   ├── ios/
│   ├── android/
│   ├── pubspec.yaml
│   └── README.md
│
├── assets/                      ← Shared images, icons
│   └── images/
│
├── documentation/               ← All guides & specs
│   ├── FLUTTER_APP_BUILD_GUIDE.md
│   ├── FLUTTER_SCREENS_IMPLEMENTATION.md
│   ├── FLUTTER_COMPLETE_APP_PART2.md
│   ├── FLUTTER_ADMIN_APP_GUIDE.md
│   ├── ADMIN_APP_IMPLEMENTATION_ROADMAP.md
│   ├── FLUTTER_FCM_PUSH_NOTIFICATIONS_GUIDE.md
│   ├── APP_STORE_SUBMISSION_GUIDE.md
│   ├── PHASE_2_IMPLEMENTATION_COMPLETE.md
│   └── COMPLETE_DELIVERY_SUMMARY.md
│
└── README.md                    ← This file
```

---

## 🚀 Quick Start

### User App
```bash
cd user_app
flutter pub get
flutter run
```

### Admin App
```bash
cd admin_app
flutter pub get
flutter run
```

---

## 📚 Documentation

All guides are in the `documentation/` folder:

| Guide | Purpose |
|-------|---------|
| FLUTTER_APP_BUILD_GUIDE.md | Complete user app setup |
| FLUTTER_SCREENS_IMPLEMENTATION.md | 6 core screens |
| FLUTTER_COMPLETE_APP_PART2.md | 4 additional screens |
| FLUTTER_ADMIN_APP_GUIDE.md | Admin app architecture |
| ADMIN_APP_IMPLEMENTATION_ROADMAP.md | Phase 2 & 3 tasks |
| FLUTTER_FCM_PUSH_NOTIFICATIONS_GUIDE.md | Push notifications |
| APP_STORE_SUBMISSION_GUIDE.md | App Store & Play Store |
| PHASE_2_IMPLEMENTATION_COMPLETE.md | 4 completed screens |

---

## 🎯 Status

### User App
- ✅ 8 screens complete
- ✅ Firebase + Stripe integration
- ✅ Push notifications ready
- ✅ Ready to submit to app stores

### Admin App
- ✅ Architecture designed
- ✅ Core services implemented
- ✅ Phase 2: 4 screens complete (Users, Deals, Team, Notifications)
- ✅ Ready for integration testing

---

## 📋 What Goes Where

### user_app/lib/screens/
- `auth/` - Login, signup screens
- `home/` - Deal feed
- `deals/` - Deal details
- `membership/` - Tier info, upgrade
- `groups/` - User groups
- `referrals/` - Referral program
- `notifications/` - Push notifications
- `profile/` - User settings
- `shared/` - Navigation shell

### admin_app/lib/screens/
- `auth/` - Admin login
- `dashboard/` - Analytics overview
- `users/` - User management
- `deals/` - Deal management
- `notifications/` - Send notifications
- `team/` - Admin team management
- `tiers/` - Subscription tiers
- `analytics/` - Detailed analytics
- `settings/` - Admin settings
- `shared/` - Navigation shell

### Configuration
- `config/firebase_config.dart` - Firebase init
- `config/router.dart` - Navigation
- `config/theme.dart` - Material Design 3

### Services
- `api_client.dart` - HTTP requests (Dio)
- `auth_service.dart` - Firebase auth
- `fcm_service.dart` - Push notifications
- `permission_service.dart` - Role-based access

### Providers (State Management)
- `auth_provider.dart` - Login state
- `users_provider.dart` - User CRUD
- `deals_provider.dart` - Deal CRUD
- `notifications_provider.dart` - Notifications
- `team_provider.dart` - Admin team

### Models
- `user.dart` - User data structure
- `deal.dart` - Deal data structure
- `tier.dart` - Subscription tier
- `admin_user.dart` - Admin user
- `notification.dart` - Notification data

---

## ⚙️ Dependencies

### Core
- flutter_riverpod - State management
- go_router - Navigation
- firebase_core - Firebase setup
- firebase_auth - Authentication

### Backend
- dio - HTTP client
- firebase_messaging - Push notifications
- cloud_firestore - Database

### Payments
- stripe_flutter - Payment processing

### UI
- flutter_material_design_icons
- intl - Localization
- fl_chart - Analytics charts

---

## 🔐 Environment Setup

1. **Firebase Project**
   - Create project at firebase.google.com
   - Add iOS & Android apps
   - Download configuration files

2. **Stripe Account**
   - Create account at stripe.com
   - Get test API keys
   - Switch to live before production

3. **Apple Developer**
   - $99/year membership
   - Create signing certificates
   - Configure APNs for push notifications

4. **Google Play Developer**
   - $25 one-time
   - Create keystore for signing
   - Configure FCM

---

## 📱 Build Commands

### User App
```bash
# Development
flutter run

# iOS Release Build
flutter build ios --release

# Android Release Build
flutter build appbundle --release
```

### Admin App
```bash
# Development
flutter run

# iOS Release Build
flutter build ios --release

# Android APK Build
flutter build apk --release
```

---

## 🧪 Testing

### Unit Tests
```bash
flutter test
```

### Integration Tests
```bash
flutter drive --target=test_driver/app.dart
```

### Device Testing
- Test on iPhone 13+ (iOS)
- Test on Samsung Galaxy/Pixel (Android)
- Test on real devices, not just emulators

---

## 📦 Deployment

### App Store (iOS)
See: `documentation/APP_STORE_SUBMISSION_GUIDE.md`
- Submit via App Store Connect
- Apple review: 1-3 days

### Google Play (Android)
See: `documentation/APP_STORE_SUBMISSION_GUIDE.md`
- Submit via Play Console
- Google review: 2-4 hours

---

## 📞 Support

For implementation questions, refer to:
1. Specific screen documentation (e.g., FLUTTER_SCREENS_IMPLEMENTATION.md)
2. API integration guide (FLUTTER_APP_BUILD_GUIDE.md)
3. Troubleshooting sections in each guide

---

## 📝 License

Proprietary - DealHunter Egypt

---

**Last Updated:** 2026-04-16  
**Status:** Production Ready ✅
