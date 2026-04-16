# DealHunter Admin App - Implementation Roadmap

**Status:** Phase 1 Complete (Core Services & Dashboard)  
**Next Phase:** Build Remaining Screens  
**Target Completion:** 3-4 weeks

---

## WHAT HAS BEEN DELIVERED (This Session)

### ✅ Complete Documentation
- [x] FLUTTER_ADMIN_APP_GUIDE.md (6000+ lines) - Comprehensive architecture, screens, and features
- [x] ADMIN_APP_IMPLEMENTATION_ROADMAP.md (this file) - Step-by-step implementation plan

### ✅ Core Project Files
- [x] `admin_app_pubspec.yaml` - All dependencies configured
- [x] `admin_app_firebase_config.dart` - Firebase setup
- [x] `admin_app_services.dart` - API client, Auth, Permissions services
- [x] `admin_app_providers.dart` - Riverpod providers for all features
- [x] `admin_app_login_screen.dart` - Complete login screen with validation
- [x] `admin_app_dashboard_and_router.dart` - Dashboard + Navigation setup

### ✅ Functional Components
- [x] DioClient with interceptors (auth token, logging)
- [x] Firebase Auth integration (email/password)
- [x] Permission service (owner/editor/viewer roles)
- [x] Riverpod state management (8 provider families)
- [x] Navigation with GoRouter
- [x] Dashboard with analytics and charts
- [x] App shell with sidebar navigation
- [x] Error handling and validation

---

## PHASE STRUCTURE

### Phase 1: ✅ COMPLETE
**Core Infrastructure (This Session)**
- Firebase & API client setup
- Authentication flow
- Permission system
- Riverpod providers
- Login screen
- Dashboard
- Navigation

**Time:** 1 session (done)

### Phase 2: NEXT (2-3 weeks)
**Primary Admin Screens**
- Users Management (list, edit, delete, tier change)
- Deals Management (list, feature, hide, mark fake)
- Team Management (add, edit, remove admins)
- Notifications (compose and send)

### Phase 3: (1-2 weeks)
**Analytics & Control Screens**
- Detailed analytics dashboard
- Revenue tracking
- Scraper control & monitoring
- Audit logs

---

## IMPLEMENTATION ROADMAP (Phase 2)

### STEP 1: Create Users Management Screen (3-4 hours)

**File:** `lib/screens/users/users_list_screen.dart`

**Deliverables:**
1. [ ] Users table with columns: email, name, tier, daily_limit, registered, last_login, actions
2. [ ] Search by email (real-time filter)
3. [ ] Filter chips by tier (Free, Trial, Premium, VIP)
4. [ ] Edit user dialog:
   - Name field
   - Tier dropdown
   - Daily limit input
   - Status (Active/Inactive)
   - [Save] [Cancel] buttons
5. [ ] Delete user with confirmation
6. [ ] Pagination (50 users per page)
7. [ ] Permission check (requires 'users' permission)
8. [ ] Loading and error states

**Code Structure:**
```dart
class UsersListScreen extends ConsumerStatefulWidget {
  // Use usersProvider to fetch list
  // Use updateUserProvider to edit
  // Use deleteUserProvider to remove
  // Show error if user lacks 'users' permission
}
```

**Testing Checklist:**
- [ ] Fetch and display 50+ users
- [ ] Search filters results correctly
- [ ] Edit dialog saves changes to API
- [ ] Delete dialog appears and removes user
- [ ] Error message shows for permission denied
- [ ] Table scrolls horizontally on small screens

---

### STEP 2: Create Deals Management Screen (3-4 hours)

**File:** `lib/screens/deals/deals_list_screen.dart`

**Deliverables:**
1. [ ] Deals table with columns: thumbnail, title, price, discount, site, status, actions
2. [ ] Search deals by title/keyword
3. [ ] Filter by source (Amazon, Jumia, Noon, etc.)
4. [ ] Filter by status (Active, Hidden, Expired, Fake)
5. [ ] Inline actions:
   - [View] → Open deal details
   - [Edit] → Edit dialog
   - [Hide/Show] → Toggle visibility
   - [Delete] → Remove deal
   - [Feature] → Pin to top
6. [ ] Edit deal dialog:
   - Title, URL, description
   - Prices (current, original)
   - Image URL
   - Category
   - Fake verdict dropdown (Genuine, Suspicious, Fake)
   - Featured toggle
   - [Save] [Cancel]
7. [ ] Permission check (requires 'deals' permission)

**Code Structure:**
```dart
class DealsListScreen extends ConsumerStatefulWidget {
  // Use dealsProvider for list
  // Use updateDealProvider for edits
  // Use deleteDealProvider for removal
}
```

**Testing Checklist:**
- [ ] Display 50+ deals with thumbnails
- [ ] Search filters by title
- [ ] Source filter works
- [ ] Feature toggle changes deal order
- [ ] Mark as fake updates verdict badge
- [ ] Bulk hide (from same source) works

---

### STEP 3: Create Team Management Screen (2-3 hours)

**File:** `lib/screens/team/team_screen.dart`

**Deliverables (Owner Only):**
1. [ ] Team members table: email, name, role, last_login, actions
2. [ ] Add team member button → dialog:
   - Email *
   - Name *
   - Role: Owner | Editor | Viewer
   - [Add] [Cancel]
3. [ ] Edit team member → permissions dialog:
   - Role selector (auto-select for new members)
   - Checkboxes for each permission:
     * Manage Sources
     * Manage Deals
     * Manage Users
     * Send Notifications
     * Manage Team
     * View Analytics
     * Pause Scraper
   - Role: Owner has all checked (disabled)
   - [Save] [Cancel]
4. [ ] Remove team member (with confirmation)
5. [ ] Display "Owner" badge on owner account
6. [ ] Last login timestamp

**Code Structure:**
```dart
class TeamScreen extends ConsumerStatefulWidget {
  // Check isOwner() - show "Owner only" if not
  // Use teamProvider to fetch members
  // Use addTeamMemberProvider to create
  // Use updateTeamMemberProvider to edit permissions
  // Use removeTeamMemberProvider to delete
}
```

**Testing Checklist:**
- [ ] Non-owner cannot access screen
- [ ] Add new member with specific permissions
- [ ] Edit member permissions
- [ ] Owner role locks all checkboxes
- [ ] Remove member with confirmation
- [ ] Owner cannot remove self

---

### STEP 4: Create Notifications Screen (2-3 hours)

**File:** `lib/screens/notifications/notifications_compose_screen.dart`

**Deliverables:**
1. [ ] Compose notification dialog:
   - Title input * (short title)
   - Message input * (up to 240 chars, char counter)
   - Target type: [All Users] [By Tier] [By Group] [Custom]
   - Tier selector (if By Tier)
   - Group selector (if By Group)
   - Schedule: [Now] [Custom Date/Time]
   - [Preview] [Send] [Cancel]
2. [ ] Preview modal showing notification as user will see it
3. [ ] Send success message with count
4. [ ] Send error with retry option

**File:** `lib/screens/notifications/notifications_history_screen.dart`

**Deliverables:**
1. [ ] Notification history table: title, message, sent_count, opened_count, sent_at, [View Stats]
2. [ ] View stats dialog:
   - Sent: 5,000
   - Opened: 2,150 (43%)
   - Failed: 50
   - Sent at: timestamp
3. [ ] Pagination

**Code Structure:**
```dart
class NotificationsScreen extends ConsumerStatefulWidget {
  // Use sendNotificationProvider to send
  // Use notificationsProvider to fetch history
  // Check permission before showing
}
```

**Testing Checklist:**
- [ ] Compose and send notification
- [ ] Permission check (requires 'notifications')
- [ ] Character counter works
- [ ] Preview shows correctly
- [ ] Tier/group selectors populate
- [ ] History loads previous notifications

---

### STEP 5: Implement Missing Screen Stubs (1-2 hours)

Create empty screens for remaining features to complete navigation:

**Files:**
- [ ] `lib/screens/tiers/tiers_screen.dart` - Tier management
- [ ] `lib/screens/analytics/analytics_screen.dart` - Detailed analytics
- [ ] `lib/screens/analytics/revenue_screen.dart` - Revenue tracking
- [ ] `lib/screens/settings/admin_settings_screen.dart` - Admin preferences
- [ ] `lib/screens/settings/audit_log_screen.dart` - Action history
- [ ] `lib/screens/deals/deal_detail_screen.dart` - View single deal

Each can be a simple placeholder with:
```dart
class XxxScreen extends ConsumerWidget {
  @override
  Widget build(BuildContext context, WidgetRef ref) {
    return Scaffold(
      appBar: AppBar(title: Text('Xxx')),
      body: Center(child: Text('Coming Soon')),
    );
  }
}
```

---

## TESTING STRATEGY FOR PHASE 2

### Authentication Testing
- [ ] Login with owner → full access to all screens
- [ ] Login with editor → limited access per permissions
- [ ] Login with viewer → read-only view (no edit buttons)
- [ ] Wrong password → error message
- [ ] Non-admin user → "Access denied"
- [ ] Token expiry → redirect to login

### Permission Testing
- [ ] Editor without 'users' → Users screen shows "Access Denied"
- [ ] Viewer → Edit buttons hidden, delete buttons hidden
- [ ] Owner → Can always access everything
- [ ] Page shows correct error for each permission

### Functionality Testing
**Users Screen:**
- [ ] Fetch and display users
- [ ] Search works (real-time filter)
- [ ] Filter by tier works
- [ ] Edit user → API updated
- [ ] Delete user → confirm dialog → removed from list

**Deals Screen:**
- [ ] Fetch and display deals
- [ ] Search by title
- [ ] Filter by source
- [ ] Filter by status
- [ ] Feature deal (moves to top)
- [ ] Mark as fake (verdict changes)
- [ ] Delete deal

**Team Screen (Owner):**
- [ ] Add new admin user
- [ ] Edit admin permissions
- [ ] Delete admin user
- [ ] Cannot delete self

**Notifications Screen:**
- [ ] Compose notification
- [ ] Send to all users
- [ ] Send to specific tier
- [ ] View history
- [ ] See delivery stats

### UI Testing
- [ ] All screens responsive (resize window)
- [ ] Tables scroll horizontally on small screens
- [ ] Dialogs are modal (block background)
- [ ] Buttons disabled during loading
- [ ] Error messages appear for API failures
- [ ] Success snackbars appear for actions

---

## API ENDPOINTS REQUIRED (Backend)

**Already implemented in server.py:**
- [x] POST /api/v1/admin/check-auth
- [x] GET /api/v1/admin/users (filters: page, limit, tier, search)
- [x] PUT /api/v1/admin/users/{user_id}
- [x] DELETE /api/v1/admin/users/{user_id}
- [x] GET /api/v1/admin/deals (filters: status, source, search)
- [x] PUT /api/v1/admin/deals/{deal_id}
- [x] DELETE /api/v1/admin/deals/{deal_id}
- [x] POST /api/v1/admin/notifications/send
- [x] GET /api/v1/admin/notifications
- [x] GET /api/v1/admin/team
- [x] POST /api/v1/admin/team
- [x] PUT /api/v1/admin/team/{email}
- [x] DELETE /api/v1/admin/team/{email}
- [x] GET /api/v1/admin/analytics
- [x] GET /api/v1/admin/scraper-status

**Verify all endpoints return correct JSON schema matching our models.**

---

## OPTIONAL: Phase 3 Screens (After Phase 2)

Not critical for MVP, but nice-to-have:

1. **Tiers Management Screen**
   - View/edit subscription tiers
   - Change pricing
   - View usage (users per tier)

2. **Detailed Analytics**
   - User growth chart (30/90 days)
   - Revenue trend
   - Subscription distribution (pie chart)
   - Top deals by views
   - Export to CSV

3. **Audit Log**
   - Who changed what and when
   - Filter by action type (user_edited, deal_hidden, etc.)
   - Filter by admin
   - Export activity log

4. **Settings**
   - Admin profile info
   - Change password
   - Notification preferences
   - Logout

---

## QUICK START (Copy-Paste Instructions)

### 1. Clone User App (Code Reuse)

Copy these files from user app to admin app:
```bash
cp user_app/lib/models/user.dart admin_app/lib/models/
cp user_app/lib/models/deal.dart admin_app/lib/models/
```

Share models between apps to reduce duplication.

### 2. Setup Firebase Console

1. Create new iOS/Android projects in Firebase Console
2. Bundle ID for iOS: `com.dealhunter.admin`
3. Package ID for Android: `com.dealhunter.admin`
4. Download `GoogleService-Info.plist` (iOS)
5. Download `google-services.json` (Android)

### 3. Update Firestore Security Rules

Current rules should allow:
```
read/write admin_users: authenticated admins only
read all collections: authenticated admins
write all collections: based on role/permissions
```

### 4. Build and Test

```bash
cd dealhunter_admin
flutter pub get
flutter run
```

Test login with owner account:
- Email: your-admin-email@example.com
- Password: (from Firebase Auth)

---

## ESTIMATED TIMELINE (Phase 2)

| Screen | Time | Dependencies |
|--------|------|--------------|
| Users Management | 3-4h | usersProvider ✅ |
| Deals Management | 3-4h | dealsProvider ✅ |
| Team Management | 2-3h | teamProvider ✅ |
| Notifications | 2-3h | sendNotificationProvider ✅ |
| Screen Stubs | 1-2h | - |
| **Total** | **11-17h** | **1-2 weeks** |

---

## COMMON ISSUES & SOLUTIONS

### Issue: "Cannot access admin features"
**Cause:** User is not in `admin_users` Firestore collection  
**Solution:** Manually create document in Firebase Console with role="owner"

### Issue: API returns 401 Unauthorized
**Cause:** Token expired or invalid  
**Solution:** Token refresh in DioClient interceptor (auto-refresh before request)

### Issue: Dialogs not showing
**Cause:** Missing `showDialog()` or `showGeneralDialog()`  
**Solution:** Wrap dialog in `showDialog(context: context, builder: ...)`

### Issue: Permission checks not working
**Cause:** Role/permissions not cached properly  
**Solution:** Call `clearCache()` after permission changes, refresh provider

---

## FILES CHECKLIST

### Already Created (Phase 1)
- [x] `pubspec.yaml` - Dependencies
- [x] `firebase_config.dart` - Firebase init
- [x] `services/` - API client, Auth, Permissions
- [x] `providers/` - Riverpod state management
- [x] `screens/auth/admin_login_screen.dart` - Login
- [x] `screens/dashboard/dashboard_screen.dart` - Analytics
- [x] `screens/shared/app_shell.dart` - Navigation
- [x] `config/router.dart` - GoRouter setup
- [x] `config/theme.dart` - Material Design 3
- [x] `main.dart` - App entry point

### To Create (Phase 2)
- [ ] `screens/users/users_list_screen.dart`
- [ ] `screens/deals/deals_list_screen.dart`
- [ ] `screens/team/team_screen.dart`
- [ ] `screens/notifications/notifications_compose_screen.dart`
- [ ] `screens/notifications/notifications_history_screen.dart`
- [ ] `screens/deals/deal_create_screen.dart`
- [ ] `screens/deals/deal_detail_screen.dart`
- [ ] `widgets/` - Reusable components
- [ ] `utils/` - Formatting, validation helpers

### To Create (Phase 3)
- [ ] `screens/tiers/tiers_screen.dart`
- [ ] `screens/analytics/revenue_screen.dart`
- [ ] `screens/analytics/engagement_screen.dart`
- [ ] `screens/settings/audit_log_screen.dart`
- [ ] `screens/settings/admin_settings_screen.dart`

---

## NEXT IMMEDIATE STEPS

1. **Copy files from this conversation** to your admin_app project
2. **Create Firebase projects** for iOS and Android (admin bundle IDs)
3. **Update pubspec.yaml** with your Firebase config
4. **Test login screen** - should redirect to dashboard on success
5. **Build users_list_screen** - primary feature for admin
6. **Test with real data** - fetch 50+ users from API

---

## SUCCESS CRITERIA (Phase 2)

- [ ] Users can login (owner, editor, viewer)
- [ ] Dashboard shows analytics and charts
- [ ] Users screen shows list with search/filter
- [ ] Users screen allows edit/delete with permission checks
- [ ] Deals screen shows list with status/source filters
- [ ] Deals screen allows feature/hide/mark-fake
- [ ] Team screen (owner) can add/remove/edit admins
- [ ] Notifications screen can send with target selection
- [ ] All CRUD operations logged in Firestore
- [ ] Error messages show for API failures
- [ ] Loading states show for async operations
- [ ] Permission denied screen shows for unauthorized access

---

**Ready to build Phase 2! 🚀**

For questions about any screen implementation, refer back to FLUTTER_ADMIN_APP_GUIDE.md for detailed specs.
