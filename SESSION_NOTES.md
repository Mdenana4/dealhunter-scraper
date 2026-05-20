# DealHunter — Full Session Notes

## Overview
Complete record of all work done to get the DealHunter app system operational — CI/CD, mobile APK builds, Firebase admin access, Firestore rules, and database setup.

---

## Architecture

```
User App (Flutter)
  ├── Firebase Auth      → login / JWT token
  ├── Firestore          → user profile, saved deals, membership tier
  ├── Firebase FCM       → push notifications
  └── Cloud Run Server   → deals data (reads from Supabase PostgreSQL)

Admin App (Flutter)
  ├── Firebase Auth      → admin login
  └── Firestore          → all admin data (sources, deals, users, scraper health)

Scraper (Python)
  └── Writes deals → Supabase PostgreSQL → Server reads → App displays
```

**Firebase project:** `dealhunter-admin-prod`
**Supabase project:** `dealhunter-prices` (ID: `rmkaljwjskxihkuvxosc`, region: eu-west-1)
**Backend server:** `https://dealhunter-server-q2rbodm3ta-uc.a.run.app`

---

## 1. CI/CD — Admin APK Build (FIXED ✓)

**File:** `.github/workflows/build.yml`

### Root Causes Fixed
| Error | Fix |
|---|---|
| `Gradle build failed to produce an .apk file` (268s timeout) | Replace `flutter build apk` with `./gradlew assembleRelease` directly |
| `FLUTTER_HOME` env var empty | Use `$FLUTTER_ROOT` (what `subosito/flutter-action@v2` exports) |
| `chmod: cannot access 'gradlew'` | Downloaded `gradlew` + `gradle-wrapper.jar` from Gradle v8.13 GitHub release |
| `ReleaseMinSdkCheck FAILED` | `minSdk 21` → `minSdk 23` |
| Gradle 8.13 warning | `gradle-8.13-bin.zip` → `gradle-8.14-bin.zip` |
| Kotlin 2.0.0 detected instead of 2.2.20 | Added `org.jetbrains.kotlin.android version "2.2.20" apply false` to settings.gradle |

### Key Build Config — `app/admin_app/android/app/build.gradle`
```groovy
plugins {
    id "com.android.application"
    id "dev.flutter.flutter-gradle-plugin"
    id "com.google.gms.google-services"
}
android {
    namespace "com.dealhunter.admin"
    compileSdk 35
    defaultConfig {
        applicationId "com.dealhunter.admin"
        minSdk 23
        targetSdk 35
        multiDexEnabled true
    }
    compileOptions {
        sourceCompatibility JavaVersion.VERSION_17
        targetCompatibility JavaVersion.VERSION_17
    }
}
```

### Workflow Build Step
```yaml
- name: Create local.properties
  run: |
    echo "flutter.sdk=$FLUTTER_ROOT" > app/admin_app/android/local.properties
    echo "sdk.dir=$ANDROID_SDK_ROOT"  >> app/admin_app/android/local.properties

- name: Build APK
  run: |
    cd app/admin_app/android
    chmod +x gradlew
    ./gradlew assembleRelease
```

---

## 2. CI/CD — User APK Build (FIXED ✓)

**File:** `.github/workflows/build-user-app.yml`

### Root Causes Fixed
| Error | Fix |
|---|---|
| `checkReleaseAarMetadata FAILED` | `compileSdk 35` → `compileSdk 36`, added `ndkVersion "28.2.13676358"` |
| `processReleaseMainManifest FAILED` | `minSdk 23` → `minSdk 24` (shared_preferences_android requirement) |
| APK not found after successful build | Broadened find path to `app/user_app/**` + added `if: always()` to Find/Upload steps |

### Key Build Config — `app/user_app/android/app/build.gradle`
```groovy
android {
    namespace "com.dealhunter.app"
    compileSdk 36
    ndkVersion "28.2.13676358"
    defaultConfig {
        applicationId "com.dealhunter.app"
        minSdk 24
        targetSdk 35
    }
    compileOptions {
        sourceCompatibility JavaVersion.VERSION_17
        targetCompatibility JavaVersion.VERSION_17
    }
}
```

---

## 3. Scraper Fixes

### Jumia Price History Discovery (FIXED ✓)
**File:** `price_history_system.py` line ~665

**Problem:** Was only discovering discounted products (URL had `?sort=discountPercent&type=lowest-price` filter)
**Fix:** Removed the filter so ALL products are tracked for price history
```python
# Before
url = f"https://{domain}/{kw}?sort=discountPercent&type=lowest-price"
# After
url = f"https://{domain}/{kw}"  # collect all prices for history
```

### Amazon Saudi Re-enabled (FIXED ✓)
**File:** `scraper.py`

**Problem:** Suspended due to scraper.do geo limitation
**Fix:** Now uses RapidAPI directly (supports SA natively, no proxy needed)
```python
def scrape_amazon_sa():
    return _scrape_amazon_via_api(
        country="SA",
        marketplace_country="amazon_sa",
        site_display="Amazon Saudi",
        currency="SAR",
    )
```

---

## 4. Firebase Admin Login (FIXED ✓)

### The Login Flow
The admin app does TWO checks:
1. Firebase Authentication — valid email + password
2. Firestore `admin_users` — document ID must match `request.auth.token.email`

### Admin Credentials
| | |
|---|---|
| **Email** | `mansy4@gmail.com` |
| **Password** | `Admin@123` |

### Firestore Documents Created
- `admin_users/mansy4@gmail.com` — email-keyed (required by deployed rules)
- `admin_users/tyNnlDRvsRWYbeAli4KCxhd2h8L2` — UID-keyed (backup)

---

## 5. Firestore Security Rules (ACTION REQUIRED ⚠️)

### Problem
The deployed rules only cover `users`, `deals`, `notifications`, `admin_users`. All other collections (`sources`, `scraper_health`, `notification_log`, etc.) are blocked by a catch-all deny rule.

### Fix
Go to **Firebase Console → dealhunter-admin-prod → Firestore → Rules tab → delete everything → paste below → click Publish:**

```javascript
rules_version = '2';
service cloud.firestore {
  match /databases/{database}/documents {
    function isAdmin() {
      return request.auth != null &&
             exists(/databases/$(database)/documents/admin_users/$(request.auth.token.email));
    }
    function isOwner() {
      let admin = get(/databases/$(database)/documents/admin_users/$(request.auth.token.email));
      return admin != null && admin.data.role == 'owner';
    }
    match /admin_users/{email} { allow read: if isAdmin(); allow write: if isOwner(); }
    match /users/{uid} { allow read, write: if isAdmin(); }
    match /deals/{id} { allow read, write: if isAdmin(); }
    match /sources/{id} { allow read, write: if isAdmin(); }
    match /scraper_health/{id} { allow read, write: if isAdmin(); }
    match /notification_log/{id} { allow read, write: if isAdmin(); }
    match /notifications/{id} { allow read, write: if isAdmin(); }
    match /user_groups/{id} { allow read, write: if isAdmin(); }
    match /scraper_control/{id} { allow read, write: if isAdmin(); }
    match /analytics_events/{id} { allow read: if isAdmin(); allow write: if false; }
    match /price_change_events/{id} { allow read: if isAdmin(); allow write: if false; }
    match /products/{id} { allow read: if isAdmin(); allow write: if false; }
    match /{document=**} { allow read, write: if false; }
  }
}
```

---

## 6. User App "No Deals Found" (PENDING ⚠️)

### Root Cause
Supabase database is empty — the scraper has never run against production.

### What needs to happen
1. Get Supabase `DATABASE_URL` (with real password) — reset in Supabase → Project Settings → Database
2. Get `RAPIDAPI_KEY` — from RapidAPI dashboard
3. Get `SCRAPERDO_API_KEY` (optional — for Jumia/Noon)
4. Run scraper locally or trigger Cloud Run job

### Scraper Schedule (when deployed)
- Deal scraper: Cloud Run Job, every 6 hours (`0 */6 * * *`)
- Price tracker: Cloud Run Job, every 8 hours (`0 */8 * * *`)

### RapidAPI Key (provided)
`3041e7da00be45828a61c399c063750ba0cb05219d0`

---

## 7. System Overview

### System 1 — Price History + Fake Deal Detection
- 24h background cycle: discovery → snapshots → analytics
- Collects price history for ALL products (not just discounted ones)
- Detects fake discounts by comparing current price vs 30-day history
- Jumia: collects all categories, no discount filter

### System 2 — Deal Collection (≥40% off)
- Sources: Amazon Egypt, Amazon Saudi, Noon Egypt, Jumia Egypt
- Amazon: RapidAPI (no proxy needed)
- Jumia/Noon: scraper.do proxy
- Minimum discount threshold: 40%

### Push Notifications
- FCM topic-based: `tier_vip`, `tier_premium`, `tier_free`
- Per-user topics for price alerts
- Admin app can send manual broadcasts

### Deal Categories
Electronics, Fashion, Home & Kitchen, Beauty, Sports, Books, Toys, Automotive, Health, Food & Grocery

---

## 8. Remaining TODO

- [ ] Paste new Firestore rules in Firebase Console (fixes admin app scraper_health error)
- [ ] Get Supabase password → reset in Supabase → Project Settings → Database → Reset password
- [ ] Run scraper with DATABASE_URL + RAPIDAPI_KEY to populate deals
- [ ] Verify Cloud Run server env vars are set (DATABASE_URL, FIREBASE_CREDENTIALS_JSON)
- [ ] Set up GitHub Secrets for automated scraper deployment

---

## Key Files Reference

| File | Purpose |
|---|---|
| `scraper.py` | Main deal scraper (Amazon, Noon, Jumia) |
| `price_history_system.py` | Price history tracking + fake deal detection |
| `server_cloudrun.py` | Backend API server (Flask, reads Supabase) |
| `app/admin_app/` | Flutter admin app |
| `app/user_app/` | Flutter user app |
| `.github/workflows/build.yml` | Admin APK CI |
| `.github/workflows/build-user-app.yml` | User APK CI |
| `firestore.rules` | Firestore security rules (local copy) |
| `firebase.json` | Firebase project config |
