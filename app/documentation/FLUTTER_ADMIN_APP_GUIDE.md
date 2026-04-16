# DealHunter Admin App - Complete Implementation Guide

**Status:** Ready to Build  
**Target Platforms:** iOS + Android  
**Framework:** Flutter (Shared codebase with user app)  
**Date:** 2026-04-16

---

## TABLE OF CONTENTS
1. [Architecture Overview](#architecture-overview)
2. [Project Structure](#project-structure)
3. [Authentication & Permissions](#authentication--permissions)
4. [Admin Screens](#admin-screens)
5. [API Integration](#api-integration)
6. [Implementation Steps](#implementation-steps)
7. [Testing Strategy](#testing-strategy)

---

## ARCHITECTURE OVERVIEW

### Option A: Separate Admin App (RECOMMENDED)
- **Pros:** Clear separation, dedicated admin features, lightweight package
- **Cons:** Code duplication, separate build process
- **Best for:** Security isolation, admin-only features

### Option B: Shared Codebase with Role-Based Routing
- **Pros:** Code reuse, single package, easier maintenance
- **Cons:** Larger app, more conditional logic
- **Best for:** Teams with tight code sharing requirements

**RECOMMENDATION:** Option A (Separate Admin App)
- Create `dealhunter_admin/` as separate Flutter project
- Share common packages (models, API client, Firebase config)
- Package as `DealHunter Admin` on app stores
- Different bundle ID from user app

---

## PROJECT STRUCTURE

```
dealhunter_admin/
├── ios/                          # iOS configuration
├── android/                       # Android configuration
├── lib/
│   ├── main.dart                # App entry point
│   ├── config/
│   │   ├── firebase_config.dart  # Firebase initialization
│   │   ├── router.dart           # GoRouter navigation
│   │   └── theme.dart            # Admin theme (professional)
│   ├── models/
│   │   ├── admin_user.dart       # Admin user model
│   │   ├── user.dart             # End-user model
│   │   ├── deal.dart             # Deal model
│   │   ├── notification.dart     # Notification model
│   │   ├── tier.dart             # Tier/Subscription model
│   │   ├── group.dart            # User group model
│   │   └── statistic.dart        # Analytics data
│   ├── services/
│   │   ├── api_client.dart       # Dio + interceptors (shared)
│   │   ├── auth_service.dart     # Admin Firebase Auth
│   │   ├── permission_service.dart # Permission checking
│   │   └── firebase_service.dart # Firestore access
│   ├── providers/
│   │   ├── auth_provider.dart    # Authentication state (Riverpod)
│   │   ├── users_provider.dart   # End-users list (CRUD)
│   │   ├── deals_provider.dart   # Deals management
│   │   ├── notifications_provider.dart # Send notifications
│   │   ├── statistics_provider.dart    # Analytics data
│   │   ├── tiers_provider.dart   # Subscription tiers
│   │   └── team_provider.dart    # Admin team management
│   ├── screens/
│   │   ├── auth/
│   │   │   ├── admin_login_screen.dart
│   │   │   └── admin_signup_screen.dart  (owner only)
│   │   ├── dashboard/
│   │   │   ├── dashboard_screen.dart     # Analytics overview
│   │   │   ├── monitor_screen.dart       # Real-time monitoring
│   │   │   └── quick_actions_screen.dart # Pause scraper, send notifications
│   │   ├── users/
│   │   │   ├── users_list_screen.dart    # All end-users
│   │   │   ├── user_detail_screen.dart   # Edit user, change tier
│   │   │   ├── user_search_screen.dart   # Find users by email/phone
│   │   │   └── bulk_actions_screen.dart  # Upgrade tier for group, etc
│   │   ├── deals/
│   │   │   ├── deals_list_screen.dart    # All deals
│   │   │   ├── deal_detail_screen.dart   # View/edit deal
│   │   │   ├── deal_create_screen.dart   # Add new deal
│   │   │   └── deal_source_screen.dart   # Manage sources & scraping
│   │   ├── notifications/
│   │   │   ├── notifications_screen.dart # Send push notifications
│   │   │   ├── notification_compose_screen.dart # Compose message
│   │   │   └── notification_analytics_screen.dart # Delivery stats
│   │   ├── team/
│   │   │   ├── team_screen.dart          # Manage admin users
│   │   │   ├── admin_detail_screen.dart  # Edit admin, permissions
│   │   │   └── permissions_screen.dart   # Assign granular permissions
│   │   ├── tiers/
│   │   │   ├── tiers_screen.dart         # View/edit subscription tiers
│   │   │   └── referrals_screen.dart     # Manage referral rewards
│   │   ├── analytics/
│   │   │   ├── analytics_screen.dart     # Charts & graphs
│   │   │   ├── revenue_screen.dart       # Revenue tracking (Stripe)
│   │   │   └── engagement_screen.dart    # User engagement metrics
│   │   ├── settings/
│   │   │   ├── admin_settings_screen.dart # Admin preferences
│   │   │   └── audit_log_screen.dart     # Who changed what
│   │   └── shared/
│   │       ├── app_shell.dart            # Main navigation scaffold
│   │       └── error_screen.dart
│   ├── widgets/
│   │   ├── admin_card.dart
│   │   ├── permission_badge.dart
│   │   ├── stat_tile.dart
│   │   ├── action_button.dart
│   │   ├── permission_checkbox_group.dart
│   │   ├── user_tier_dropdown.dart
│   │   └── data_table_with_actions.dart
│   └── utils/
│       ├── formatting.dart
│       ├── validators.dart
│       └── constants.dart
├── pubspec.yaml
├── .env.example
└── README.md
```

---

## AUTHENTICATION & PERMISSIONS

### Admin Login Flow

```
Login Screen
    ↓
Email + Password → Firebase Auth
    ↓
Check admin_users collection
    ↓
Load admin role + permissions
    ↓
Store JWT token in secure storage
    ↓
Redirect to Dashboard (or Permission Denied)
```

### Three-Tier Permission System

```
┌─────────────────────────────────────────────────────────┐
│ OWNER (Full control)                                    │
│ - Manage all team members                               │
│ - Access all features                                   │
│ - Can NOT be removed by anyone                          │
└─────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────┐
│ EDITOR (Can modify data)                                │
│ - Assigned specific permissions (see below)             │
│ - Can view all data                                     │
│ - Actions are logged with their email                   │
└─────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────┐
│ VIEWER (Read-only)                                      │
│ - Can view dashboards, users, deals, analytics          │
│ - Can NOT make changes                                  │
│ - Cannot manage team or settings                        │
└─────────────────────────────────────────────────────────┘
```

### Granular Permissions

```javascript
{
  sources: boolean,           // Can manage scraping sources + pause scraper
  deals: boolean,             // Can feature/hide/delete deals
  users: boolean,             // Can view/edit users, change tiers
  notifications: boolean,     // Can send push notifications
  checker: boolean,           // Can run fake deal checker
  competitors: boolean,       // Can view competitor analysis
  scraper_control: boolean,   // Can pause/resume scraper
  team: boolean,              // Can add/remove/edit team members (owner only)
  tiers: boolean,             // Can create/edit subscription tiers
  analytics: boolean          // Can view analytics + revenue
}
```

### Permission Service

```dart
class PermissionService {
  Future<bool> canAccessPage(String pageName) async {
    final admin = await getCurrentAdmin();
    final permissions = admin.permissions;
    
    final pagePermissions = {
      'users': 'users',
      'deals': 'deals',
      'sources': 'sources',
      'notifications': 'notifications',
      'checker': 'checker',
      'team': 'team',
      'tiers': 'tiers',
      'analytics': 'analytics',
    };
    
    return permissions.contains(pagePermissions[pageName]);
  }
  
  bool canEditDeal() => currentAdmin.permissions.contains('deals');
  bool canSendNotification() => currentAdmin.permissions.contains('notifications');
  bool canPauseScraper() => currentAdmin.permissions.contains('scraper_control');
  bool canManageTeam() => currentAdmin.role == 'owner';
}
```

---

## ADMIN SCREENS

### 1. Admin Login Screen

**File:** `lib/screens/auth/admin_login_screen.dart`

**Features:**
- Email + Password input with validation
- Error messages for invalid credentials
- "Forgot Password" link (Firebase password reset)
- Link to request admin access (if user not in admin_users)
- Remember email option (local storage)
- Loading state during authentication

**Code:**
```dart
class AdminLoginScreen extends ConsumerWidget {
  const AdminLoginScreen({Key? key}) : super(key: key);

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final authService = ref.read(authServiceProvider);
    final isLoading = ref.watch(isLoadingProvider);
    final emailController = TextEditingController();
    final passwordController = TextEditingController();

    return Scaffold(
      appBar: AppBar(
        title: const Text('DealHunter Admin'),
        centerTitle: true,
      ),
      body: Center(
        child: SingleChildScrollView(
          padding: EdgeInsets.all(24),
          child: Column(
            children: [
              Icon(Icons.admin_panel_settings, size: 64, color: Colors.blue),
              SizedBox(height: 24),
              Text('Admin Portal', style: Theme.of(context).textTheme.headlineSmall),
              SizedBox(height: 32),
              
              TextField(
                controller: emailController,
                decoration: InputDecoration(
                  labelText: 'Email',
                  border: OutlineInputBorder(),
                  prefixIcon: Icon(Icons.email),
                ),
                keyboardType: TextInputType.emailAddress,
              ),
              SizedBox(height: 16),
              
              TextField(
                controller: passwordController,
                decoration: InputDecoration(
                  labelText: 'Password',
                  border: OutlineInputBorder(),
                  prefixIcon: Icon(Icons.lock),
                  suffixIcon: Icon(Icons.visibility),
                ),
                obscureText: true,
              ),
              SizedBox(height: 24),
              
              SizedBox(
                width: double.infinity,
                child: ElevatedButton(
                  onPressed: isLoading ? null : () async {
                    try {
                      await authService.login(
                        emailController.text,
                        passwordController.text,
                      );
                      // Navigate to dashboard
                    } catch (e) {
                      ScaffoldMessenger.of(context).showSnackBar(
                        SnackBar(content: Text('Login failed: $e')),
                      );
                    }
                  },
                  child: isLoading
                    ? CircularProgressIndicator()
                    : Text('LOGIN'),
                ),
              ),
              
              TextButton(
                onPressed: () {
                  // Show forgot password dialog
                },
                child: Text('Forgot Password?'),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
```

---

### 2. Dashboard Screen (Analytics Overview)

**File:** `lib/screens/dashboard/dashboard_screen.dart`

**Features:**
- Key metrics (total users, deals scraped today, revenue, active subscriptions)
- Charts (user growth, daily revenue, subscription tiers)
- Recent user signups table
- Recent deal additions
- System health (scraper status, API latency, Firestore writes/day)
- Quick action buttons (pause scraper, send notification)

**Widgets:**
- `StatTile`: Single stat (title, value, trend icon)
- `ChartCard`: Mini line/bar chart
- `RecentActivityTable`: Scrollable table of recent events

**Mockup:**
```
┌─────────────────────────────────────────┐
│ 📊 DASHBOARD                            │
├─────────────────────────────────────────┤
│                                         │
│  [👥 12,543 Users] [💰 EGP 145,200]   │
│  [📦 2,847 Deals] [🔄 856 Active Sub] │
│                                         │
│  ┌─ User Growth (7 days) ───────────┐ │
│  │ Graph showing upward trend        │ │
│  └───────────────────────────────────┘ │
│                                         │
│  ┌─ Recent Signups ──────────────────┐ │
│  │ email@ex | Free | 2h ago | [Edit]│ │
│  │ email@ex | Trial| 4h ago | [Edit]│ │
│  └───────────────────────────────────┘ │
│                                         │
│  ⚡ Scraper: RUNNING (last: 2m ago)   │
│  🌐 API Health: GOOD (150ms avg)      │
│                                         │
└─────────────────────────────────────────┘
```

---

### 3. Users Management Screen

**File:** `lib/screens/users/users_list_screen.dart`

**Features:**
- Table view (email, name, tier, daily limit, referrals, group, registered, last login, actions)
- Search by email/phone
- Filter by tier (Free, Trial, Premium, VIP)
- Filter by registration date range
- Inline actions: [Edit] [Upgrade] [Delete]
- Bulk actions: Select multiple → Upgrade all to Premium
- Pagination (50 users per page)

**Edit User Dialog:**
- Name
- Email (read-only)
- Current Tier [dropdown]
- Custom Daily Limit [input]
- Group assignment [dropdown]
- Status [Active/Inactive]
- Notes [text area]
- [Save] [Cancel]

**Code (DataTable):**
```dart
class UsersListScreen extends ConsumerWidget {
  const UsersListScreen({Key? key}) : super(key: key);

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final usersAsync = ref.watch(usersProvider);
    final permissionService = ref.read(permissionServiceProvider);

    if (!permissionService.canAccessPage('users')) {
      return ErrorScreen(message: 'Access Denied');
    }

    return Scaffold(
      appBar: AppBar(title: Text('Users Management')),
      body: usersAsync.when(
        data: (users) => Column(
          children: [
            Padding(
              padding: EdgeInsets.all(16),
              child: TextField(
                decoration: InputDecoration(
                  labelText: 'Search users',
                  border: OutlineInputBorder(),
                  prefixIcon: Icon(Icons.search),
                ),
                onChanged: (query) {
                  // Filter users
                },
              ),
            ),
            Expanded(
              child: SingleChildScrollView(
                scrollDirection: Axis.horizontal,
                child: DataTable(
                  columns: [
                    DataColumn(label: Text('Email')),
                    DataColumn(label: Text('Name')),
                    DataColumn(label: Text('Tier')),
                    DataColumn(label: Text('Daily Limit')),
                    DataColumn(label: Text('Registered')),
                    DataColumn(label: Text('Actions')),
                  ],
                  rows: users.map((user) {
                    return DataRow(cells: [
                      DataCell(Text(user.email)),
                      DataCell(Text(user.name)),
                      DataCell(Chip(label: Text(user.tier))),
                      DataCell(Text('${user.dailyDealLimit} deals')),
                      DataCell(Text(formatDate(user.registeredAt))),
                      DataCell(Row(
                        children: [
                          IconButton(
                            icon: Icon(Icons.edit),
                            onPressed: () => _showEditDialog(context, user),
                          ),
                          IconButton(
                            icon: Icon(Icons.delete),
                            onPressed: () => _deleteUser(user.id),
                          ),
                        ],
                      )),
                    ]);
                  }).toList(),
                ),
              ),
            ),
          ],
        ),
        loading: () => Center(child: CircularProgressIndicator()),
        error: (err, stack) => ErrorScreen(message: err.toString()),
      ),
    );
  }
}
```

---

### 4. Deals Management Screen

**File:** `lib/screens/deals/deals_list_screen.dart`

**Features:**
- List all deals (image thumbnail, title, price, discount, site, status)
- Search deals by title/keyword
- Filter by source (Amazon, Jumia, Noon)
- Filter by status (Active, Hidden, Expired, Fake)
- Inline actions: [View] [Edit] [Hide/Show] [Delete]
- Feature deal (pin to top)
- Mark as fake (update fake_verdict)
- Bulk actions: Hide all deals from source X

**Edit Deal Dialog:**
- Title, URL, description
- Current price, original price, discount %
- Image URL
- Category
- Site/Source
- Visibility toggle (hidden/active)
- Featured toggle
- Fake verdict (Genuine, Suspicious, Fake)
- [Save] [Cancel]

---

### 5. Notifications Management Screen

**File:** `lib/screens/notifications/notifications_screen.dart`

**Features:**
- Compose notification message
- Target audience (all users, specific tier, specific group)
- Schedule (send now, schedule for later)
- Preview message
- Send analytics (messages sent, opened, failed)
- Notification history (view past notifications)

**Compose Dialog:**
- Title * (short)
- Message * (up to 240 chars)
- Target: [All Users] [By Tier] [By Group] [Custom List]
- Tier selector (if By Tier)
- Group selector (if By Group)
- Schedule time [Now] [Custom Date/Time]
- [Preview] [Send] [Cancel]

**History View:**
```
Message | Sent At | Count | Opened | Failed | View Stats
```

---

### 6. Team Management Screen

**File:** `lib/screens/team/team_screen.dart`

**Features (Owner Only):**
- List all admin users (email, name, role, last login)
- Add new team member (email, name, role, permissions)
- Edit team member (change role, permissions, status)
- Remove team member (with confirmation)
- View admin action audit log

**Permissions Assignment:**
- Checkbox group for each permission
- Role selector (Owner/Editor/Viewer)
- Owner role locks all checkboxes (has all permissions)
- Viewer role has no edit checkboxes
- Real-time permission preview

**Code:**
```dart
class TeamScreen extends ConsumerWidget {
  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final currentAdmin = ref.watch(currentAdminProvider);

    // Only owners can access this
    if (currentAdmin?.role != 'owner') {
      return ErrorScreen(message: 'Owners only');
    }

    return Scaffold(
      appBar: AppBar(title: Text('Admin Team')),
      floatingActionButton: FloatingActionButton(
        onPressed: () => _showAddMemberDialog(context),
        child: Icon(Icons.add),
      ),
      body: // Team member list
    );
  }
}
```

---

### 7. Tiers Management Screen

**File:** `lib/screens/tiers/tiers_screen.dart`

**Features:**
- View all subscription tiers (Free, Trial, Premium, VIP)
- Edit tier pricing (monthly price in EGP)
- Edit daily deal limit per tier
- View features for each tier
- Create custom tier (with custom daily limit)
- View tier usage (X users on Premium)

**Tier Card:**
```
┌──────────────────────┐
│ 🏷️  PREMIUM         │
├──────────────────────┤
│ Price: EGP 29/month  │
│ Daily Limit: 500     │
│ Users: 2,847         │
│ Features:            │
│   ✓ Advanced filters │
│   ✓ API access       │
│   ✓ Priority support │
│ [Edit] [Delete]      │
└──────────────────────┘
```

---

### 8. Analytics Screen

**File:** `lib/screens/analytics/analytics_screen.dart`

**Features:**
- User growth chart (7/30/90 days)
- Revenue chart (Stripe data)
- Top deals by views
- User engagement (daily active users, deal views/user)
- Subscription distribution (pie chart)
- Geographic data (if available)
- Export to CSV

---

### 9. Scraper Control Screen

**File:** `lib/screens/dashboard/quick_actions_screen.dart`

**Features:**
- Scraper status (running/paused)
- Pause button (with confirm dialog)
- Resume button
- Show last successful run timestamp
- Show error log if last run failed
- Manual run button (start scraper now)
- Scraper statistics (deals added today, processing time)

**Code:**
```dart
class ScraperControlCard extends ConsumerWidget {
  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final scraperStatus = ref.watch(scraperStatusProvider);
    final permissionService = ref.read(permissionServiceProvider);

    if (!permissionService.canAccessPage('scraper_control')) {
      return SizedBox.shrink();
    }

    return Card(
      child: Padding(
        padding: EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                Text('Scraper Status'),
                Chip(
                  label: Text(scraperStatus.isRunning ? 'RUNNING' : 'PAUSED'),
                  backgroundColor: scraperStatus.isRunning ? Colors.green : Colors.orange,
                  labelStyle: TextStyle(color: Colors.white),
                ),
              ],
            ),
            SizedBox(height: 16),
            Text('Last run: ${formatDate(scraperStatus.lastRun)}'),
            SizedBox(height: 16),
            Row(
              children: [
                ElevatedButton(
                  onPressed: scraperStatus.isRunning ? () => _pauseScraper(ref) : null,
                  child: Text('Pause'),
                ),
                SizedBox(width: 8),
                ElevatedButton(
                  onPressed: !scraperStatus.isRunning ? () => _resumeScraper(ref) : null,
                  child: Text('Resume'),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }
}
```

---

## API INTEGRATION

### Admin-Specific Endpoints

```
GET /api/v1/admin/check-auth
  - Returns: Current admin user + permissions
  - Headers: Authorization: Bearer token
  - Response: { email, name, role, permissions, last_login }

POST /api/v1/admin/logout
  - Logout and revoke token
  - Returns: { success: true }

GET /api/v1/admin/users
  - List all end-users
  - Query params: ?page=1&limit=50&tier=premium&search=email
  - Returns: { users: [], total: 5000, page: 1 }

PUT /api/v1/admin/users/{user_id}
  - Update user (tier, daily_limit, group, status)
  - Input: { tier, daily_deal_limit, group_name, status }
  - Logs: { edited_by, edited_at }

DELETE /api/v1/admin/users/{user_id}
  - Soft-delete user
  - Returns: { success: true, deleted_at }

GET /api/v1/admin/deals
  - List all deals
  - Query: ?status=active&source=amazon&search=keyword
  - Returns: { deals: [], total: 50000, filters: {...} }

PUT /api/v1/admin/deals/{deal_id}
  - Update deal (hidden, featured, fake_verdict)
  - Input: { hidden, featured, fake_verdict }

POST /api/v1/admin/notifications/send
  - Send push notification
  - Input: { title, message, target_type, target_id, schedule_at }
  - Returns: { notification_id, sent_count }

GET /api/v1/admin/team
  - List admin users
  - Returns: { admins: [] }
  - Requires: owner role

POST /api/v1/admin/team
  - Add admin user
  - Input: { email, name, role, permissions }
  - Returns: { admin_id, created_at }

PUT /api/v1/admin/team/{email}
  - Update admin user
  - Input: { role, permissions, status }

DELETE /api/v1/admin/team/{email}
  - Remove admin user
  - Requires: owner role

GET /api/v1/admin/analytics
  - Get analytics data
  - Query: ?metric=user_growth&period=7d
  - Returns: { data: [], labels: [] }

GET /api/v1/admin/scraper-status
  - Check scraper state
  - Returns: { status, last_run, next_run, error_log }

POST /api/v1/admin/scraper/pause
  - Pause scraper
  - Input: { reason }
  - Returns: { paused_at, paused_by }

POST /api/v1/admin/scraper/resume
  - Resume scraper
  - Returns: { resumed_at }

POST /api/v1/admin/scraper/run
  - Start manual scraper run
  - Returns: { job_id, started_at }
```

---

## IMPLEMENTATION STEPS

### STEP 1: Setup Admin App Project
```bash
# Create new Flutter project
flutter create dealhunter_admin

cd dealhunter_admin

# Add dependencies to pubspec.yaml
flutter pub add flutter_riverpod firebase_core firebase_auth cloud_firestore dio \
  go_router shared_preferences flutter_secure_storage charts_flutter \
  dio_logging intl fl_chart
```

### STEP 2: Create Core Services
- [ ] Firebase config (use same project as user app)
- [ ] API client (Dio + interceptors)
- [ ] Auth service (email/password)
- [ ] Permission service (role-based access)
- [ ] Firestore service (admin reads)

### STEP 3: Create Riverpod Providers
- [ ] Auth provider (current admin + token)
- [ ] Users provider (CRUD operations)
- [ ] Deals provider (list, search, update)
- [ ] Notifications provider (send notifications)
- [ ] Analytics provider (fetch metrics)
- [ ] Team provider (manage admins)

### STEP 4: Create Screens (in order of importance)
1. [ ] Admin Login Screen
2. [ ] Dashboard (analytics overview)
3. [ ] Users Management
4. [ ] Deals Management
5. [ ] Team Management
6. [ ] Notifications
7. [ ] Tiers Management
8. [ ] Analytics Details
9. [ ] Scraper Control
10. [ ] Audit Log

### STEP 5: Setup Navigation
- [ ] GoRouter configuration
- [ ] Auth guards (login required)
- [ ] Permission guards (role-based)
- [ ] Bottom navigation for main sections

### STEP 6: Testing
- [ ] Login as owner → full access
- [ ] Login as editor → permission-filtered access
- [ ] Login as viewer → read-only mode
- [ ] Test all CRUD operations
- [ ] Test permission enforcement

---

## EXAMPLE: Complete Users Provider

```dart
// providers/users_provider.dart

import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../models/user.dart';
import '../services/api_client.dart';

final usersProvider = FutureProvider<List<User>>((ref) async {
  final api = ref.read(apiClientProvider);
  final response = await api.get('/api/v1/admin/users');
  final List users = response.data['users'] ?? [];
  return users.map((u) => User.fromJson(u)).toList();
});

final updateUserProvider = FutureProvider.family<void, (String, Map)>((ref, args) async {
  final (userId, updates) = args;
  final api = ref.read(apiClientProvider);
  
  await api.put('/api/v1/admin/users/$userId', data: updates);
  
  // Refresh users list
  ref.refresh(usersProvider);
});

final deleteUserProvider = FutureProvider.family<void, String>((ref, userId) async {
  final api = ref.read(apiClientProvider);
  
  await api.delete('/api/v1/admin/users/$userId');
  
  // Refresh users list
  ref.refresh(usersProvider);
});
```

---

## EXAMPLE: Complete Users Screen

```dart
// screens/users/users_list_screen.dart

class UsersListScreen extends ConsumerStatefulWidget {
  const UsersListScreen({Key? key}) : super(key: key);

  @override
  ConsumerState<UsersListScreen> createState() => _UsersListScreenState();
}

class _UsersListScreenState extends ConsumerState<UsersListScreen> {
  String searchQuery = '';
  String selectedTier = 'all';

  @override
  Widget build(BuildContext context) {
    final usersAsync = ref.watch(usersProvider);
    final permissionService = ref.read(permissionServiceProvider);

    if (!permissionService.canAccessPage('users')) {
      return Scaffold(
        appBar: AppBar(title: Text('Users')),
        body: Center(
          child: Text('Access Denied - Insufficient Permissions'),
        ),
      );
    }

    return Scaffold(
      appBar: AppBar(
        title: Text('Users Management'),
        actions: [
          IconButton(
            icon: Icon(Icons.refresh),
            onPressed: () => ref.refresh(usersProvider),
          ),
        ],
      ),
      body: usersAsync.when(
        data: (users) {
          // Filter users
          final filtered = users.where((u) {
            final matchesSearch = u.email.toLowerCase().contains(searchQuery.toLowerCase());
            final matchesTier = selectedTier == 'all' || u.tier == selectedTier;
            return matchesSearch && matchesTier;
          }).toList();

          return Column(
            children: [
              // Search bar
              Padding(
                padding: EdgeInsets.all(16),
                child: TextField(
                  decoration: InputDecoration(
                    labelText: 'Search users',
                    border: OutlineInputBorder(),
                    prefixIcon: Icon(Icons.search),
                  ),
                  onChanged: (value) => setState(() => searchQuery = value),
                ),
              ),
              
              // Tier filter chips
              Padding(
                padding: EdgeInsets.symmetric(horizontal: 16),
                child: Wrap(
                  spacing: 8,
                  children: ['all', 'free', 'trial', 'premium', 'vip'].map((tier) {
                    return FilterChip(
                      label: Text(tier.toUpperCase()),
                      selected: selectedTier == tier,
                      onSelected: (selected) {
                        setState(() => selectedTier = selected ? tier : 'all');
                      },
                    );
                  }).toList(),
                ),
              ),
              
              // Users table
              Expanded(
                child: SingleChildScrollView(
                  scrollDirection: Axis.horizontal,
                  child: DataTable(
                    columns: [
                      DataColumn(label: Text('Email')),
                      DataColumn(label: Text('Name')),
                      DataColumn(label: Text('Tier')),
                      DataColumn(label: Text('Daily Limit')),
                      DataColumn(label: Text('Registered')),
                      DataColumn(label: Text('Last Login')),
                      DataColumn(label: Text('Actions')),
                    ],
                    rows: filtered.map((user) {
                      return DataRow(cells: [
                        DataCell(Text(user.email)),
                        DataCell(Text(user.name ?? '')),
                        DataCell(Chip(
                          label: Text(user.tier),
                          backgroundColor: _getTierColor(user.tier),
                        )),
                        DataCell(Text('${user.dailyDealLimit}')),
                        DataCell(Text(formatDate(user.registeredAt))),
                        DataCell(Text(formatDate(user.lastLogin))),
                        DataCell(Row(
                          children: [
                            IconButton(
                              icon: Icon(Icons.edit),
                              onPressed: () => _showEditDialog(context, user),
                            ),
                            IconButton(
                              icon: Icon(Icons.delete, color: Colors.red),
                              onPressed: () => _confirmDelete(context, user),
                            ),
                          ],
                        )),
                      ]);
                    }).toList(),
                  ),
                ),
              ),
            ],
          );
        },
        loading: () => Center(child: CircularProgressIndicator()),
        error: (error, stack) => Center(
          child: Text('Error: $error'),
        ),
      ),
    );
  }

  void _showEditDialog(BuildContext context, User user) {
    final nameController = TextEditingController(text: user.name);
    final limitController = TextEditingController(
      text: user.dailyDealLimit.toString(),
    );
    String selectedTier = user.tier;

    showDialog(
      context: context,
      builder: (context) => AlertDialog(
        title: Text('Edit User'),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            TextField(
              controller: nameController,
              decoration: InputDecoration(labelText: 'Name'),
            ),
            SizedBox(height: 16),
            DropdownButtonFormField<String>(
              value: selectedTier,
              decoration: InputDecoration(labelText: 'Tier'),
              items: ['free', 'trial', 'premium', 'vip'].map((tier) {
                return DropdownMenuItem(value: tier, child: Text(tier.toUpperCase()));
              }).toList(),
              onChanged: (value) => selectedTier = value ?? selectedTier,
            ),
            SizedBox(height: 16),
            TextField(
              controller: limitController,
              decoration: InputDecoration(labelText: 'Daily Deal Limit'),
              keyboardType: TextInputType.number,
            ),
          ],
        ),
        actions: [
          TextButton(onPressed: () => Navigator.pop(context), child: Text('Cancel')),
          ElevatedButton(
            onPressed: () async {
              ref.read(updateUserProvider.future as dynamic).then((_) {
                Navigator.pop(context);
                ScaffoldMessenger.of(context).showSnackBar(
                  SnackBar(content: Text('User updated')),
                );
              });
            },
            child: Text('Save'),
          ),
        ],
      ),
    );
  }

  void _confirmDelete(BuildContext context, User user) {
    showDialog(
      context: context,
      builder: (context) => AlertDialog(
        title: Text('Delete User?'),
        content: Text('Are you sure you want to delete ${user.email}?'),
        actions: [
          TextButton(onPressed: () => Navigator.pop(context), child: Text('Cancel')),
          ElevatedButton(
            onPressed: () {
              ref.read(deleteUserProvider(user.id)).then((_) {
                Navigator.pop(context);
                ScaffoldMessenger.of(context).showSnackBar(
                  SnackBar(content: Text('User deleted')),
                );
              });
            },
            child: Text('Delete'),
          ),
        ],
      ),
    );
  }

  Color _getTierColor(String tier) {
    return {
      'free': Colors.grey,
      'trial': Colors.blue,
      'premium': Colors.green,
      'vip': Colors.purple,
    }[tier] ?? Colors.grey;
  }
}
```

---

## TESTING STRATEGY

### Authentication Testing
- [ ] Login with owner account → full access
- [ ] Login with editor account → limited access per permissions
- [ ] Login with viewer account → read-only mode
- [ ] Wrong password → error message
- [ ] Non-existent user → "User not found" error
- [ ] Token expiry → redirect to login

### Permission Testing
- [ ] Viewer cannot see edit buttons
- [ ] Editor without "users" permission cannot access Users screen
- [ ] Owner can always access everything
- [ ] Page shows "Access Denied" for insufficient permissions

### Functionality Testing
- [ ] Add new team member (owner)
- [ ] Edit admin permissions (owner)
- [ ] Remove team member (owner)
- [ ] Change user tier → API call successful
- [ ] Send notification → users receive it
- [ ] Pause scraper → /api/v1/admin/scraper/pause called
- [ ] Feature deal → deal appears at top

### UI Testing
- [ ] All screens display correctly
- [ ] Tables have proper horizontal scroll
- [ ] Dialogs are modal and prevent background interaction
- [ ] Buttons are disabled when appropriate (loading, no permission)
- [ ] Toast notifications appear for actions

---

## DEPLOYMENT

### App Store Submission (Admin App)

**Bundle IDs:**
- iOS: `com.dealhunter.admin` (different from user app)
- Android: `com.dealhunter.admin`

**App Names:**
- iOS: "DealHunter Admin"
- Android: "DealHunter Admin"

**Restrictions:**
- Admin app should NOT appear in public App Store search
- Configure to be "Admin Only" (restricted availability)
- Or: Submit to TestFlight/Internal Testing only

**Review Notes:**
> This is an administrative tool for managing the DealHunter platform. It is not intended for end-user consumption and contains features for user management, payment processing, and platform analytics. Access is restricted to authorized administrators only via Firebase Authentication.

---

## NEXT STEPS

1. **Create dealhunter_admin/ project**
2. **Implement core services** (Firebase, API client, auth)
3. **Build login screen** first
4. **Build dashboard screen** second
5. **Build users management screen** third
6. **Implement permissions system** (permission_service.dart)
7. **Build remaining screens** in priority order
8. **Test all flows** (especially permissions)
9. **Submit to TestFlight** (iOS) and **Internal Testing** (Android)

---

## SUMMARY

**Admin App Features:**
1. ✅ Role-based access (Owner/Editor/Viewer)
2. ✅ Granular permissions (8 permission types)
3. ✅ User management (view, edit, delete, tier change)
4. ✅ Deal management (feature, hide, mark fake)
5. ✅ Notification sending (target by tier/group)
6. ✅ Team management (add/remove admins)
7. ✅ Analytics dashboard (user growth, revenue)
8. ✅ Scraper control (pause/resume/manual run)

**Timeline:** 3-4 weeks for complete implementation

**Testing:** Comprehensive permission-based testing required

---

**Ready to start building the Admin App!** 🚀
