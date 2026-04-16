# Firebase Setup Guide - DealHunter Admin App

Complete step-by-step guide to setup Firebase for the DealHunter Admin App.

---

## 📋 Prerequisites

- Google Cloud account
- Firebase project created
- Render account (for backend deployment)
- Flutter environment setup

---

## 🔧 Step 1: Create Firebase Project

### 1.1 Go to Firebase Console
1. Visit https://console.firebase.google.com/
2. Sign in with your Google account
3. Click "Create a project"

### 1.2 Configure Project
1. **Project Name:** `dealhunter-admin`
2. **Analytics:** Enable (optional)
3. Click "Create project"
4. Wait for project to be created

### 1.3 Add App to Firebase
1. Click the Android icon (or iOS for both)
2. **Package Name:** `com.dealhunter.admin`
3. **App nickname:** DealHunter Admin
4. Click "Register app"
5. Download `google-services.json` (Android)
6. Place in `android/app/` directory

---

## 🔐 Step 2: Setup Authentication

### 2.1 Enable Email/Password Authentication
1. Go to **Authentication** > **Sign-in method**
2. Click **Email/Password**
3. Enable both "Email/Password" and "Email link (passwordless sign-in)"
4. Click **Save**

### 2.2 Create First Admin User
1. Go to **Authentication** > **Users**
2. Click **Create user**
3. **Email:** `admin@example.com` (or your email)
4. **Password:** Set a strong password
5. Click **Create**

---

## 📊 Step 3: Setup Firestore Database

### 3.1 Create Firestore Database
1. Go to **Firestore Database**
2. Click **Create database**
3. **Location:** Choose your region (e.g., us-central1)
4. **Security rules:** Select "Start in production mode"
5. Click **Create**

### 3.2 Create Collections

#### Collection 1: `admin_users`
```
Collection: admin_users
Document ID: {email_address}

Fields:
├── email (string) - Admin email
├── name (string) - Admin full name
├── role (string) - "owner" | "editor" | "viewer"
├── permissions (array) - ["sources", "deals", "users", ...]
├── status (string) - "active" | "inactive"
├── added_at (timestamp) - When added
├── added_by (string) - Email of admin who added
└── last_login (timestamp) - Last login time
```

**Create first admin:**
1. Click **+ Add collection**
2. Name: `admin_users`
3. Click **Next**
4. Document ID: `admin@example.com`
5. Add fields:
   - `email`: admin@example.com
   - `name`: Admin Name
   - `role`: owner
   - `permissions`: ["sources", "deals", "users", "notifications", "checker", "competitors", "scraper_control"]
   - `status`: active
   - `added_at`: Now
   - `added_by`: system
6. Click **Save**

#### Collection 2: `users`
```
Collection: users
Document ID: Auto-generated

Fields:
├── email (string) - User email
├── name (string) - User name
├── tier (string) - "free" | "trial" | "premium" | "vip"
├── daily_deal_limit (number) - Max deals per day
├── registered_at (timestamp) - Registration date
├── last_login (timestamp) - Last login
├── is_active (boolean) - User status
├── group_name (string) - Group membership
└── stripe_customer_id (string) - Stripe ID
```

**Create one test user:**
1. Click **+ Add collection**
2. Name: `users`
3. Click **Next**
4. Document ID: Auto-generate
5. Add test user data
6. Click **Save**

#### Collection 3: `deals`
```
Collection: deals
Document ID: Auto-generated

Fields:
├── title (string) - Deal title
├── source (string) - amazon | jumia | noon
├── current_price (number) - Current price
├── original_price (number) - Original price
├── discount_percent (number) - Discount %
├── image_url (string) - Product image
├── product_url (string) - Product link
├── status (string) - active | hidden | expired
├── verdict (string) - genuine | suspicious | fake
├── featured (boolean) - Featured status
├── hidden (boolean) - Visibility
├── views (number) - View count
├── rating (number) - Product rating
├── reviews (number) - Review count
├── added_at (timestamp) - Added date
└── updated_at (timestamp) - Last update
```

**Create one test deal:**
1. Click **+ Add collection**
2. Name: `deals`
3. Click **Next**
4. Document ID: Auto-generate
5. Add test deal data
6. Click **Save**

#### Collection 4: `notifications`
```
Collection: notifications
Document ID: Auto-generated

Fields:
├── title (string) - Notification title
├── message (string) - Notification message
├── target_type (string) - all | tier | group
├── target_tier (string) - Premium | VIP (if tier)
├── target_group (string) - Group name (if group)
├── sent_count (number) - How many sent
├── sent_at (timestamp) - When sent
└── sent_by (string) - Admin email
```

**Create collection (empty for now):**
1. Click **+ Add collection**
2. Name: `notifications`
3. Click **Next**
4. Click **Save** (can add documents later)

---

## 🔒 Step 4: Setup Security Rules

### 4.1 Update Firestore Security Rules

1. Go to **Firestore Database** > **Rules**
2. Replace default rules with:

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

3. Click **Publish**

---

## 🔗 Step 5: Get Firebase Configuration

### 5.1 Get Configuration Values

1. Go to **Project Settings** (gear icon)
2. Click **Your apps** section
3. Select your app
4. Copy the following values:

```
API Key: AIzaSy...
App ID: 1:123456789:android:abc...
Messaging Sender ID: 123456789
Project ID: dealhunter-admin
Auth Domain: dealhunter-admin.firebaseapp.com
Database URL: https://dealhunter-admin.firebaseio.com
Storage Bucket: dealhunter-admin.appspot.com
```

### 5.2 Update Firebase Config

1. Open `app/admin_app/lib/config/firebase_config.dart`
2. Replace placeholder values with your actual values
3. Update `main.dart` Firebase initialization

---

## 🌐 Step 6: Deploy Backend to Render

### 6.1 Update Server Configuration

1. Open `server.py`
2. Verify Firebase initialization code is correct
3. Update environment variables on Render:
   - `FIREBASE_CREDENTIALS_JSON` - Your Firebase service account JSON

### 6.2 Deploy to Render

```bash
# Commit changes
git add server.py
git commit -m "Add Phase 1 API endpoints"

# Push to Render (auto-deploys)
git push
```

### 6.3 Verify Deployment

Test endpoints:
```bash
# Get all users
curl -H "Authorization: Bearer <token>" \
  https://dealhunter-scraper.onrender.com/api/v1/admin/users

# Get all deals
curl -H "Authorization: Bearer <token>" \
  https://dealhunter-scraper.onrender.com/api/v1/admin/deals

# Get notifications
curl -H "Authorization: Bearer <token>" \
  https://dealhunter-scraper.onrender.com/api/v1/admin/notifications
```

---

## 📱 Step 7: Configure Flutter App

### 7.1 Update Firebase Config

File: `app/admin_app/lib/config/firebase_config.dart`

Replace all `YOUR_*` values with actual Firebase config values.

### 7.2 Update API Base URL

File: `app/admin_app/lib/providers/*.dart`

Verify base URL is correct:
```
baseUrl: 'https://dealhunter-scraper.onrender.com/api/v1'
```

### 7.3 Add Environment Variables

Create `.env` file in project root (optional):
```
FIREBASE_API_KEY=AIzaSy...
FIREBASE_APP_ID=1:123456789:android:abc...
API_BASE_URL=https://dealhunter-scraper.onrender.com/api/v1
```

---

## ✅ Step 8: Verify Setup

### 8.1 Check Firebase

- [ ] Firebase project created
- [ ] Authentication enabled
- [ ] First admin user created
- [ ] Firestore database created
- [ ] 4 collections created (admin_users, users, deals, notifications)
- [ ] Security rules deployed
- [ ] Configuration values obtained

### 8.2 Check Backend

- [ ] server.py updated with endpoints
- [ ] Deployed to Render
- [ ] API endpoints tested
- [ ] Authentication working
- [ ] Permission checks working

### 8.3 Check Flutter App

- [ ] Firebase config updated
- [ ] API base URL correct
- [ ] Environment variables set (if using .env)

---

## 🚀 Step 9: Run the App

### 9.1 Install Dependencies

```bash
cd app/admin_app
flutter pub get
```

### 9.2 Run on Device/Emulator

```bash
flutter run
```

### 9.3 Test Login Flow

1. App loads → Should show login screen
2. Enter email: `admin@example.com`
3. Enter password: (the password you set)
4. Click Login → Should navigate to dashboard
5. Should see "Welcome, Admin Name!"
6. Should see navigation cards (Users, Deals, Team, Notifications)

### 9.4 Test Users Screen

1. Click "Users" card
2. Should load all users (test user + any others)
3. Try search functionality
4. Try filter by tier
5. Try edit user
6. Try delete user (with confirmation)

### 9.5 Test Deals Screen

1. Click "Deals" card
2. Should load all deals
3. Try search functionality
4. Try filter by source/status
5. Try edit deal
6. Try toggle visibility
7. Try toggle featured
8. Try set verdict

### 9.6 Test Team Screen (Owner Only)

1. Click "Team" card (should show if Owner)
2. Should show admin list
3. Try add team member
4. Try edit permissions
5. Try remove member

### 9.7 Test Notifications Screen

1. Click "Notifications" card
2. Go to Compose tab
3. Enter title and message
4. Select target type
5. Click Send
6. Go to History tab
7. Should see sent notification

---

## 🐛 Troubleshooting

### "Access Denied" on Login
- Check admin user exists in admin_users collection
- Verify Firestore security rules are correct
- Check Firebase authentication is enabled

### "API Request Failed"
- Verify server.py is deployed on Render
- Check API base URL is correct in providers
- Verify Firebase credentials are correct on server
- Check network connectivity

### "Permission Denied" on screens
- Check admin user has correct role (owner/editor/viewer)
- Verify permissions array in admin_users document
- Check permission checks in PermissionService

### "Firebase Configuration Error"
- Verify Firebase config values are correct
- Check `firebase_config.dart` has actual values
- Verify `main.dart` Firebase initialization matches

---

## 📚 Next Steps

After setup is complete:

1. ✅ Test all screens thoroughly
2. ✅ Test all API endpoints
3. ✅ Test permission system
4. ✅ Test error handling
5. ✅ Verify user experience
6. ✅ Performance testing
7. ✅ Security audit
8. ✅ Deploy to App Store/Play Store

---

## 📞 Support

If you encounter issues:

1. Check Firebase Console for error logs
2. Check Render dashboard for backend logs
3. Check Flutter console for app errors
4. Verify Firestore collection structure
5. Verify security rules are correct
6. Test API endpoints with Postman

---

**Status:** Ready for deployment 🚀  
**Created:** 2026-04-16  
**Version:** 1.0.0
