# Production Deployment Guide - DealHunter Admin App

**Status:** 🟢 **READY FOR PRODUCTION**  
**Version:** 1.0.0  
**Last Updated:** 2026-04-16

---

## Overview

Complete production deployment guide for DealHunter Admin App. This covers:
- Firebase production setup
- Backend deployment to Render
- Flutter app release builds
- Monitoring and security

**Total Time Estimate:** 3-4 hours

---

## Phase 1: Firebase Production Setup (45 minutes)

### 1.1 Create Firebase Project

```
1. Go to https://console.firebase.google.com/
2. Click "Create a project"
3. Project name: dealhunter-admin-prod
4. Enable Google Analytics (recommended for production)
5. Create project and wait for completion
```

### 1.2 Get Firebase Service Account

**For Backend (server.py):**
```
1. Go to Project Settings (gear icon)
2. Click "Service Accounts" tab
3. Select "Python" SDK
4. Click "Generate new private key"
5. Save as firebase-credentials.json (KEEP SECRET)
6. Copy entire JSON content
```

### 1.3 Setup Authentication

```
1. Go to Authentication > Sign-in method
2. Enable "Email/Password" authentication
3. Click Save
4. Go to Authentication > Users
5. Create admin user:
   - Email: admin@example.com (or your admin email)
   - Password: Generate STRONG password (32+ chars with numbers/symbols)
   - Save credentials securely
```

### 1.4 Create Firestore Database

```
1. Go to Firestore Database
2. Click "Create database"
3. Location: us-central1 (or closest to you)
4. Start in "Production mode"
5. Click "Create"
6. Wait for database creation (2-3 minutes)
```

### 1.5 Create Firestore Collections

Create exactly 4 collections with these structures:

**Collection 1: admin_users**
```
Document: admin@example.com
{
  "email": "admin@example.com",
  "name": "Administrator",
  "role": "owner",
  "permissions": ["sources", "deals", "users", "notifications", "checker", "competitors", "scraper_control"],
  "status": "active",
  "added_at": timestamp(now),
  "added_by": "system",
  "last_login": timestamp(now),
  "notes": "First admin user"
}
```

**Collection 2: users** (empty, auto-populated by scraper)
```
Auto-generated documents with structure:
{
  "email": "user@example.com",
  "name": "User Name",
  "tier": "free",
  "daily_deal_limit": 50,
  "registered_at": timestamp,
  "last_login": timestamp,
  "is_active": true,
  "group_name": null,
  "stripe_customer_id": null
}
```

**Collection 3: deals** (auto-populated by scraper)
```
Auto-generated documents
```

**Collection 4: notifications** (empty)
```
Can remain empty, will be populated by app
```

### 1.6 Deploy Firestore Security Rules

**Go to:** Firestore > Rules tab

**Replace all content with:**

```javascript
rules_version = '2';
service cloud.firestore {
  match /databases/{database}/documents {
    
    // Admin user functions
    function isAdmin() {
      return request.auth != null && 
             exists(/databases/$(database)/documents/admin_users/$(request.auth.token.email));
    }
    
    function isOwner() {
      let admin = get(/databases/$(database)/documents/admin_users/$(request.auth.token.email));
      return admin != null && admin.data.role == 'owner';
    }
    
    function hasPermission(perm) {
      let admin = get(/databases/$(database)/documents/admin_users/$(request.auth.token.email));
      return admin != null && admin.data.permissions.hasAll([perm]);
    }
    
    // Admin users - Owner only
    match /admin_users/{email} {
      allow read: if isAdmin();
      allow write: if isOwner();
    }
    
    // Users - Admin with users permission
    match /users/{userId} {
      allow read: if isAdmin();
      allow write: if isAdmin() && (hasPermission('users') || isOwner());
    }
    
    // Deals - Admin with deals permission
    match /deals/{dealId} {
      allow read: if isAdmin();
      allow write: if isAdmin() && (hasPermission('deals') || isOwner());
    }
    
    // Notifications - Admin with notifications permission
    match /notifications/{notifId} {
      allow read: if isAdmin();
      allow write: if isAdmin() && (hasPermission('notifications') || isOwner());
    }
    
    // Deny all other access
    match /{document=**} {
      allow read, write: if false;
    }
  }
}
```

**Click "Publish"** and verify success

### 1.7 Get Firebase Configuration

**Go to:** Project Settings > Your apps > Select your app

**Copy these 7 values:**
- API Key
- App ID  
- Messaging Sender ID
- Project ID
- Auth Domain
- Database URL
- Storage Bucket

**Save to:** `.env` or password manager (DO NOT commit to git)

---

## Phase 2: Backend Deployment (30 minutes)

### 2.1 Prepare Render Service

#### Create Render Account
```
1. Go to https://render.com
2. Sign up with GitHub account (recommended)
3. Verify email
```

#### Connect GitHub Repository
```
1. Go to Dashboard > New +
2. Select "Web Service"
3. Connect GitHub repository: dealhunter
4. Branch: main
5. Name: dealhunter-scraper (must match for auto-deploys)
6. Environment: Python 3
7. Build command: pip install -r requirements.txt
8. Start command: python server.py
```

### 2.2 Set Environment Variables on Render

**In Render Dashboard:**
```
1. Go to your service: dealhunter-scraper
2. Click "Environment"
3. Add variable: FIREBASE_CREDENTIALS_JSON
4. Value: Paste entire contents of firebase-credentials.json (from 1.2)
5. Click "Save"
6. Service will auto-restart
```

**Verify:** Check logs, should see "✓ Firebase Admin SDK initialized"

### 2.3 Deploy Code

```bash
# In your local repo
git add server.py
git commit -m "Production: Phase 1 API endpoints ready"
git push origin main
```

**Render auto-deploys** (watch logs in Render dashboard)

### 2.4 Test API Endpoints

**Get admin token first** (from Flutter app login or Firebase CLI):

```bash
# Test Users endpoint
curl -H "Authorization: Bearer <YOUR_TOKEN>" \
  https://dealhunter-scraper.onrender.com/api/v1/admin/users

# Expected response:
{
  "success": true,
  "data": [
    {
      "id": "user123",
      "email": "user@example.com",
      "name": "User Name",
      "tier": "free",
      ...
    }
  ]
}
```

**Test Deals endpoint:**
```bash
curl -H "Authorization: Bearer <YOUR_TOKEN>" \
  https://dealhunter-scraper.onrender.com/api/v1/admin/deals

# Expected response:
{
  "success": true,
  "data": [...]
}
```

**All 6 Phase 1 endpoints:**
- ✅ GET /api/v1/admin/users
- ✅ PUT /api/v1/admin/users/<id>
- ✅ GET /api/v1/admin/deals
- ✅ PUT /api/v1/admin/deals/<id>
- ✅ DELETE /api/v1/admin/deals/<id>
- ✅ PATCH /api/v1/admin/deals/<id>/visibility
- ✅ PATCH /api/v1/admin/deals/<id>/featured
- ✅ PATCH /api/v1/admin/deals/<id>/verdict
- ✅ GET /api/v1/admin/notifications
- ✅ GET /api/v1/admin/permissions

---

## Phase 3: Flutter App Release Build (45 minutes)

### 3.1 Update Firebase Config

**File:** `app/admin_app/lib/config/firebase_config.dart`

```dart
class FirebaseConfig {
  static const String apiKey = 'AIzaSy...'; // From Phase 1.7
  static const String appId = '1:123456789:android:abc...';
  static const String messagingSenderId = '123456789';
  static const String projectId = 'dealhunter-admin-prod';
  static const String authDomain = 'dealhunter-admin-prod.firebaseapp.com';
  static const String databaseUrl = 'https://dealhunter-admin-prod.firebaseio.com';
  static const String storageBucket = 'dealhunter-admin-prod.appspot.com';
}
```

### 3.2 Build Android Release APK

```bash
cd app/admin_app

# Clean build
flutter clean
flutter pub get

# Build release APK
flutter build apk --release

# Output location:
# app/admin_app/build/app/outputs/flutter-apk/app-release.apk
```

**Size:** ~50-80 MB

### 3.3 Build iOS Release IPA

```bash
cd app/admin_app

# Build release IPA
flutter build ipa --release

# Output location:
# app/admin_app/build/ios/ipa/admin_app.ipa
```

### 3.4 Test Release Build

```bash
# Install on device/emulator
flutter install --release

# Test:
# 1. Login with admin credentials
# 2. Navigate through all 4 screens
# 3. Test API calls (Users, Deals, Notifications)
# 4. Verify permission system works
# 5. Test permission denied screens
```

---

## Phase 4: App Store Submission (1-2 hours)

### 4.1 Android Play Store

**Prerequisites:**
- Google Play Developer account ($25 one-time)
- Signed APK (generated in Phase 3.2)
- App icon (1024x1024 PNG)
- Screenshots (4-5 screenshots of app)
- App description & privacy policy

**Steps:**
```
1. Go to https://play.google.com/console
2. Create new app: "DealHunter Admin"
3. Fill app details (name, description, category)
4. Upload signed APK
5. Add screenshots & graphics
6. Set content rating & privacy policy
7. Add pricing ($0 - free)
8. Submit for review (7-10 days)
```

### 4.2 iOS App Store

**Prerequisites:**
- Apple Developer account ($99/year)
- Signed IPA (generated in Phase 3.3)
- App icon (1024x1024 PNG)
- Screenshots (minimum 2 sets for different devices)
- App description & privacy policy
- Certificate, provisioning profile

**Steps:**
```
1. Go to https://appstoreconnect.apple.com
2. Create new app: "DealHunter Admin"
3. Fill app details
4. Upload signed IPA
5. Add screenshots & marketing info
6. Set pricing & availability
7. Submit for review (1-3 days)
```

---

## Phase 5: Production Monitoring (Ongoing)

### 5.1 Backend Monitoring

**Render Dashboard:**
```
- Monitor service health (CPU, memory, requests)
- View logs for errors
- Set up auto-scaling if needed
- Monitor database usage
```

**Firebase Console:**
```
- Monitor authentication attempts
- Check Firestore read/write quotas
- Review security rules violations
- Monitor real-time database changes
```

### 5.2 Error Tracking

**Option 1: Sentry (Free tier available)**
```
1. Go to https://sentry.io
2. Create organization & project
3. Get DSN
4. Add to server.py:
   import sentry_sdk
   sentry_sdk.init("<YOUR_SENTRY_DSN>")
```

**Option 2: Firebase Crashlytics**
```
Already integrated in Flutter app via Firebase SDK
- Automatic crash reporting
- Performance monitoring
- Real-time alerts
```

### 5.3 Logging

**Enable structured logging in server.py:**
```python
import logging
import json

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

# Log important events
logger.info(f"Admin action: {action} by {user} at {timestamp}")
logger.error(f"Authentication failed: {reason}")
```

---

## Production Checklist

### Before Deployment
- [ ] Firebase project created (dealhunter-admin-prod)
- [ ] Service account created and credentials saved
- [ ] Admin user created in Firebase Auth
- [ ] Firestore database created with 4 collections
- [ ] Security rules deployed and tested
- [ ] Firebase configuration values obtained
- [ ] .env.production file created with credentials
- [ ] Render service created and connected to GitHub
- [ ] Environment variables set on Render
- [ ] server.py deployed to Render
- [ ] All 6 Phase 1 API endpoints tested
- [ ] Firebase config updated in Flutter app
- [ ] Release APK built and tested
- [ ] Release IPA built and tested
- [ ] Play Store developer account created
- [ ] iOS App Store developer account created

### During Deployment
- [ ] Test login flow on real device
- [ ] Test all 4 admin screens
- [ ] Test permission system
- [ ] Test all API endpoints with real data
- [ ] Verify analytics logging
- [ ] Verify error handling
- [ ] Test network timeouts
- [ ] Test offline scenarios

### After Deployment
- [ ] Monitor app crash rates
- [ ] Monitor API response times
- [ ] Monitor authentication failures
- [ ] Monitor Firestore usage
- [ ] Respond to user feedback
- [ ] Monitor app store reviews
- [ ] Plan Phase 5 (User Dashboard)

---

## Critical Files Checklist

### Flutter App
- ✅ `app/admin_app/lib/main.dart` - Entry point
- ✅ `app/admin_app/lib/config/firebase_config.dart` - Config (UPDATE WITH REAL VALUES)
- ✅ `app/admin_app/lib/config/router.dart` - Navigation
- ✅ `app/admin_app/lib/screens/auth/admin_login_screen.dart` - Login
- ✅ `app/admin_app/lib/screens/dashboard/dashboard_screen.dart` - Dashboard
- ✅ `app/admin_app/lib/screens/users/users_list_screen.dart` - Users
- ✅ `app/admin_app/lib/screens/deals/deals_list_screen.dart` - Deals
- ✅ `app/admin_app/lib/screens/team/team_screen.dart` - Team
- ✅ `app/admin_app/lib/screens/notifications/notifications_screen.dart` - Notifications
- ✅ `app/admin_app/lib/models/` - All models
- ✅ `app/admin_app/lib/providers/` - All providers
- ✅ `app/admin_app/lib/services/permission_service.dart` - RBAC

### Backend
- ✅ `server.py` - All endpoints implemented
- ✅ `.env.production` - Environment config (UPDATE WITH REAL VALUES)
- ✅ `requirements.txt` - All dependencies

### Documentation
- ✅ `FIREBASE_SETUP_QUICK_START.md` - Firebase setup guide
- ✅ `FIREBASE_SETUP_GUIDE.md` - Detailed Firebase guide
- ✅ `API_ENDPOINTS.md` - API documentation
- ✅ `PRODUCTION_DEPLOYMENT.md` - This file

---

## Troubleshooting

### Firebase Auth Errors
**"Authentication error" on login:**
- Verify admin user exists in Firebase Console > Authentication > Users
- Check email matches exactly (case-sensitive)
- Verify password is correct
- Check Firebase SDK is initialized in main.dart

### API Connection Errors
**"API Request Failed":**
- Verify Render service is running (check dashboard)
- Verify API base URL is correct: `https://dealhunter-scraper.onrender.com/api/v1`
- Check network connectivity
- Verify Firebase credentials are set on Render
- Check Render logs for errors

### Firestore Security Rules Errors
**"Permission denied" when accessing collections:**
- Verify admin user is in admin_users collection
- Verify security rules are published
- Check rules syntax for errors
- Verify request includes valid Firebase ID token

### Build Errors
**Flutter build fails:**
```bash
flutter clean
flutter pub get
flutter pub upgrade
flutter build apk --release  # or flutter build ipa --release
```

---

## Support

For issues:
1. Check Render logs: Dashboard > Your Service > Logs
2. Check Firebase Console: Firestore > Logs
3. Check Flutter console output
4. Enable debug logging:
   ```bash
   flutter run --verbose
   ```

---

## Next Steps After Launch

### Phase 5: User Dashboard (3-4 weeks)
- User-facing dashboard (home, membership, groups, referrals)
- Tier management system
- Referral system implementation
- Group sharing features
- Stripe payment integration

### Phase 6: Advanced Features (TBD)
- Real-time WebSocket updates
- Advanced analytics
- Bulk operations
- Custom reports

---

**Status:** 🟢 READY FOR PRODUCTION DEPLOYMENT  
**Last Updated:** 2026-04-16  
**Version:** 1.0.0

Ready to proceed with Phase 1 deployment? Start with Firebase setup (Phase 1 above).
