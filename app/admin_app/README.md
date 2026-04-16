# DealHunter Admin App (Flutter)

Administrative dashboard for managing users, deals, team, notifications, and analytics.

## 📋 Project Overview

**Platforms:** iOS + Android  
**Framework:** Flutter  
**Language:** Dart  
**State Management:** Riverpod  
**Navigation:** GoRouter  
**Access:** Owner/Editor/Viewer roles with granular permissions

---

## 🎯 Features

### Authentication
- ✅ Email/password login
- ✅ Firebase authentication
- ✅ Owner/Editor/Viewer roles
- ✅ Granular permission system

### User Management
- ✅ View all users
- ✅ Search & filter (by tier, status)
- ✅ Edit user (name, tier, daily limit)
- ✅ Delete user
- ✅ Upgrade/downgrade subscriptions
- ✅ Bulk tier changes

### Deal Management
- ✅ View all deals
- ✅ Search & filter (source, status)
- ✅ Edit deal details
- ✅ Feature/unfeature deals
- ✅ Hide/show deals
- ✅ Mark as fake/suspicious/genuine
- ✅ Delete deals
- ✅ View deal analytics

### Team Management (Owner Only)
- ✅ Add team members
- ✅ Assign roles (Owner/Editor/Viewer)
- ✅ Edit permissions
- ✅ Remove members
- ✅ View last login

### Notifications
- ✅ Compose notifications
- ✅ Send to All Users / By Tier / By Group
- ✅ Preview before sending
- ✅ View notification history
- ✅ Track delivery stats

### Analytics
- ✅ Dashboard with key metrics
- ✅ User growth charts
- ✅ Revenue tracking
- ✅ Subscription distribution
- ✅ Engagement metrics

### Scraper Control
- ✅ View scraper status
- ✅ Pause/resume scraper
- ✅ View error logs
- ✅ Manual run trigger

---

## 🏗️ Folder Structure

```
lib/
├── screens/
│   ├── auth/
│   │   ├── admin_login_screen.dart
│   │   └── admin_signup_screen.dart
│   ├── dashboard/
│   │   ├── dashboard_screen.dart
│   │   └── quick_actions_screen.dart
│   ├── users/
│   │   ├── users_list_screen.dart
│   │   ├── user_detail_screen.dart
│   │   └── user_search_screen.dart
│   ├── deals/
│   │   ├── deals_list_screen.dart
│   │   ├── deal_detail_screen.dart
│   │   ├── deal_create_screen.dart
│   │   └── deal_source_screen.dart
│   ├── notifications/
│   │   ├── notifications_screen.dart
│   │   ├── notification_compose_screen.dart
│   │   └── notification_analytics_screen.dart
│   ├── team/
│   │   ├── team_screen.dart
│   │   ├── admin_detail_screen.dart
│   │   └── permissions_screen.dart
│   ├── tiers/
│   │   ├── tiers_screen.dart
│   │   └── referrals_screen.dart
│   ├── analytics/
│   │   ├── analytics_screen.dart
│   │   ├── revenue_screen.dart
│   │   └── engagement_screen.dart
│   ├── settings/
│   │   ├── admin_settings_screen.dart
│   │   └── audit_log_screen.dart
│   └── shared/
│       ├── app_shell.dart
│       └── error_screen.dart
├── services/
│   ├── api_client.dart
│   ├── auth_service.dart
│   ├── permission_service.dart
│   └── firebase_service.dart
├── providers/
│   ├── auth_provider.dart
│   ├── users_provider.dart
│   ├── deals_provider.dart
│   ├── notifications_provider.dart
│   ├── team_provider.dart
│   ├── analytics_provider.dart
│   ├── scraper_provider.dart
│   └── tiers_provider.dart
├── models/
│   ├── admin_user.dart
│   ├── user.dart
│   ├── deal.dart
│   ├── notification.dart
│   ├── tier.dart
│   └── statistics.dart
├── config/
│   ├── firebase_config.dart
│   ├── router.dart
│   └── theme.dart
├── widgets/
│   ├── admin_card.dart
│   ├── permission_badge.dart
│   ├── stat_tile.dart
│   ├── action_button.dart
│   ├── user_tier_dropdown.dart
│   └── data_table_with_actions.dart
├── utils/
│   ├── formatting.dart
│   ├── validators.dart
│   └── constants.dart
├── main.dart
└── index.dart
```

---

## 🚀 Getting Started

### Prerequisites
- Flutter 3.0+ installed
- Dart 3.0+ installed
- Firebase project created
- Admin user created in Firestore

### Installation

1. **Clone/Setup Project**
   ```bash
   cd app/admin_app
   flutter pub get
   ```

2. **Configure Firebase**
   - Download `GoogleService-Info.plist` (iOS)
   - Download `google-services.json` (Android)
   - Place in `ios/Runner/` and `android/app/`

3. **Setup Admin User**
   - Create first admin in Firebase Console
   - Email + password
   - Create `admin_users` collection in Firestore
   - Add document with role: "owner"

4. **Run App**
   ```bash
   flutter run
   ```

---

## 🎨 Admin Screens (10+ Total)

### Phase 1: COMPLETE ✅

#### 1. Admin Login Screen
- Email/password input
- Validation
- Error handling
- Password reset link

#### 2. Dashboard Screen
- Key metrics (users, deals, revenue)
- User growth chart (7 days)
- Revenue chart (7 days)
- Recent signups
- Scraper status
- Quick actions

### Phase 2: COMPLETE ✅

#### 3. Users Management Screen
- List all users (paginated)
- Search by email/name
- Filter by tier (Free, Trial, Premium, VIP)
- Toggle "Active Users Only"
- Edit user (name, tier, daily limit, status)
- Delete user
- Inline edit/delete buttons
- Show/hide count

#### 4. Deals Management Screen
- List all deals with thumbnails
- Search by title/source
- Filter by source (Amazon, Jumia, Noon)
- Filter by status (Active, Hidden, Expired)
- Featured deals toggle
- Edit deal (title, prices, verdict, featured)
- Toggle visibility (hide/show)
- Toggle featured (star)
- Delete deal
- Fraud verdict badges (✓ ⚠ ✗)

#### 5. Team Management Screen (Owner Only)
- List admin users
- Add team member (email, name, role)
- Edit member (change role)
- Remove member (with confirmation)
- Role badges (Owner, Editor, Viewer)
- Last login display

#### 6. Notifications Screen
- **Compose Tab:**
  - Title input (max 50 chars)
  - Message input (max 240 chars)
  - Target type selector (All/Tier/Group)
  - Live preview
  - Send button
- **History Tab:**
  - List sent notifications
  - Show: title, message, sent count, date
  - View delivery stats

### Phase 3: STUBS (To Build)

#### 7. Tiers Management Screen
- View all tiers
- Edit pricing
- Edit daily limits
- Show usage stats

#### 8. Analytics Details Screen
- User growth (30/90 day)
- Revenue trends
- Top deals by views
- Engagement metrics
- Export to CSV

#### 9. Settings/Preferences Screen
- Admin profile
- Change password
- Notification preferences
- Logout

#### 10. Audit Log Screen
- Who changed what
- When it changed
- Filter by action/admin
- Export logs

---

## 🔐 Permission System

### Three-Tier Roles

**OWNER**
- All permissions
- Can add/remove/edit team members
- Cannot be removed

**EDITOR**
- Assigned granular permissions:
  - Manage sources
  - Manage deals
  - Manage users
  - Send notifications
  - Run fake checker
  - View competitors
  - Pause scraper

**VIEWER**
- Read-only access
- Can view all data
- Cannot modify anything

### Permission Checks

```dart
// In every screen
if (!permissionService.canAccessPage('users', currentAdmin)) {
  return PermissionDeniedScreen();
}
```

---

## 🔌 API Integration

### Base URL
```
https://dealhunter-scraper.onrender.com/api/v1
```

### Key Endpoints
```
POST /auth/login                      → Admin login
GET /auth/me                          → Current admin
POST /auth/logout                     → Logout

GET /admin/users                      → List users
PUT /admin/users/{user_id}            → Update user
DELETE /admin/users/{user_id}         → Delete user

GET /admin/deals                      → List deals
PUT /admin/deals/{deal_id}            → Update deal
DELETE /admin/deals/{deal_id}         → Delete deal

POST /admin/notifications/send        → Send notification
GET /admin/notifications              → Notification history

GET /admin/team                       → List admins
POST /admin/team                      → Add admin
PUT /admin/team/{email}               → Update admin
DELETE /admin/team/{email}            → Remove admin

GET /admin/analytics                  → Dashboard stats
GET /admin/scraper-status             → Scraper info
POST /admin/scraper/pause             → Pause scraper
POST /admin/scraper/resume            → Resume scraper
```

---

## 🛠️ Development Workflow

### Adding New Permission

1. Add to `permission_service.dart`:
   ```dart
   bool canManageNewFeature(Map<String, dynamic> admin) {
     return admin['permissions'].contains('new_feature');
   }
   ```

2. Add to admin_users in Firestore:
   ```
   permissions: ["sources", "deals", "new_feature"]
   ```

3. Use in screen:
   ```dart
   if (!permissionService.canManageNewFeature(currentAdmin)) {
     return PermissionDeniedScreen();
   }
   ```

---

## 📊 State Management (Riverpod)

### Admin Providers
```dart
// Get current admin
final currentAdminProvider = FutureProvider<AdminUser?>(...);

// Get all users
final usersProvider = FutureProvider<List<UserModel>>(...);

// Update user
final updateUserProvider = FutureProvider.family<void, (String, Map)>(...);
```

---

## 🎨 Theme & Styling

### Professional Admin Theme
- Material Design 3
- Blue accent color
- Professional typography
- Data table styling
- Card layouts

---

## 📱 Build for Devices

### iOS
```bash
flutter build ios --release
```

### Android
```bash
flutter build appbundle --release
```

---

## 🧪 Testing

### Test Admin Login
1. Run app
2. Enter admin email
3. Enter admin password
4. Should see dashboard

### Test User Management
1. Go to Users screen
2. Search for user
3. Click edit
4. Change tier
5. Click save
6. Verify update in Firestore

### Test Permissions
1. Login as Editor (not Owner)
2. Go to Team screen
3. Should see "Owner Only" message
4. Try accessing Users (if allowed)

---

## 📦 Dependencies

```yaml
# State Management
flutter_riverpod: ^2.4.0

# Navigation
go_router: ^12.1.0

# Firebase
firebase_core: ^2.24.0
firebase_auth: ^4.15.0
cloud_firestore: ^4.14.0

# HTTP
dio: ^5.4.0

# Charts
fl_chart: ^0.65.0

# UI
flutter_material_design_icons: ^0.0.2
intl: ^0.19.0
```

---

## 🚀 Deployment

See: `../documentation/APP_STORE_SUBMISSION_GUIDE.md`

### Bundle ID
- iOS: `com.dealhunter.admin`
- Android: `com.dealhunter.admin`

### App Name
- "DealHunter Admin"

### App Store Notes
> This is an administrative tool for managing the DealHunter platform. Access restricted to authorized administrators only via Firebase Authentication.

---

## 📚 Implementation Guides

- **Phase 1 (Complete):** `../documentation/FLUTTER_ADMIN_APP_GUIDE.md`
- **Phase 2 (Complete):** `../documentation/PHASE_2_IMPLEMENTATION_COMPLETE.md`
- **Phase 3 (TODO):** `../documentation/ADMIN_APP_IMPLEMENTATION_ROADMAP.md`

---

## ✅ Status

### Phase 1: Core Infrastructure
- ✅ Firebase + API client
- ✅ Authentication
- ✅ Permission system
- ✅ Dashboard
- ✅ Navigation

### Phase 2: Primary Screens
- ✅ Users Management (COMPLETE)
- ✅ Deals Management (COMPLETE)
- ✅ Team Management (COMPLETE)
- ✅ Notifications (COMPLETE)

### Phase 3: Additional Features
- ⏳ Tiers Management
- ⏳ Analytics Details
- ⏳ Settings/Audit Log

---

**Status:** ✅ Phase 1 & 2 COMPLETE - Ready for Integration Testing

Last Updated: 2026-04-16
