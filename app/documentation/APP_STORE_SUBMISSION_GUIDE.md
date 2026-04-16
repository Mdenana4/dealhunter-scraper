# DealHunter App Store Submission Guide

**Status:** Ready to Submit  
**Platforms:** iOS (Apple App Store) + Android (Google Play Store)  
**Framework:** Flutter  
**Date:** 2026-04-16

---

## TABLE OF CONTENTS
1. [Pre-Submission Checklist](#pre-submission-checklist)
2. [iOS App Store Submission](#ios-app-store-submission)
3. [Android Google Play Submission](#android-google-play-submission)
4. [App Store Optimization (ASO)](#app-store-optimization-aso)
5. [Post-Submission Monitoring](#post-submission-monitoring)
6. [Troubleshooting](#troubleshooting)

---

## PRE-SUBMISSION CHECKLIST

### Technical Checklist

- [ ] App builds successfully (no errors/warnings)
  ```bash
  flutter build ios --release
  flutter build apk --release
  flutter build appbundle --release
  ```

- [ ] All required screens are complete:
  - [ ] Login/Signup
  - [ ] Home (Deal Feed)
  - [ ] Deal Details
  - [ ] Membership/Upgrade
  - [ ] Groups
  - [ ] Referrals
  - [ ] Notifications
  - [ ] Profile/Settings
  - [ ] Admin App (separate)

- [ ] Firebase configured correctly
  - [ ] Authentication working
  - [ ] Firestore data access working
  - [ ] Push notifications (FCM) enabled
  - [ ] No hardcoded API keys in app code

- [ ] Payment processing working
  - [ ] Stripe integration tested
  - [ ] Test payments successful
  - [ ] Stripe mode switched to LIVE before submission

- [ ] App tested on real devices
  - [ ] iOS 15+ (minimum iOS version)
  - [ ] Android 8+ (minimum Android version)
  - [ ] All features work on real devices
  - [ ] No crashes after 5+ minutes usage

- [ ] Performance optimized
  - [ ] App startup < 2 seconds
  - [ ] Deal feed scrolls smoothly
  - [ ] Images load without lag
  - [ ] API calls have reasonable timeouts
  - [ ] No memory leaks (test with 10+ deals loaded)

- [ ] Privacy & Security
  - [ ] Privacy policy created
  - [ ] Terms of service created
  - [ ] GDPR compliance checked
  - [ ] Data encryption in transit (HTTPS)
  - [ ] No sensitive data hardcoded

- [ ] Localization (if targeting international)
  - [ ] Arabic support (for Egypt)
  - [ ] English support
  - [ ] RTL text layout tested
  - [ ] All strings translated

### App Content Checklist

- [ ] App icons created
  - [ ] 1024x1024 PNG (required)
  - [ ] All app icon sizes (iOS: 29, 40, 60, 76, 83.5, 120, 152, 167, 180 px)
  - [ ] No background transparency for iOS
  - [ ] Branded/professional design

- [ ] Launch screen designed
  - [ ] Not a static image (use Flutter splash screen)
  - [ ] Loading indicator visible
  - [ ] Brand logo/name

- [ ] Screenshots created (minimum 2, maximum 5 per language)
  - [ ] iPhone 6.7" (largest)
  - iPhone 5.5"
  - Show key features
  - Professional quality (1170x2532 for iPhone)
  - Text overlay explaining features

- [ ] Preview video (optional but recommended)
  - [ ] 15-30 seconds
  - [ ] Shows key features in action
  - [ ] No watermarks
  - [ ] 1080p minimum quality

### Account & Legal Checklist

**For iOS (Apple):**
- [ ] Apple Developer Account ($99/year)
- [ ] Apple ID & password
- [ ] Team ID from Apple
- [ ] Privacy policy URL (HTTPS)
- [ ] Terms of service URL (HTTPS)
- [ ] Contact email for support
- [ ] Website URL (optional)

**For Android:**
- [ ] Google Play Developer Account ($25 one-time)
- [ ] Google account with 2FA enabled
- [ ] Privacy policy URL (HTTPS)
- [ ] Contact email
- [ ] Website URL (optional)
- [ ] Stripe Account for payments

---

## iOS APP STORE SUBMISSION

### Step 1: Prepare iOS Build

**1.1: Update pubspec.yaml**
```yaml
flutter:
  version: 1.0.0+1
```

**1.2: Update Info.plist**

File: `ios/Runner/Info.plist`

```xml
<dict>
  <key>CFBundleName</key>
  <string>DealHunter</string>
  
  <key>CFBundleDisplayName</key>
  <string>DealHunter Egypt</string>
  
  <key>CFBundleIdentifier</key>
  <string>com.dealhunter.egypt</string>
  
  <key>CFBundleVersion</key>
  <string>1</string>
  
  <key>CFBundleShortVersionString</key>
  <string>1.0.0</string>
  
  <key>MinimumOSVersion</key>
  <string>15.0</string>
  
  <key>NSAppTransportSecurity</key>
  <dict>
    <key>NSAllowsArbitraryLoads</key>
    <false/>
  </dict>
  
  <key>NSPhotoLibraryUsageDescription</key>
  <string>Used to share deals and referral codes</string>
  
  <key>NSCameraUsageDescription</key>
  <string>Used for profile picture (optional)</string>
  
  <!-- Firebase APNs key -->
  <key>UIApplicationSceneManifest</key>
  <dict>
    <key>UISceneConfigurations</key>
    <dict/>
  </dict>
</dict>
```

**1.3: Update Xcode Project**

Open in Xcode:
```bash
open ios/Runner.xcworkspace
```

1. Select Runner → Build Settings
2. Set "Minimum Deployment Target" to 15.0
3. Check "Valid Architectures": arm64
4. Ensure "Code Signing" certificates are configured

**1.4: Build for Release**

```bash
flutter clean
flutter pub get
flutter build ios --release
```

### Step 2: Create Archive

1. Open Xcode: `ios/Runner.xcworkspace`
2. Select "Runner" → "Any iOS Device (arm64)"
3. Product → Archive
4. Wait for build to complete
5. Organizer window appears → Select archive

### Step 3: Validate & Upload to App Store Connect

**3.1: Prepare Signing**

1. In Archive → Validate App
2. Select signing certificate (Developer Team)
3. Click Validate

**3.2: Upload**

1. In Archive → Distribute App
2. Select "App Store Connect"
3. Select "Upload"
4. Choose team
5. Automatically manage signing
6. Upload begins

### Step 4: Configure App Store Connect

1. Go to **appstoreconnect.apple.com**
2. Login with Apple ID
3. Select "My Apps" → "DealHunter"

**4.1: General Information**

- [ ] App name: "DealHunter Egypt"
- [ ] Subtitle: "Find the Best Deals"
- [ ] Category: Shopping
- [ ] Content Rating: Complete questionnaire
- [ ] Age Rating: 4+

**4.2: Pricing & Availability**

- [ ] Price tier: Free
- [ ] Availability: Add countries (at least Egypt)
- [ ] Release date: Immediate or custom

**4.3: App Information**

- [ ] Privacy Policy URL: (HTTPS URL to your privacy policy)
- [ ] Support URL: (Support email or website)
- [ ] Marketing URL: (Your website or marketing page)

**4.4: Privacy**

- [ ] Data Collection: Indicate what data is collected
  - [ ] User ID
  - [ ] Email Address
  - [ ] Device Model
  - [ ] Device ID (IDFA if using ads)
- [ ] Data Usage: "Used to personalize content and improve service"
- [ ] Health & Fitness: No (unless applicable)
- [ ] Financial Info: Yes (payment processing)

**4.5: Screenshots (Required)**

- [ ] Upload 2-5 screenshots per device size
- [ ] Show key features:
  1. Deal browsing
  2. Membership/Upgrade screen
  3. Notification/Groups
  4. Settings/Profile
  5. (Optional) Admin app features

**Screenshot Specifications:**
```
iPhone (5.5-inch):  1242 x 2208 pixels
iPhone (6.5-inch):  1242 x 2688 pixels
iPad Pro:           2048 x 2732 pixels
```

**4.6: App Description**

```
Title: DealHunter Egypt - Best Shopping Deals

Description:
DealHunter is your ultimate deal finder for Egyptian e-commerce platforms. 
Discover the hottest deals from Amazon Egypt, Jumia, Noon, and more - 
all in one app.

Key Features:
• Browse deals from multiple Egyptian retailers
• Create groups and share deals with friends
• Earn rewards through our referral program
• Get instant notifications about flash sales
• Join our membership program for exclusive deals
• Advanced filtering and personalized recommendations

Join thousands of smart shoppers saving money every day!

Support: support@dealhunter.egypt
Website: www.dealhunter.egypt
```

**4.7: Keywords**

Choose 5-10 relevant keywords:
- deals
- shopping
- egypt
- discount
- bargains
- save money
- e-commerce
- amazon egypt
- jumia
- noon

**4.8: Build**

- [ ] Wait for build to process (usually 10-20 minutes)
- [ ] Build status: "Ready to Submit for Review"

### Step 5: Prepare for Review

**5.1: Review Information**

- [ ] Contact Information: Your name, email, phone
- [ ] Demo Account (if requires login):
  - Username: `demo@dealhunter.test`
  - Password: `DemoPassword123!`
  - Note: "No special setup required for review"

**5.2: Notes for Reviewer**

```
DealHunter is a deal aggregator app for Egyptian e-commerce platforms. 
Users can browse deals, create groups, earn referral rewards, and 
upgrade their membership for better deals.

Key Features Demonstrated:
1. Browsing deals with filters by source and category
2. User authentication and profile setup
3. Membership tiers and payment processing (Stripe)
4. Group creation and sharing
5. Notifications for new deals
6. Referral program

No special setup required. The app works immediately after login 
with demo account.

Legal:
- Privacy Policy: https://www.dealhunter.egypt/privacy
- Terms of Service: https://www.dealhunter.egypt/terms
```

**5.3: Version Release**

- [ ] Release Type: "Automatic"
- [ ] Comments: (Leave empty unless special notes)

### Step 6: Submit for Review

1. Click "Submit for Review"
2. Confirm all information is correct
3. Click "Submit"
4. Status changes to "Waiting for Review"

**Typical Review Timeline:** 1-3 days

### Step 7: Monitor Review Status

1. Check **appstoreconnect.apple.com** regularly
2. Status updates:
   - `Waiting for Review` - In queue
   - `In Review` - Apple is testing
   - `Ready for Sale` - APPROVED ✅
   - `Rejected` - Fix issues and resubmit

3. If Rejected:
   - Read rejection reasons carefully
   - Fix issues
   - Resubmit with updated version (bump build number)

### Common iOS Rejection Reasons & Fixes

| Reason | Fix |
|--------|-----|
| Missing privacy policy | Add HTTPS privacy policy URL |
| Requires login for core features | Allow demo mode or free trial |
| Crashes on iPad | Fix orientation/layout issues |
| Uses private APIs | Remove/replace private API calls |
| Misleading screenshots | Ensure screenshots match actual app |
| Payment method not disclosed | Clearly show Stripe pricing |
| Data practices not explained | Update privacy policy |

---

## ANDROID GOOGLE PLAY SUBMISSION

### Step 1: Prepare Android Build

**1.1: Update pubspec.yaml & android/app/build.gradle**

File: `android/app/build.gradle`

```gradle
android {
    compileSdkVersion 34
    
    defaultConfig {
        applicationId "com.dealhunter.egypt"
        minSdkVersion 21
        targetSdkVersion 34
        versionCode 1
        versionName "1.0.0"
    }
    
    buildTypes {
        release {
            minifyEnabled true
            proguardFiles getDefaultProguardFile('proguard-android-optimize.txt'), 'proguard-rules.pro'
            signingConfig signingConfigs.release
        }
    }
    
    signingConfigs {
        release {
            storeFile file('keystore.jks')
            storePassword System.getenv("KEYSTORE_PASSWORD")
            keyAlias System.getenv("KEY_ALIAS")
            keyPassword System.getenv("KEY_PASSWORD")
        }
    }
}
```

**1.2: Create Keystore (One-time)**

```bash
keytool -genkey -v -keystore keystore.jks \
  -keyalg RSA -keysize 2048 -validity 10000 \
  -alias key -storetype JKS
```

Save keystore.jks securely (don't commit to git).

**1.3: Update AndroidManifest.xml**

File: `android/app/src/main/AndroidManifest.xml`

```xml
<manifest xmlns:android="http://schemas.android.com/apk/res/android"
    package="com.dealhunter.egypt">

    <!-- Permissions -->
    <uses-permission android:name="android.permission.INTERNET" />
    <uses-permission android:name="android.permission.ACCESS_NETWORK_STATE" />
    <uses-permission android:name="android.permission.ACCESS_COARSE_LOCATION" />
    <uses-permission android:name="android.permission.CAMERA" />
    <uses-permission android:name="android.permission.READ_EXTERNAL_STORAGE" />

    <application
        android:label="DealHunter Egypt"
        android:icon="@mipmap/ic_launcher"
        android:usesCleartextTraffic="false">
        
        <activity android:name=".MainActivity" />
        
    </application>
</manifest>
```

**1.4: Create App Icons**

Generate icons (1024x1024 baseline):
```bash
flutter pub run flutter_launcher_icons
```

Or use Android Studio:
- Right-click `android/app/src/main/res`
- "Image Asset" → Upload 1024x1024 PNG

**1.5: Build Release APK & AAB**

```bash
flutter clean
flutter pub get

# Build APK (for manual testing)
flutter build apk --release

# Build AAB (for Play Store - recommended)
flutter build appbundle --release
```

Output: `build/app/outputs/bundle/release/app-release.aab`

### Step 2: Create Google Play Developer Account

1. Go to **play.google.com/console**
2. Create account (if not already)
3. Pay $25 one-time registration fee
4. Agree to terms

### Step 3: Create App in Play Console

1. Click "Create app"
2. App name: "DealHunter Egypt"
3. Default language: English
4. App type: App
5. Audience: Google Play

### Step 4: Configure App Details

**4.1: App Informations**

- [ ] Title: "DealHunter Egypt"
- [ ] Short description: "Find the best deals from Egyptian e-commerce"
- [ ] Full description: (Same as iOS, 4000 chars max)

```
DealHunter is your ultimate deal finder for Egyptian e-commerce platforms. 
Discover the hottest deals from Amazon Egypt, Jumia, Noon, and more - 
all in one app.

Key Features:
• Browse deals from multiple Egyptian retailers
• Create groups and share deals with friends
• Earn rewards through our referral program
• Get instant notifications about flash sales
• Join our membership program for exclusive deals
• Advanced filtering and personalized recommendations

Join thousands of smart shoppers saving money every day!

Support: support@dealhunter.egypt
Website: www.dealhunter.egypt
```

**4.2: Category**

- [ ] Shopping (primary)
- [ ] Lifestyle (secondary, optional)

**4.3: Content Rating**

1. Complete questionnaire
2. Most answers: "No"
3. No violence, profanity, or adult content
4. Final rating: "Everyone" (3+)

**4.4: Target Audience**

- [ ] Children: No
- [ ] Designed for families: No
- [ ] Target audience: Everyone 3+

**4.5: Screenshots**

Upload 2-8 screenshots (Android):
```
Specifications:
- Format: PNG or JPG
- Min: 320x426 pixels (phone)
- Max: 1080x1920 pixels (phone)
- Recommended: 1080x1920
```

Feature screens same as iOS:
1. Deal browsing
2. Membership/upgrade
3. Groups/Social
4. Notifications
5. Profile

**4.6: Feature Image**

- Size: 1024x500 pixels
- Shows main app feature
- No text overlay

**4.7: Icon & Banner**

- Icon: 512x512 PNG (use app icon)
- Banner: 1024x500 PNG (play store banner)

### Step 5: Configure Pricing & Distribution

**5.1: Pricing**

- [ ] Free (no IAP)
- [ ] OR Free with in-app purchases (Membership)
  - If membership via Stripe, still "Free" app

**5.2: Distribution**

- [ ] Countries/regions: Select Egypt + target countries
- [ ] Release date: Immediate

**5.3: Device Categories**

- [ ] Phones: Yes
- [ ] Tablets: Yes (app should support landscape)
- [ ] Wear OS: No
- [ ] Android TV: No

### Step 6: Configure Privacy & Permissions

**6.1: Privacy Policy**

- [ ] Privacy policy URL: (HTTPS)
- [ ] Content rating certificate: Complete questionnaire
- [ ] Target audience: Everyone
- [ ] Data safety:
  - [ ] User data collection: Yes
  - [ ] Data types collected:
    - [x] User ID
    - [x] Email
    - [x] Device identifiers
  - [ ] Data shared: No (internal only)
  - [ ] Data secured: Encrypted in transit

**6.2: Permissions Disclosure**

List all dangerous permissions in Play Console:
- Internet (required)
- Access network state (required)
- Camera (optional, for profile picture)
- Read external storage (optional)

### Step 7: Upload APK/AAB

1. **Testing Release (Internal Testing)**
   - Click "Internal testing"
   - Click "Create new release"
   - Upload `app-release.aab`
   - Add release notes: "Initial release for testing"
   - Click "Save"
   - Invite testers (internal team)
   - Install via Play Console link

2. **Production Release**
   - Once tested, go to "Production"
   - Click "Create new release"
   - Upload same `app-release.aab`
   - Add release notes:
     ```
     Version 1.0.0 - Initial Release
     
     Features:
     - Browse deals from Egyptian e-commerce sites
     - User authentication and profile
     - Membership tiers and payment
     - Groups and referral program
     - Push notifications
     ```
   - Review all information
   - Click "Review release"

### Step 8: Submit for Review

1. All fields must be completed (green checkmarks)
2. Click "Submit release"
3. Status: "In review" (usually 2-4 hours)
4. Wait for approval

### Step 9: Monitor Approval Status

1. Play Console → Release overview
2. Status options:
   - `Queued` - Waiting to be reviewed
   - `In review` - Being tested
   - `Approved` - Ready for release ✅
   - `Rejected` - Fix issues and resubmit

3. If Rejected:
   - Read rejection email carefully
   - Fix specific issues
   - Bump version code in `build.gradle`
   - Rebuild AAB
   - Resubmit

### Common Android Rejection Reasons & Fixes

| Reason | Fix |
|--------|-----|
| Crashes during testing | Fix crashes, test on real device |
| Missing permissions explanation | Add to app description |
| Requires test account | Provide test credentials |
| Links to external payment | Remove/use Google Play Billing |
| Malware detected | Check dependencies, run security scan |
| Misleading description | Match description to actual features |
| Violates financial services policy | Update Stripe integration disclosure |

---

## APP STORE OPTIMIZATION (ASO)

### Keywords & Discoverability

**Good Keywords (High Volume, Low Competition):**
```
Primary: deals, shopping, save money, discounts
Secondary: egypt, arabic shopping, bargains, sale
Long-tail: best deals egypt, jumia amazon deals, shopping app
```

**Avoid:**
- Trademarked names (unless licensed)
- Competitor names
- Misleading keywords

### Rating Optimization

**Encourage 5-star Reviews:**

```dart
// In settings or after first deal viewed
if (user.deals_viewed > 5 && !user_already_rated) {
  _showRatingDialog();
}
```

**Respond to Reviews:**
- Monitor app store ratings daily
- Respond to 1-star reviews within 24 hours
- Thank users for positive reviews
- Address specific issues mentioned

### A/B Testing

**Pre-Launch:**
- Test screenshots on 10+ people
- Get feedback on descriptions
- Verify icon is recognizable

**Post-Launch:**
- Monitor crash rates
- Track uninstall reasons (surveys)
- Update description based on user feedback

---

## POST-SUBMISSION MONITORING

### Day 1-7: App Store Review & Launch

- [ ] Monitor submission status daily
- [ ] Prepare for approval (can take 1-3 days)
- [ ] Have response plan for rejection
- [ ] Set up analytics tracking

### Day 7-30: Initial Launch Monitoring

- [ ] Monitor crash logs (Firebase Crashlytics)
- [ ] Check app rating (aim for 4.0+)
- [ ] Respond to user reviews
- [ ] Track user acquisition metrics
- [ ] Monitor API performance

### Daily Tasks (After Launch)

- [ ] Check Firebase Crashlytics for crashes
  ```
  Firebase Console → Crashlytics → Top issues
  ```
- [ ] Monitor API error rates
  ```
  Backend logs → Check 5xx errors
  ```
- [ ] Review new user reviews/ratings
- [ ] Track key metrics:
  - Daily active users (DAU)
  - Session length
  - Upgrade rate
  - Referral conversion

### Monthly Tasks

- [ ] Publish monthly release with improvements
- [ ] Update screenshots/description based on user feedback
- [ ] Respond to review themes (e.g., "crashes on login")
- [ ] Analyze retention curves
- [ ] Plan next feature release

---

## TROUBLESHOOTING

### Issue: "Verify Your Email Address" During Submission

**Solution:**
- Check Firebase Console → Authentication → Users
- Verify email is confirmed
- If not, resend verification email

### Issue: App Crashes on Launch

**Solution:**
- [ ] Check Firebase Crashlytics
- [ ] Run `flutter analyze` for lint errors
- [ ] Test on real device (not emulator)
- [ ] Check all dependencies are compatible with Flutter version

### Issue: "Binary is Invalid" Error (iOS)

**Solution:**
```bash
# Clean and rebuild
flutter clean
flutter pub get
flutter build ios --release

# Or if issue persists, use Xcode
cd ios
pod deintegrate
pod install
cd ..
flutter run --release
```

### Issue: Play Store Rejects Payment Integration

**Solution:**
- Remove direct Stripe implementation if required
- Use Google Play Billing Library instead
  ```dart
  pubspec.yaml:
    in_app_purchase: ^3.1.1
  ```
- Or clearly disclose: "Membership via Stripe (external payment)"

### Issue: App Not Showing in Search (After Launch)

**Causes:**
1. Wrong category selected
2. Keywords not indexed yet (takes 24-48 hours)
3. Rating too low (< 2.0 stars)
4. Too many crashes reported

**Solutions:**
1. Wait 48 hours for indexing
2. Fix crashes and update version
3. Encourage positive reviews
4. Verify category is correct

---

## LAUNCH CHECKLIST (Final)

### 48 Hours Before Launch

- [ ] Final build tested on 3+ real devices
- [ ] No crashes in 10-minute usage session
- [ ] Payment processing works (test transaction)
- [ ] All screenshots correct and appealing
- [ ] Description accurate and complete
- [ ] Privacy policy and terms live (HTTPS)
- [ ] Support email configured and monitored
- [ ] Analytics set up (Firebase, Mixpanel, etc.)
- [ ] Crash reporting enabled (Crashlytics)
- [ ] App version bumped (1.0.0)

### Day of Launch

- [ ] Submit to App Store (iOS)
- [ ] Submit to Google Play (Android)
- [ ] Communicate launch on social media (if applicable)
- [ ] Prepare response for potential issues
- [ ] Monitor crash logs in real-time

### Post-Launch Monitoring

- [ ] Daily: Check crash reports, ratings, reviews
- [ ] Weekly: Analyze metrics, user feedback
- [ ] Monthly: Plan next release, gather feature requests

---

## TIMELINE ESTIMATE

| Phase | Duration | Details |
|-------|----------|---------|
| Pre-submission prep | 2-3 days | Icons, screenshots, description |
| Build & sign | 1 day | Create keystore, build APK/AAB |
| iOS submission | 1-3 days | Review process (can be 1-7 days) |
| Android submission | 2-4 hours | Faster review than iOS |
| **Total time** | **5-14 days** | Most time is waiting for review |

---

## RESOURCES

**Apple:**
- App Store Connect: https://appstoreconnect.apple.com
- Apple Developer: https://developer.apple.com
- App Review Guidelines: https://developer.apple.com/app-store/review/guidelines

**Google:**
- Play Console: https://play.google.com/console
- Play Developer Policy: https://play.google.com/about/developer-content-policy
- Publishing Checklist: https://developer.android.com/studio/publish

**Flutter:**
- iOS Build: https://flutter.dev/docs/deployment/ios
- Android Build: https://flutter.dev/docs/deployment/android
- App Signing: https://flutter.dev/docs/deployment/android#signing-the-app

---

## SUMMARY

**iOS App Store:**
- Setup time: 2-3 hours
- Review time: 1-3 days
- Requirements: Mac, Xcode, Developer account ($99)
- Main challenge: APNs certificate setup

**Android Google Play:**
- Setup time: 1-2 hours
- Review time: 2-4 hours
- Requirements: Java keystore, Dev account ($25)
- Main challenge: Policy compliance

**After Launch:**
- Monitor daily for crashes
- Respond to reviews promptly
- Plan feature updates (monthly)
- Build community engagement

---

**You're ready to launch DealHunter globally!** 🚀

For live questions during submission, refer to:
- iOS: Apple Support (support.apple.com)
- Android: Google Play Support (support.google.com/googleplay)
