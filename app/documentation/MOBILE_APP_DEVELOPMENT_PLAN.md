# DealHunter Egypt - Mobile App Development Plan

**Status:** Ready to Start  
**Target Platforms:** iOS + Android  
**Estimated Timeline:** 6-8 weeks for MVP  
**Date Created:** 2026-04-16

---

## PART 1: TECHNOLOGY STACK RECOMMENDATION

### Option A: React Native (RECOMMENDED - Fastest)
**Pros:**
- Write once, deploy to iOS + Android
- Share 80-90% of codebase between platforms
- Large community + tons of libraries
- Can use Expo for rapid development
- Can test on real devices without Mac initially

**Cons:**
- Slightly less native feel than pure native
- Performance slightly lower than native

**Best for:** Quick market entry, shared codebase, cross-platform consistency

---

### Option B: Flutter (Alternative - Excellent Performance)
**Pros:**
- Even faster development than React Native
- Better performance (60/120 FPS animations)
- Beautiful out-of-the-box UI
- Single language (Dart)

**Cons:**
- Smaller ecosystem than React Native
- Less third-party integrations

**Best for:** Performance-critical app, premium UX

---

### Option C: Native (iOS + Android)
**Pros:**
- Best performance
- Full access to native APIs
- Best app store presence

**Cons:**
- Code duplication (Swift + Kotlin)
- 2x development time
- More expensive

**Best for:** Large teams, performance critical, complex native features

---

## RECOMMENDATION: React Native + Expo
**Why?** Fastest time to market, maximum code sharing, easiest to maintain. Perfect for startup/MVP phase.

---

## PART 2: ARCHITECTURE OVERVIEW

```
┌─────────────────────────────────────────────────────┐
│                  Mobile App (React Native)          │
│  ┌──────────────────────────────────────────────┐   │
│  │  Screens                                     │   │
│  │  - Login/Signup                              │   │
│  │  - Deal Feed (Home)                          │   │
│  │  - Deal Details                              │   │
│  │  - Membership                                │   │
│  │  - Groups                                    │   │
│  │  - Referrals                                 │   │
│  │  - Settings                                  │   │
│  └──────────────────────────────────────────────┘   │
│  ┌──────────────────────────────────────────────┐   │
│  │  State Management (Redux or Zustand)         │   │
│  └──────────────────────────────────────────────┘   │
│  ┌──────────────────────────────────────────────┐   │
│  │  API Client (Axios)                          │   │
│  └──────────────────────────────────────────────┘   │
│  ┌──────────────────────────────────────────────┐   │
│  │  Firebase (Auth + Push Notifications)        │   │
│  └──────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────┘
         ↓  HTTPS API Calls
┌─────────────────────────────────────────────────────┐
│         Backend Server (Flask @ server.py)          │
│  - User management                                  │
│  - Deal aggregation                                 │
│  - Subscription handling                            │
│  - Push notifications                               │
└─────────────────────────────────────────────────────┘
         ↓  Firestore + Stripe
```

---

## PART 3: PROJECT STRUCTURE

```
dealhunter-mobile/
├── ios/                          # iOS specific files
│   ├── Podfile
│   ├── Runner.xcworkspace
│   └── ...
├── android/                      # Android specific files
│   ├── app/
│   ├── build.gradle
│   └── ...
├── src/
│   ├── screens/
│   │   ├── AuthStack/
│   │   │   ├── LoginScreen.js
│   │   │   ├── SignupScreen.js
│   │   │   └── PasswordResetScreen.js
│   │   ├── MainStack/
│   │   │   ├── HomeScreen.js
│   │   │   ├── DealDetailScreen.js
│   │   │   ├── MembershipScreen.js
│   │   │   ├── GroupsScreen.js
│   │   │   ├── ReferralsScreen.js
│   │   │   └── SettingsScreen.js
│   │   └── AdminStack/
│   │       ├── AdminHomeScreen.js
│   │       ├── UsersScreen.js
│   │       └── ...
│   ├── components/
│   │   ├── DealCard.js
│   │   ├── TierBadge.js
│   │   ├── NotificationBanner.js
│   │   └── ...
│   ├── services/
│   │   ├── api.js            # Axios API client
│   │   ├── auth.js           # Firebase Auth
│   │   ├── firebase.js       # Firebase config
│   │   └── notifications.js  # Push notifications
│   ├── store/
│   │   ├── slices/           # Redux slices
│   │   │   ├── authSlice.js
│   │   │   ├── dealsSlice.js
│   │   │   └── userSlice.js
│   │   └── store.js
│   ├── utils/
│   │   ├── formatting.js
│   │   ├── colors.js
│   │   └── constants.js
│   ├── App.js               # Main app component
│   └── index.js
├── app.json                 # Expo config
├── package.json
├── .env.example
└── README.md
```

---

## PART 4: PHASE-WISE DEVELOPMENT

### PHASE 1: Setup & Authentication (Week 1)
**Goal:** Get login/signup working

**Tasks:**
1. Create React Native project with Expo
2. Install dependencies:
   - `expo-firebase-recaptcha`
   - `firebase` (Auth)
   - `@react-navigation/native` (Navigation)
   - `axios` (API calls)
   - `redux-toolkit` (State management)
3. Setup Firebase Auth
4. Create login/signup screens
5. Setup token storage (AsyncStorage)
6. Setup navigation stack (Auth vs Main)

**Acceptance Criteria:**
- [ ] User can sign up with email/password
- [ ] User can log in
- [ ] Login token persists across app restarts
- [ ] Logout clears token

---

### PHASE 2: Deal Feed & Browsing (Week 2)
**Goal:** Display deals from backend API

**Tasks:**
1. Create deal listing API client
2. Build HomeScreen with:
   - Deal feed (FlatList)
   - Deal cards
   - Category filters
   - Source filters
3. Build DealDetailScreen
4. Add deal images + caching
5. Add "View Deal" → open browser
6. Track daily deal limit

**Acceptance Criteria:**
- [ ] Deals load from API
- [ ] Images display
- [ ] Filters work
- [ ] Daily limit tracked
- [ ] Can open product links

---

### PHASE 3: Membership & Payments (Week 2-3)
**Goal:** Show tier info and allow upgrades

**Tasks:**
1. Create MembershipScreen
2. Display current tier + renewal date
3. Display daily usage (X/Y deals today)
4. Add "Upgrade Tier" buttons
5. Integrate Stripe (mobile payment SDK)
6. Handle successful payment → tier upgrade
7. Show tier benefits

**Acceptance Criteria:**
- [ ] Current tier displays
- [ ] Daily usage shows
- [ ] Can tap "Upgrade"
- [ ] Stripe payment works
- [ ] Tier updates after payment

---

### PHASE 4: Social Features (Week 3-4)
**Goal:** Groups, referrals, gifting

**Tasks:**
1. GroupsScreen:
   - Create group
   - Join group
   - View group members
   - Group daily limit

2. ReferralsScreen:
   - Display referral code
   - Copy to clipboard
   - Show referrals made
   - Show rewards earned

3. Add gift deal functionality:
   - Select contact
   - Send gift

**Acceptance Criteria:**
- [ ] Can create/join groups
- [ ] Referral code displays
- [ ] Can gift deals
- [ ] Rewards shown

---

### PHASE 5: Notifications & Settings (Week 4)
**Goal:** Push notifications, preferences

**Tasks:**
1. Setup Firebase Cloud Messaging (FCM)
2. Request notification permissions
3. Handle notification reception
4. SettingsScreen:
   - Language toggle
   - Notification preferences
   - Change password
   - Logout

**Acceptance Criteria:**
- [ ] Push notifications work
- [ ] In-app notifications show
- [ ] Settings persist

---

### PHASE 6: Admin Mobile App (Week 5-6) - Optional
**Goal:** Minimal admin functionality on mobile

**Tasks:**
1. Create separate admin app (or shared codebase)
2. Admin login
3. View users (read-only or with filters)
4. Send notifications
5. View analytics

**Acceptance Criteria:**
- [ ] Admin can log in
- [ ] Can view users
- [ ] Can send notifications

---

### PHASE 7: Testing & Polishing (Week 6-7)
**Goal:** Quality assurance, bug fixes

**Tasks:**
1. Test on real devices (iOS + Android)
2. Fix bugs
3. Performance optimization
4. Offline capability (cache deals)
5. Error handling
6. Loading states

**Acceptance Criteria:**
- [ ] No crashes
- [ ] All flows work
- [ ] Smooth animations
- [ ] Fast load times

---

### PHASE 8: App Store Submission (Week 8)
**Goal:** Publish to Apple App Store + Google Play

**Tasks:**
1. Create app icons + screenshots
2. Write app descriptions
3. Setup privacy policy
4. Configure signing certificates
5. Submit to app stores
6. Handle review feedback

**Acceptance Criteria:**
- [ ] iOS app on App Store
- [ ] Android app on Google Play

---

## PART 5: SETUP INSTRUCTIONS

### Step 1: Install Development Tools

```bash
# Install Node.js 16+ (if not already installed)
# From: https://nodejs.org/

# Install Expo CLI
npm install -g expo-cli

# Install EAS CLI (for building/publishing)
npm install -g eas-cli
```

### Step 2: Create React Native Project

```bash
# Create new Expo project
expo init DealHunterMobile --template blank

cd DealHunterMobile

# Install dependencies
npm install

# Core libraries
npm install firebase axios @react-navigation/native @react-navigation/stack redux @reduxjs/toolkit react-redux

# UI components
npm install react-native-paper react-native-gesture-handler react-native-reanimated

# Storage
npm install @react-native-async-storage/async-storage

# Image caching
npm install react-native-cached-image

# Expo modules
npm install expo-constants expo-updates
```

### Step 3: Setup Firebase Config

Create `src/services/firebase.js`:

```javascript
import { initializeApp } from 'firebase/app';
import { getAuth } from 'firebase/auth';
import { getFirestore } from 'firebase/firestore';
import { getMessaging } from 'firebase/messaging';

const firebaseConfig = {
  apiKey: "AIzaSyCM7irklt9VLM7NrIXovI3oZQ9wkoodywU",
  authDomain: "dealhunter-egypt-70d29.firebaseapp.com",
  projectId: "dealhunter-egypt-70d29",
  storageBucket: "dealhunter-egypt-70d29.appspot.com",
  messagingSenderId: "477835366168",
  appId: "1:477835366168:web:YOUR_APP_ID"
};

const app = initializeApp(firebaseConfig);
export const auth = getAuth(app);
export const db = getFirestore(app);
export const messaging = getMessaging(app);
```

### Step 4: Setup API Client

Create `src/services/api.js`:

```javascript
import axios from 'axios';
import AsyncStorage from '@react-native-async-storage/async-storage';

const API_BASE_URL = 'https://dealhunter-scraper.onrender.com/api/v1';

const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 10000,
});

// Add auth token to requests
api.interceptors.request.use(async (config) => {
  const token = await AsyncStorage.getItem('adminToken');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

export default api;
```

### Step 5: Test on Device

```bash
# Start development server
expo start

# Scan QR code with Expo Go app (iOS/Android)
# Or press 'i' for iOS simulator / 'a' for Android emulator
```

---

## PART 6: KEY FEATURES TO BUILD

### Deal Feed Screen
- [ ] List deals from `/api/v1/deals`
- [ ] Filter by category/source
- [ ] Search deals
- [ ] Scroll/pagination
- [ ] Show discount %, price, image
- [ ] Open product in browser

### User Profile
- [ ] Display current tier
- [ ] Show daily usage (X/Y deals)
- [ ] Show referral code (copy to clipboard)
- [ ] Edit profile
- [ ] Change password
- [ ] Logout

### Upgrade Flow
- [ ] Show all tiers
- [ ] Display benefits
- [ ] Integrate Stripe (use `@stripe/stripe-react-native`)
- [ ] Handle payment
- [ ] Update tier on success

### Groups
- [ ] Create group
- [ ] Join group with code
- [ ] List members
- [ ] Leave group
- [ ] Show group daily limit

### Notifications
- [ ] Request push notification permission
- [ ] Receive notifications
- [ ] Show notification badge
- [ ] Handle notification tap

### Offline Support
- [ ] Cache deals locally (SQLite or AsyncStorage)
- [ ] Show cached deals when offline
- [ ] Sync when back online

---

## PART 7: API ENDPOINTS NEEDED

All these endpoints should already exist in your `server.py`:

### Authentication
- `POST /api/v1/auth/register` - Sign up
- `POST /api/v1/auth/login` - (Firebase handles this)
- `GET /api/v1/user/me` - Get user profile

### Deals
- `GET /api/v1/deals` - List deals (with filters)
- `GET /api/v1/deals?category=electronics&source=amazon` - Filtered deals

### User Account
- `PUT /api/v1/users/{uid}` - Update profile
- `POST /api/v1/subscriptions/checkout` - Get Stripe session
- `GET /api/v1/subscriptions/current` - Get current subscription
- `POST /api/v1/subscriptions/cancel` - Cancel subscription

### Groups
- `GET /api/v1/user-groups` - List user's groups
- `POST /api/v1/user-groups` - Create group
- `POST /api/v1/user-groups/{id}/members` - Join group

### Referrals
- `GET /api/v1/user/referral-code` - Get referral code
- `GET /api/v1/user/referral-status` - Get referral stats

### Notifications
- `GET /api/v1/user/notifications` - List notifications
- `POST /api/v1/notifications/mark-read` - Mark as read

---

## PART 8: TESTING STRATEGY

### Device Testing
- [ ] Test on iPhone 13+ (iOS)
- [ ] Test on Samsung Galaxy / Pixel (Android)
- [ ] Test on tablets (iPad / iPad-sized Android)
- [ ] Test offline scenario
- [ ] Test with poor network (3G simulation)

### User Flows
- [ ] Complete signup → login → view deals → upgrade tier flow
- [ ] Complete referral sharing flow
- [ ] Complete group creation + join flow
- [ ] Push notification receipt

### Performance
- [ ] Deal feed scrolls smoothly
- [ ] Images load without lag
- [ ] Payment doesn't timeout
- [ ] App doesn't crash after 5 minutes of use

---

## PART 9: DEPLOYMENT TO APP STORES

### iOS (Apple App Store)

**Requirements:**
- Mac with Xcode
- Apple Developer Account ($99/year)
- Team ID from Apple

**Steps:**
1. Build with EAS: `eas build --platform ios`
2. Generate signing certificates
3. Upload to TestFlight first
4. Test on real devices
5. Submit to App Store

**Timeline:** 5-7 days (Apple review)

---

### Android (Google Play Store)

**Requirements:**
- Google Play Developer Account ($25 one-time)
- Keystore file for signing

**Steps:**
1. Build with EAS: `eas build --platform android`
2. Generate signed APK/AAB
3. Upload to Google Play Console
4. Fill in store listing
5. Submit for review

**Timeline:** Usually 2-4 hours (faster than Apple)

---

## PART 10: NEXT IMMEDIATE STEPS

### Action Items:
1. **Today:**
   - [ ] Decide: React Native (recommended) or Flutter?
   - [ ] Decide: Expo or bare React Native?
   - [ ] Create GitHub repo for mobile code

2. **Tomorrow:**
   - [ ] Create React Native project
   - [ ] Install dependencies
   - [ ] Setup Firebase config
   - [ ] Create basic navigation structure

3. **Week 1:**
   - [ ] Complete authentication screens
   - [ ] Test login/signup flow
   - [ ] Setup token persistence

4. **Week 2:**
   - [ ] Build deal feed screen
   - [ ] Integrate deal listing API
   - [ ] Add filters

---

## SUMMARY

**Tech Stack:**
- Framework: React Native + Expo
- State: Redux Toolkit
- API: Axios
- Auth: Firebase Auth
- Payments: Stripe
- Database: Firestore (read-only from mobile)
- Notifications: Firebase Cloud Messaging (FCM)

**Timeline:** 6-8 weeks for MVP to App Store

**MVP Features:**
1. ✅ Login/Signup
2. ✅ Deal feed & browsing
3. ✅ Membership/upgrade
4. ✅ Basic groups
5. ✅ Referrals
6. ✅ Push notifications
7. ✅ Settings

**Post-MVP (Nice to have):**
- Offline deal caching
- Advanced search
- Deal watchlist
- Social sharing
- Admin mobile app

---

## Questions to Decide NOW:

1. **Framework?** React Native (recommended) or Flutter?
2. **Distribution?** Expo Go testing first, then EAS builds?
3. **Admin app?** Separate native admin or skip for now?
4. **MVP priority?** Focus on deal browsing, or include all features?

**Answer these and I'll start building!** 🚀
