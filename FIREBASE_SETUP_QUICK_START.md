# Firebase Setup - Quick Start Checklist

Complete Firebase setup in 4 steps. Estimated time: 1-2 hours.

---

## ⏱️ Step 1: Create Firebase Project (10 minutes)

### Actions to Take:
1. ✅ Go to https://console.firebase.google.com/
2. ✅ Click **Create a project**
3. ✅ Project name: `dealhunter-admin`
4. ✅ Enable Analytics (optional)
5. ✅ Click **Create project** and wait
6. ✅ Once created, click gear icon (Settings) > **Your apps**
7. ✅ Click Android icon or iOS icon
   - Package Name: `com.dealhunter.admin`
   - App nickname: `DealHunter Admin`
8. ✅ Click **Register app**
9. ✅ Download `google-services.json` (Android)
10. ✅ Place in `android/app/` directory

**Status:** ⬜ Ready to proceed →

---

## 🔐 Step 2: Setup Authentication (5 minutes)

### Actions to Take:
1. ✅ Go to **Authentication** > **Sign-in method**
2. ✅ Click **Email/Password**
3. ✅ Enable "Email/Password" 
4. ✅ Enable "Email link (passwordless)"
5. ✅ Click **Save**

### Create First Admin User:
1. ✅ Go to **Authentication** > **Users**
2. ✅ Click **Create user**
3. ✅ Email: `admin@example.com` (or YOUR email)
4. ✅ Password: (set a strong password - SAVE THIS!)
5. ✅ Click **Create**

**⚠️ IMPORTANT: Save your admin credentials!**
```
Email: admin@example.com
Password: [YOUR PASSWORD HERE]
```

**Status:** ⬜ Ready to proceed →

---

## 📊 Step 3: Create Firestore Database (15 minutes)

### 3.1: Create Database
1. ✅ Go to **Firestore Database**
2. ✅ Click **Create database**
3. ✅ Location: **us-central1** (or your region)
4. ✅ Security rules: **Start in production mode**
5. ✅ Click **Create**
6. ✅ Wait for database to be created

### 3.2: Create Collections

**Collection 1: `admin_users`**

```
Steps:
1. Click "+" > Start collection
2. Collection ID: admin_users
3. Document ID: admin@example.com
4. Add these fields:

   email: admin@example.com
   name: Admin Name
   role: owner
   permissions: ["sources","deals","users","notifications","checker","competitors","scraper_control"]
   status: active
   added_at: [TODAY'S DATE]
   added_by: system

5. Click Save
```

**Collection 2: `users`**

```
Steps:
1. Click "+" > Start collection
2. Collection ID: users
3. Document ID: [Auto-generate]
4. Add these test fields:

   email: testuser@example.com
   name: Test User
   tier: premium
   daily_deal_limit: 500
   registered_at: [TODAY'S DATE]
   is_active: true

5. Click Save
```

**Collection 3: `deals`**

```
Steps:
1. Click "+" > Start collection
2. Collection ID: deals
3. Document ID: [Auto-generate]
4. Add these test fields:

   title: Sample Deal
   source: amazon
   current_price: 99.99
   original_price: 149.99
   discount_percent: 33
   status: active
   verdict: genuine
   featured: false
   hidden: false
   views: 0
   added_at: [TODAY'S DATE]

5. Click Save
```

**Collection 4: `notifications`**

```
Steps:
1. Click "+" > Start collection
2. Collection ID: notifications
3. Click Create (empty is fine, can add later)
```

**Status:** ⬜ Ready to proceed →

---

## 🔒 Step 4: Deploy Security Rules (10 minutes)

### Actions to Take:
1. ✅ Go to **Firestore Database** > **Rules** tab
2. ✅ Delete existing rules
3. ✅ Copy and paste these rules:

```javascript
rules_version = '2';
service cloud.firestore {
  match /databases/{database}/documents {
    
    // Helper function to check if user is authenticated admin
    function isAdmin() {
      return request.auth != null && 
             exists(/databases/$(database)/documents/admin_users/$(request.auth.token.email));
    }
    
    function hasPermission(perm) {
      let admin = get(/databases/$(database)/documents/admin_users/$(request.auth.token.email));
      return admin != null && admin.data.permissions.hasAll([perm]);
    }
    
    function isOwner() {
      let admin = get(/databases/$(database)/documents/admin_users/$(request.auth.token.email));
      return admin != null && admin.data.role == 'owner';
    }
    
    // Admin users collection - Owner only
    match /admin_users/{email} {
      allow read: if isAdmin();
      allow write: if isOwner();
    }
    
    // Users collection - Users permission
    match /users/{userId} {
      allow read: if isAdmin();
      allow write: if isAdmin() && (hasPermission('users') || isOwner());
    }
    
    // Deals collection - Deals permission
    match /deals/{dealId} {
      allow read: if isAdmin();
      allow write: if isAdmin() && (hasPermission('deals') || isOwner());
    }
    
    // Notifications collection - Notifications permission
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

4. ✅ Click **Publish**

**Status:** ⬜ Ready to proceed →

---

## 📋 Step 5: Get Firebase Configuration (5 minutes)

### Actions to Take:
1. ✅ Go to **Project Settings** (gear icon at top)
2. ✅ Click **Your apps** section
3. ✅ Click on your app
4. ✅ Copy these values:

**Copy These Values:**
```
API Key:                AIzaSy...
App ID:                 1:123456789:android:abc...
Messaging Sender ID:    123456789
Project ID:             dealhunter-admin
Auth Domain:            dealhunter-admin.firebaseapp.com
Database URL:           https://dealhunter-admin.firebaseio.com
Storage Bucket:         dealhunter-admin.appspot.com
```

**Status:** ⬜ Ready for app config →

---

## 🔗 Step 6: Update Flutter App (15 minutes)

### File: `app/admin_app/lib/config/firebase_config.dart`

Open this file and update:

```dart
class FirebaseConfig {
  static const String apiKey = 'YOUR_API_KEY_HERE';
  static const String appId = 'YOUR_APP_ID_HERE';
  static const String messagingSenderId = 'YOUR_SENDER_ID_HERE';
  static const String projectId = 'YOUR_PROJECT_ID_HERE';
  static const String authDomain = 'YOUR_AUTH_DOMAIN_HERE';
  static const String databaseUrl = 'YOUR_DATABASE_URL_HERE';
  static const String storageBucket = 'YOUR_STORAGE_BUCKET_HERE';
}
```

Replace all `YOUR_*` values with values from Firebase Console.

**Status:** ⬜ Ready to run app →

---

## 📱 Step 7: Test the App (15 minutes)

### Actions to Take:

```bash
# 1. Install dependencies
cd app/admin_app
flutter pub get

# 2. Run app
flutter run

# 3. Login with your admin credentials
# Email: admin@example.com
# Password: [PASSWORD YOU CREATED]

# 4. Test login
# Should see Dashboard screen after login
```

### What to Test:
- [ ] Login with admin credentials
- [ ] See Dashboard with welcome message
- [ ] Click Users → Should load test user
- [ ] Click Deals → Should load test deal
- [ ] Click Team → Should show you as Owner
- [ ] Click Notifications → Should open compose tab

**Status:** ✅ Setup Complete!

---

## ✅ Setup Verification Checklist

Before moving to deployment, verify:

- [ ] Firebase project created
- [ ] Authentication enabled
- [ ] First admin user created
- [ ] Firestore database created
- [ ] 4 collections created (admin_users, users, deals, notifications)
- [ ] Security rules published
- [ ] Configuration values copied
- [ ] Firebase config updated in app
- [ ] App runs without errors
- [ ] Login works with admin credentials
- [ ] Dashboard loads
- [ ] All screens accessible

---

## 🔧 Troubleshooting

### "Cannot find google-services.json"
- Download from Firebase Console
- Place in `android/app/` directory
- Run `flutter clean` then `flutter pub get`

### "Authentication error"
- Verify admin user exists in Firebase Console
- Check email matches exactly
- Verify password is correct
- Check internet connection

### "Firestore rules error"
- Go to Firestore > Rules
- Verify rules are correctly published
- Check no syntax errors in rules

### "App won't compile"
- Run `flutter clean`
- Run `flutter pub get`
- Update Firebase plugins: `flutter pub upgrade`

---

## 📞 Next Steps

Once setup is complete:

1. ✅ Deploy backend to Render
2. ✅ Run full test suite
3. ✅ Build release APK/IPA
4. ✅ Submit to App Stores

---

## 📊 Setup Time Estimate

| Step | Time | Status |
|------|------|--------|
| Create Firebase Project | 10 min | ⬜ |
| Setup Authentication | 5 min | ⬜ |
| Create Firestore DB | 15 min | ⬜ |
| Deploy Security Rules | 10 min | ⬜ |
| Get Configuration | 5 min | ⬜ |
| Update Flutter App | 15 min | ⬜ |
| Test App | 15 min | ⬜ |
| **TOTAL** | **75 min** | ⬜ |

---

**Status:** 🟢 Ready to begin Firebase setup!

Start with **Step 1: Create Firebase Project**
