# DealHunter Egypt - Complete Testing Checklist

**Purpose:** Verify all features are working correctly before iOS/Android mobile development
**Last Updated:** 2026-04-16
**Status:** In Progress

---

## PHASE 1: SYSTEM SETUP & DEPLOYMENT

### 1.1 Backend Deployment
- [ ] Server running on Render: https://dealhunter-scraper.onrender.com (or your deployed URL)
  - Test: `curl https://dealhunter-scraper.onrender.com/health`
  - Expected: 200 OK response
- [ ] Firebase Admin SDK initialized
  - Check console logs for: "✓ Firebase Admin SDK initialized"
- [ ] Database connection active
  - Check logs for: "Connected to Firebase successfully"
- [ ] Scraper running in background
  - Check logs for: "Scraper started, running every X minutes"

### 1.2 Frontend Deployment
- [ ] Admin dashboard accessible: `/admin`
- [ ] User dashboard accessible: `/user`
- [ ] Both dashboards load Firebase config correctly
- [ ] No 404 errors in browser console

---

## PHASE 2: AUTHENTICATION

### 2.1 Firebase Auth Setup
- [ ] Firebase project created: `dealhunter-egypt-70d29`
- [ ] Email/Password auth enabled in Firebase Console
- [ ] First admin user created and verified
- [ ] Test user(s) created for testing

### 2.2 Admin Authentication
- [ ] Admin can log in to `/admin` with email/password
  - Login: admin-email@example.com / password
  - Expected: Redirects to Monitor page
- [ ] Invalid credentials rejected with error message
  - Test: Wrong password → "Invalid credentials" shown
- [ ] JWT token stored in localStorage
  - Check: Browser DevTools → Application → localStorage → `adminToken`
- [ ] Token persists across page reloads
  - Reload `/admin` → stays logged in without re-entering credentials
- [ ] Logout works: Click logout → redirects to login page
- [ ] Expired token handled: Delete localStorage token → redirect to login

### 2.3 User Authentication
- [ ] User can sign up on `/user`
  - Email: test@example.com
  - Password: TestPassword123
  - Expected: Account created, logged in automatically
- [ ] User can log in with correct credentials
- [ ] User can log out
- [ ] Invalid credentials rejected
- [ ] Password reset works (if implemented)
- [ ] User token persists in localStorage

---

## PHASE 3: ADMIN DASHBOARD - CORE FUNCTIONALITY

### 3.1 Navigation & Permissions
- [ ] All 10 tabs visible: Monitor, Deals, Sources, Users, Notifications, Add Deal, Fake Checker, Competitors, Team, Pricing
- [ ] Only tab pages load when clicked (not scrolling)
- [ ] Permission checks work:
  - [ ] Owner role: Can access all pages
  - [ ] Editor role: Can access assigned pages, denied on others
  - [ ] Viewer role: Can view only, edit buttons disabled

### 3.2 Users Page (Critical)
- [ ] Users table loads with all columns:
  - [ ] Email
  - [ ] Name
  - [ ] Current Tier (dropdown)
  - [ ] Previous Tier
  - [ ] Referrals Made
  - [ ] Group
  - [ ] Registered Date
  - [ ] Last Login
  - [ ] Actions (edit, delete)
- [ ] Can change user tier via dropdown
  - Change user from "Free" → "Premium"
  - Expected: Tier changes in Firestore `users` collection
- [ ] Can set custom daily limit
  - Input: 200
  - Click "Set" button
  - Expected: Value persists in Firestore `users.daily_deal_limit`
- [ ] Can delete user
  - Click 🗑️ button
  - Confirm deletion
  - Expected: User removed from table and Firestore
- [ ] "+ Create User" button works
  - Opens modal with: Email, Name, Tier, Daily Limit
  - Save new user
  - Expected: New user appears in table

### 3.3 Notifications Page (Critical)
- [ ] "+ Send Notification" button opens modal
- [ ] Modal has:
  - [ ] Title input
  - [ ] Message textarea
  - [ ] Target: Dropdown (All Users / Specific Tier / Specific Group / Specific User)
  - [ ] Channel: Checkboxes (In-App, Email, SMS)
  - [ ] Send button
- [ ] Send notification to "All Users"
  - Expected: Logs show API call succeeding, notification saved to Firestore
- [ ] Send notification to specific tier (e.g., "Premium")
  - Expected: Only Premium users receive notification
- [ ] Send notification to specific group
  - Expected: Only group members receive notification
- [ ] Send notification to specific user
  - Expected: Only that user receives notification
- [ ] Notification appears in user dashboard (in-app)
- [ ] API logs show: 🔑 Token, 📡 Request, ✅ Success

### 3.4 Pricing Page (💰)
- [ ] All 4 tiers displayed: Free, Trial, Premium, VIP
- [ ] Each tier shows: Daily limit, Monthly price, Features list
- [ ] "+ Add New Tier" button works
  - Create: "Premium Plus" with daily_limit=750, price=49, features
  - Expected: New tier appears in list
- [ ] "Edit" button opens tier edit modal
  - Change Premium daily limit: 500 → 600
  - Save
  - Expected: Change persists in Firestore `tier_config` collection
- [ ] "Delete" button removes tier
  - Expected: Tier no longer in list

### 3.5 Team Page (👥)
- [ ] All team members displayed in table
- [ ] Columns: Email, Name, Role, Permissions, Status, Last Login
- [ ] "+ Add Team Member" button opens modal
  - Email: newadmin@example.com
  - Name: New Admin
  - Role: Editor
  - Permissions: sources, deals (unchecked: users, notifications, etc.)
  - Status: Active
  - Save
  - Expected: New team member appears in table
- [ ] Can edit team member
  - Change role: Editor → Viewer
  - Expected: Changes persist
- [ ] Can remove team member
  - Expected: Removed from table
- [ ] Permissions cascade: Owner has all permissions (checkboxes disabled)

### 3.6 Groups Page (👨‍👩‍👧‍👦)
- [ ] Group creation modal works
  - Group Name: "Smith Family"
  - Members: family@email.com, dad@email.com
  - Tier: Premium
  - Description: "Family deal sharing"
  - Save
  - Expected: Group appears in list
- [ ] Group edit works
  - Click edit → change tier to VIP
  - Save → changes persist
- [ ] Group delete works
- [ ] Group members listed

### 3.7 Offers Page (🎁)
- [ ] "+ Create Offer" button opens modal
  - Discount Type: Percentage
  - Discount Value: 25
  - Target: Specific Group ("Smith Family")
  - Description: "Family special"
  - Save
  - Expected: Offer appears in list
- [ ] Can edit offers
- [ ] Can delete offers
- [ ] Offers show: Type, Value, Target, Created Date

### 3.8 Sources, Deals, Add Deal, Fake Checker, Competitors Pages
- [ ] Each page loads without errors
- [ ] Data displays correctly (if applicable)
- [ ] CRUD operations work (Create, Read, Update, Delete)

---

## PHASE 4: USER DASHBOARD - CORE FUNCTIONALITY

### 4.1 Login & Account
- [ ] User can log in to `/user`
- [ ] User can sign up for new account
- [ ] Account info persists across sessions
- [ ] Logout works

### 4.2 Home Page - Deal Feed
- [ ] Deals load from Firestore `deals` collection
  - Expected: Real deal cards with images, titles, prices, discounts
  - Minimum 10+ deals should appear
- [ ] Deal cards display:
  - [ ] Product image
  - [ ] Product title
  - [ ] Current price (EGP)
  - [ ] Original price (struck-through)
  - [ ] Discount percentage
  - [ ] Source (Amazon, Jumia, Noon)
  - [ ] Rating/verdict
  - [ ] "View Deal" button
- [ ] Click "View Deal" button
  - Expected: Opens product page in new tab
  - Daily deal count increments: "5/50 deals today"
- [ ] Filters work:
  - [ ] Filter by Category
  - [ ] Filter by Source (Amazon, Jumia, Noon)
  - [ ] Clear filters button works
- [ ] Loading state shows while deals fetch
- [ ] "No deals found" message if Firestore empty

### 4.3 Membership Page
- [ ] Current tier displayed: "Free" / "Trial" / "Premium" / "VIP"
- [ ] Daily usage shown: "25/100 deals viewed today"
- [ ] Tier features listed
- [ ] Renewal date displayed (if applicable)
- [ ] "Upgrade to [Tier]" button works for each tier
  - Click → Opens Stripe checkout session
  - Enter test card: `4242 4242 4242 4242` / Any future date / Any CVC
  - Confirm payment
  - Expected: User tier changes to new tier in Firestore
  - No longer shows upgrade button for purchased tier

### 4.4 Groups Page
- [ ] User can create group
  - Group Name: "My Friends"
  - Invite members: friend1@email.com, friend2@email.com
  - Expected: Group created, members invited
- [ ] User can join group via invite
  - Get invite link from group admin
  - Click link → User joins group
- [ ] Group members listed
- [ ] Group daily limit shown: "150/500 deals (group)"
- [ ] Leave group button works

### 4.5 Referrals Page
- [ ] Referral code displayed and copyable
  - Click "Copy" → Copied to clipboard
  - Can share with friends
- [ ] Referrals made counter: "3 friends referred"
- [ ] Reward status shown: "1 month Premium earned"
- [ ] Pending referrals listed: "Waiting for friend to sign up"
- [ ] Completed referrals listed: "friend@email.com - Completed"
- [ ] Reward balance shown: "2 months Premium earned"

### 4.6 Settings Page
- [ ] Edit profile button works
  - Change name: "John" → "John Smith"
  - Save → Changes persist
- [ ] Change password works
  - Old password required
  - New password set
  - Can log in with new password
- [ ] Language selection works
  - Select "العربية"
  - UI switches to Arabic
  - Selection persists across page reloads
- [ ] Notification preferences editable
- [ ] Privacy settings functional

---

## PHASE 5: SCRAPER & BACKGROUND JOBS

### 5.1 Scraper Execution
- [ ] Scraper runs on schedule (every 3 minutes by default)
  - Check logs: "Scraper started" messages appearing
- [ ] Scraper pauses/resumes via Admin panel
  - Admin → Monitor → "Pause Scraper" button
  - Check logs: "Scraper paused by [admin email]"
  - Click "Resume" → Scraper starts again

### 5.2 Data Sources - CRITICAL FIX NEEDED
**Current Status:** Only Amazon Egypt & Jumia Egypt working

- [ ] **Amazon Egypt** - WORKING
  - [ ] Scraper fetches deals
  - [ ] Prices in EGP
  - [ ] Images load
  - [ ] Discounts calculated correctly
  - [ ] Data saved to Firestore with `site_display: "Amazon Egypt"`

- [ ] **Jumia Egypt** - WORKING
  - [ ] Scraper fetches deals
  - [ ] Prices in EGP
  - [ ] Images load
  - [ ] Discounts calculated correctly
  - [ ] Data saved to Firestore with `site_display: "Jumia Egypt"`

- [ ] **Noon Egypt** - NEEDS FIXING
  - [ ] Scraper fetches deals
  - [ ] Prices in EGP
  - [ ] Images load
  - [ ] Discounts calculated correctly
  - [ ] Data saved to Firestore with `site_display: "Noon Egypt"`

- [ ] **Carrefour Egypt** (if enabled)
  - [ ] Scraper fetches deals
  - [ ] Data saved correctly

### 5.3 Fake Checker Integration
- [ ] Fake Checker runs on each scraped deal
  - [ ] Checks price history (Kanbkam, Safqa)
  - [ ] Sets `fake_verdict`: "GENUINE" / "SUSPICIOUS" / "FAKE"
  - [ ] Sets `verdict_reason`: explanation
  - [ ] Data saved to Firestore

### 5.4 Firestore Data Integrity
- [ ] Deals collection properly structured
  - Required fields: `title`, `current_price`, `original_price`, `site_display`, `image_url`, `product_url`, `verified`, `hidden`, `timestamp`, `fake_verdict`, `rating`
- [ ] No duplicate deals (same product on same site)
- [ ] Deals ordered by `timestamp` (newest first)
- [ ] Old deals archived or deleted (older than 30 days)

---

## PHASE 6: API ENDPOINTS - ALL ENDPOINTS

### 6.1 Authentication Endpoints
- [ ] `POST /api/v1/auth/register` - Create new user account
  - Body: `{ email, password, name }`
  - Expected: User created, auth token returned

- [ ] `POST /api/v1/auth/login` - User login
  - Body: `{ email, password }`
  - Expected: Auth token returned

- [ ] `POST /api/v1/auth/logout` - Logout
  - Expected: Token invalidated

### 6.2 User Management Endpoints
- [ ] `GET /api/v1/users/{uid}` - Get user profile
  - Expected: User data with tier, daily_limit, referral_code

- [ ] `PUT /api/v1/users/{uid}` - Update user profile
  - Body: `{ name, email }`
  - Expected: Changes persisted

- [ ] `DELETE /api/v1/users/{uid}` - Delete user
  - Expected: User removed from Firestore

- [ ] `PUT /api/v1/users/{uid}/daily-limit` - Set custom daily limit
  - Body: `{ daily_limit: 200 }`
  - Expected: Value persisted, accessible in admin panel

### 6.3 Subscription/Tier Endpoints
- [ ] `POST /api/v1/subscriptions/checkout` - Create Stripe session
  - Body: `{ tier: "premium" }`
  - Expected: Stripe session URL returned, checkout works

- [ ] `GET /api/v1/subscriptions/current` - Get current subscription
  - Expected: Current tier, renewal date

- [ ] `POST /api/v1/subscriptions/cancel` - Cancel subscription
  - Expected: Tier downgraded to Free

- [ ] `GET /api/v1/tiers` - Get all tier configurations
  - Expected: All tiers with prices, daily limits, features

- [ ] `PUT /api/v1/tiers/{tier_name}` - Update tier (admin)
  - Body: `{ daily_limit, price, features }`
  - Expected: Changes persist, visible in pricing page

### 6.4 Notifications Endpoints
- [ ] `POST /api/v1/notifications/send` - Send notification (admin)
  - Body: `{ title, message, target_tier/target_group/target_user, channels: [in_app, email, sms] }`
  - Expected: Notification saved, appears in user dashboard

- [ ] `GET /api/v1/user/notifications` - Get user's notifications
  - Expected: All notifications for logged-in user

### 6.5 Groups Endpoints
- [ ] `POST /api/v1/user-groups` - Create group (admin)
  - Body: `{ group_name, members: [emails], tier, description }`
  - Expected: Group created, members added

- [ ] `GET /api/v1/user-groups` - Get all groups (admin)
  - Expected: All groups listed

- [ ] `POST /api/v1/user/groups/join` - User joins group
  - Body: `{ invite_code }`
  - Expected: User added to group

### 6.6 Referrals Endpoints
- [ ] `GET /api/v1/user/referral-code` - Get user's referral code
  - Expected: Unique code in format "DEAL8F7K9X2Q"

- [ ] `GET /api/v1/user/referral-status` - Get referral stats
  - Expected: { made: 3, reward_balance: "1 month Premium" }

- [ ] `POST /api/v1/user/referral/{code}` - Sign up with referral code
  - Expected: Referrer recorded, reward queued

### 6.7 Deals Endpoints
- [ ] `GET /api/v1/deals` - Get all deals (with filters)
  - Query params: `category`, `site`, `limit`
  - Expected: Filtered deals list

- [ ] `POST /api/v1/deals/gift` - Gift deal to friend
  - Body: `{ deal_id, to_email }`
  - Expected: Gift created, friend notified

### 6.8 Admin Endpoints
- [ ] `POST /api/v1/admin/users` - Admin create user
  - Body: `{ email, name, tier }`
  - Expected: User created with auth token

- [ ] `GET /api/v1/admin/team` - Get team members
  - Expected: All admin team members with roles

- [ ] `POST /api/v1/admin/team` - Add team member
  - Body: `{ email, name, role, permissions }`
  - Expected: Team member added, can log in

- [ ] `PUT /api/v1/admin/team/{email}` - Update team member
  - Body: `{ role, permissions }`
  - Expected: Changes persist, permissions enforced

- [ ] `DELETE /api/v1/admin/team/{email}` - Remove team member
  - Expected: Team member can no longer access admin

---

## PHASE 7: FIRESTORE COLLECTIONS & SECURITY

### 7.1 Collections Exist & Structured
- [ ] `users` collection exists
  - Fields: email, name, tier, daily_deal_limit, referral_code, stripe_customer_id, group_name, created_at
- [ ] `deals` collection exists
  - Fields: title, current_price, original_price, site_display, image_url, product_url, timestamp, verified, hidden, fake_verdict, rating
- [ ] `admin_users` collection exists
  - Fields: email, name, role, permissions, status, added_at, last_login
- [ ] `tier_config` collection exists
  - Fields per tier: daily_limit, price, features, status
- [ ] `user_groups` collection exists
  - Fields: group_name, admin_email, members, tier, daily_budget, created_at
- [ ] `notifications` collection exists
  - Fields: title, message, target_tier/group/user, channels, created_at, read_by
- [ ] `special_offers` collection exists
  - Fields: discount_type, discount_value, target_type, target_value, created_at
- [ ] `scraper_control` collection exists
  - Status document with: status (active/paused), paused_by, paused_at, resume_at

### 7.2 Firestore Security Rules
- [ ] Public read access to `deals` collection (for both admins and users)
- [ ] Private read/write to `admin_users` (only authenticated admins)
- [ ] Private read/write to `users` (user can read own, admin can read all)
- [ ] Rules deployed to Firebase Console

### 7.3 Composite Indexes
- [ ] Index exists: `deals` (timestamp DESC, featured DESC)
- [ ] Index exists: `users` (tier, created_at DESC)
- [ ] Index exists: `notifications` (user_id, read, created_at DESC)

---

## PHASE 8: STRIPE INTEGRATION (TEST MODE)

### 8.1 Stripe Account & Keys
- [ ] Stripe test mode enabled
- [ ] Publishable key: `pk_test_...` in environment
- [ ] Secret key: `sk_test_...` in environment (server only)

### 8.2 Test Card Payments
- [ ] Successful charge: `4242 4242 4242 4242`
  - Any future expiry date, any CVC
  - Expected: Payment succeeds, user tier upgrades
  
- [ ] Declined card: `4000 0000 0000 0002`
  - Expected: Payment fails, error message shown
  
- [ ] Requires authentication: `4000 0025 0000 3155`
  - Expected: 3D Secure dialog shown
  
- [ ] Webhook handler working
  - Payment success webhook creates/updates subscription in Firestore
  - Webhook failure webhook updates subscription status to failed

### 8.3 Subscription Management
- [ ] User can view current subscription
- [ ] User can cancel subscription
  - Expected: Tier downgraded to Free, cancellation date set
- [ ] Admin can view all subscriptions
- [ ] Admin can override subscription status

---

## PHASE 9: CRITICAL ISSUES TO FIX

### ISSUE 1: Scraper Not Working for All Sources ⚠️
**Status:** Only Amazon Egypt & Jumia Egypt scraping successfully

**Required Fix:**
1. Debug Noon Egypt scraper:
   - Check if endpoint is accessible
   - Verify HTML structure matches parsing code
   - Check for rate limiting or IP blocks
   - Implement fallback methods if primary fails

2. Test each source independently:
   - Run scraper in debug mode with single source
   - Check Firestore for incoming deals
   - Verify `site_display` field is correct

3. Add monitoring:
   - Log number of deals scraped per source
   - Alert if a source scrapes 0 deals
   - Automatic retry with exponential backoff

**Acceptance Criteria:**
- [ ] All 3+ sources scraping successfully
- [ ] Each source saves to Firestore with correct `site_display`
- [ ] Admin Monitor page shows deal counts per source

---

### ISSUE 2: Firebase Authentication Not Accessible ⚠️
**Status:** Admin dashboard shows "auth/invalid-login-credentials"

**Required Fix:**
1. Verify admin user exists in Firebase Console
   - Go to Firebase Console → Authentication → Users
   - Check if test admin account exists
   - If not, create new account with email/password

2. Test login locally first (if running locally):
   - Run server locally
   - Verify Firebase credentials loaded
   - Test login on http://localhost:5000/admin

3. Verify credentials in production (Render):
   - Check FIREBASE_CREDENTIALS_JSON environment variable is set
   - Restart Render app: Settings → Restart → Manual restart

4. Enable Firebase Auth methods:
   - Firebase Console → Authentication → Sign-in Method
   - Enable "Email/Password"
   - Enable "Google" (optional, for easier testing)

**Acceptance Criteria:**
- [ ] Admin can log in successfully
- [ ] User can sign up/log in successfully
- [ ] Both receive valid JWT tokens

---

### ISSUE 3: API Calls Not Showing Console Logs ⚠️
**Status:** Daily limit updates not logging to console despite debug code

**Possible Causes:**
- Logs being buffered and not flushed
- Console cleared before inspection
- API calls failing silently (500 error)
- Token validation failing (403)

**Required Fix:**
1. Check browser console thoroughly:
   - Open DevTools (F12)
   - Go to Console tab
   - Look for all 🔑 📡 ✅ emoji logs
   - Scroll up to see all messages
   - Check "All Levels" not filtering errors only

2. Check Network tab:
   - Go to Network tab
   - Perform action (change daily limit)
   - Look for API request
   - Click request → check Response tab
   - Check Status code: 200 (success) or 403/500 (error)?
   - If error, read response body for error message

3. Server logs:
   - Render: Dashboard → Logs
   - Check for API endpoint logs
   - Look for permission errors

4. Add request/response logging:
   - If still not visible, enable verbose logging in server.py
   - Add print statements for every step

**Acceptance Criteria:**
- [ ] All API calls logged in browser console
- [ ] Network requests show 200 status
- [ ] Data persists in Firestore

---

## TESTING EXECUTION PLAN

### Week 1: Authentication & Setup (Days 1-2)
1. Verify Firebase project and credentials
2. Test admin login (fix if needed)
3. Test user signup/login
4. Verify tokens stored in localStorage

### Week 1: Admin Dashboard (Days 3-5)
1. Test Users page completely
2. Test Notifications page
3. Test Pricing page
4. Test Team management
5. Test Groups and Offers

### Week 2: User Dashboard (Days 6-7)
1. Test deal feed loading
2. Test filters
3. Test daily limit tracking
4. Test membership upgrade
5. Test groups and referrals

### Week 2: API & Backend (Days 8-10)
1. Test all API endpoints
2. Verify Firestore data
3. Test Stripe integration
4. Verify scraper (fix sources)

### Week 3: End-to-End Testing (Days 11-14)
1. Full user journey: Signup → Browse → Upgrade → Refer → Gift
2. Full admin journey: Login → Manage → Send Notifications → Pricing
3. Stress testing: Create 100+ users, send bulk notifications
4. Production simulation: Use live URLs, test all features

---

## SIGN-OFF CHECKLIST

Before proceeding to iOS/Android development, verify:

- [ ] All 3 phases (Admin, User, Backend) tested and passing
- [ ] Zero critical bugs remaining
- [ ] Scraper working for all sources
- [ ] API response times < 2 seconds
- [ ] Stripe integration working in test mode
- [ ] Firestore data clean and properly indexed
- [ ] Security rules deployed and tested
- [ ] All error messages user-friendly
- [ ] Mobile-friendly UI verified (use phone/tablet browser)
- [ ] Production URLs working (not localhost)

**Sign-off Date:** _________________
**Tested By:** _________________
**Issues Found:** _________________
**Ready for Mobile Dev:** YES / NO

---

## NEXT STEPS AFTER TESTING

If all tests pass:
1. Deploy final version to production
2. Switch Stripe to live mode (update keys)
3. Create mobile development plan (Phase 6A: iOS, Phase 6B: Android)
4. Begin iOS and Android app development

If tests fail:
1. Document all failures
2. Prioritize by severity (Critical, High, Medium, Low)
3. Fix each issue systematically
4. Re-test after each fix
5. Repeat until all critical issues resolved
