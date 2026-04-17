# APK Build Guide - DealHunter Admin App

**Status:** Production Ready  
**Version:** 1.0.0  
**Date:** 2026-04-17

---

## Overview

Complete guide to build release APK for Android deployment. 

**Estimated Time:** 10-20 minutes (after dependencies resolve)

---

## Prerequisites

✅ **Already Completed:**
- Flutter SDK installed
- Firebase configured
- Backend deployed
- Code committed
- Firebase credentials in firebase_config.dart

---

## Build Instructions

### Step 1: Navigate to Project Directory

```bash
cd D:\Python\Panadas\dealhunter\app\admin_app
```

**Verify you're in the correct location:**
```
D:\Python\Panadas\dealhunter\app\admin_app>
```

### Step 2: Clean Build (Important!)

```bash
flutter clean
```

**What it does:**
- Removes previous build artifacts
- Clears cache
- Ensures fresh build

**Wait for completion.**

### Step 3: Get Dependencies

```bash
flutter pub get
```

**What it does:**
- Downloads all package dependencies
- Updates pubspec.lock
- Prepares for build

**Note:** This might take a few minutes. Be patient.

### Step 4: Build Release APK

```bash
flutter build apk --release
```

**What happens:**
1. Builds Flutter framework
2. Compiles Dart code
3. Generates APK file
4. Signs with default key
5. Optimizes for release

**Estimated time:** 10-15 minutes

**Expected output:**
```
Building flutter tool...
Building APK...
✓ Built build/app/outputs/flutter-apk/app-release.apk (XX.X MB)
```

### Step 5: Verify APK Created

```bash
dir build\app\outputs\flutter-apk\
```

**You should see:**
- `app-release.apk` (50-80 MB)

---

## APK Details

### File Information
- **Location:** `build/app/outputs/flutter-apk/app-release.apk`
- **Size:** ~50-80 MB
- **Format:** Release (optimized, signed)
- **Signing:** Debug key (for testing)

### What's Included
- ✅ Flutter framework (optimized)
- ✅ Dart code (compiled and minified)
- ✅ Firebase configuration
- ✅ All screens (6 screens)
- ✅ All models (4 models)
- ✅ All providers (4 providers)
- ✅ All services (RBAC system)
- ✅ Material Design 3 theme
- ✅ All dependencies

### What's NOT Included
- ❌ Debuggable code
- ❌ Development symbols
- ❌ Test files

---

## Install APK on Device

### Option A: Connect Android Device via USB

```bash
flutter install build/app/outputs/flutter-apk/app-release.apk
```

**Or:**

```bash
adb install build/app/outputs/flutter-apk/app-release.apk
```

### Option B: Transfer to Device

1. Copy APK to device via USB
2. Open file manager on device
3. Tap APK to install
4. Grant permissions

### Option C: Email/Download

1. Email APK to yourself
2. Download on Android device
3. Open to install

---

## Test on Device

### Initial Launch
1. **Tap app icon** to open
2. **See login screen**
3. **Enter credentials:**
   - Email: `admin@example.com`
   - Password: (your Firebase password)
4. **Tap Login**

### Verify Login Works
- ✅ Dashboard should load
- ✅ See welcome message
- ✅ See navigation cards (Users, Deals, Notifications)
- ✅ See admin info

### Test Screens
1. **Users Screen**
   - Should load list of users
   - Search should work
   - Edit/delete should work

2. **Deals Screen**
   - Should load list of deals
   - Filter should work
   - Toggle visibility/featured should work

3. **Notifications Screen**
   - Compose tab should work
   - Send button functional

4. **Team Screen**
   - Should show (Owner only)
   - Or show "Owner Only" message

### Verify API Connection
- ✅ Users data loads from API
- ✅ Deals data loads from API
- ✅ No network errors
- ✅ API responds in < 2 seconds

---

## Troubleshooting

### "flutter command not found"
**Solution:** Set Flutter in PATH
```bash
set PATH=D:\Python\Panadas\dealhunter\app\flutter\flutter\bin;%PATH%
```

Then retry build.

### "Resolving dependencies" takes forever
**Solution:** 
- Wait longer (can take 10+ minutes on slow networks)
- Or try: `flutter pub get --offline`
- Or clear pub cache: `flutter pub cache repair`

### APK build fails with error
**Solution:**
1. Run `flutter clean`
2. Run `flutter pub get`
3. Try `flutter build apk --release` again
4. Check the full error message

### "AAPT2 error"
**Solution:**
```bash
flutter clean
flutter pub upgrade
flutter build apk --release
```

### App crashes on launch
**Check:**
- ✅ Firebase credentials are correct
- ✅ Backend is running (https://dealhunter-scraper-1.onrender.com)
- ✅ Firestore is accessible
- ✅ Admin user exists

**Check logs:**
```bash
flutter logs
```

---

## Build Variants

### Debug Build (for testing)
```bash
flutter build apk --debug
```
- Larger file size
- Debuggable
- Slower performance
- For development only

### Release Build (for production)
```bash
flutter build apk --release
```
- Optimized size
- Not debuggable
- Full performance
- **USE THIS FOR APP STORE**

### Split Per ABI (smaller downloads)
```bash
flutter build apk --release --split-per-abi
```
Creates separate APKs:
- app-armeabi-v7a-release.apk
- app-arm64-v8a-release.apk
- app-x86-release.apk
- app-x86_64-release.apk

**Recommended for Play Store** (users download smaller file for their device)

---

## Next Steps After Build

### For Testing
1. Install APK on Android device
2. Test login and all screens
3. Verify API connection works
4. Check no errors in logs

### For Play Store Submission
1. Sign APK with production key
2. Prepare store listing (description, screenshots)
3. Upload to Play Store Console
4. Submit for review

**See:** APP_STORE_SUBMISSION_GUIDE.md

---

## File Output Summary

After successful build, you'll have:

```
build/
└── app/
    └── outputs/
        └── flutter-apk/
            ├── app-release.apk (✅ Use this)
            ├── app-release.apk.sha1
            └── output-metadata.json
```

---

## Build Process Timeline

| Step | Duration | Status |
|------|----------|--------|
| flutter clean | 1-2 min | Quick |
| flutter pub get | 5-10 min | Network-dependent |
| flutter build apk | 10-15 min | Build process |
| **Total** | **15-25 min** | Depends on network |

---

## Success Criteria

✅ Build completes with no errors  
✅ APK file created (50-80 MB)  
✅ APK installs on device  
✅ App launches without crashing  
✅ Login screen appears  
✅ Can login with admin credentials  
✅ Dashboard loads with data  
✅ All screens accessible  
✅ No console errors  
✅ API calls succeed  

---

## Advanced Options

### Build with Specific Dart Version
```bash
flutter build apk --release --dart-obfuscation
```

### Build with Verbose Output
```bash
flutter build apk --release -v
```

Shows detailed build logs for debugging.

### Skip Gradle Build
```bash
flutter build apk --release --no-pub
```

Skips pub upgrade (if already done).

---

## Security Notes

### Debug Key (Current)
- Uses Flutter's default debug key
- OK for testing
- NOT for production Play Store

### Production Key (Required for Play Store)
You'll need to create a signing key:
```bash
keytool -genkey -v -keystore ~/release-keystore.jks -keyalg RSA -keysize 2048 -validity 10000 -alias upload
```

Then sign APK for production upload.

**See:** APP_STORE_SUBMISSION_GUIDE.md for full signing instructions

---

## Common Issues & Solutions

| Issue | Cause | Solution |
|-------|-------|----------|
| "flutter not found" | Not in PATH | Set PATH to flutter/bin |
| "Resolving dependencies..." (slow) | Network issue | Wait or use `--offline` flag |
| APK build fails | Missing dependencies | Run `flutter pub get` |
| App won't launch | Firebase error | Check firebase_config.dart |
| Blank screen on startup | API not responding | Check backend is running |
| Login fails | Wrong credentials | Verify admin user in Firebase |
| Permission denied | File access | Run as Administrator |

---

## What to Do If Build Fails

1. **Read the error message** - it usually tells you what's wrong
2. **Try `flutter clean` first** - solves most issues
3. **Check Flutter version:** `flutter --version`
4. **Check device connectivity** - USB connection
5. **Try on emulator** - different device, same app
6. **Check logs:** `flutter logs`

---

## Next Phase: App Store Submission

Once APK is built and tested:

1. **For Play Store:**
   - See: APP_STORE_SUBMISSION_GUIDE.md
   - Create Play Store developer account ($25)
   - Prepare screenshots and description
   - Upload signed APK
   - Submit for review (7-10 days)

2. **For App Store (iOS):**
   - Build IPA: `flutter build ipa --release`
   - See: APP_STORE_SUBMISSION_GUIDE.md
   - Create App Store developer account ($99/year)
   - Prepare screenshots and description
   - Upload signed IPA
   - Submit for review (1-3 days)

---

## Status

✅ **Prerequisites Complete**  
✅ **Firebase Configured**  
✅ **Backend Deployed**  
✅ **Code Ready**  
⏳ **APK Build** ← You are here  
⏳ **App Store Submission**  

---

## Questions?

Refer to:
- PRODUCTION_DEPLOYMENT.md - Full deployment guide
- PRODUCTION_DEPLOYED.md - Current status
- API_ENDPOINTS.md - API reference
- FIREBASE_SETUP_GUIDE.md - Firebase setup

---

**Version:** 1.0.0  
**Last Updated:** 2026-04-17  
**Status:** Ready to build

Good luck with your build! 🚀
