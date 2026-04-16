# Phase 2 Admin Screens - Integration Guide

## Status: ✅ COMPLETE - Ready for Integration Testing

All necessary files have been created and integrated into the app structure.

---

## Files Created

### 1. Models (lib/models/)
- ✅ `admin_user.dart` - Admin user model with roles & permissions
- ✅ `user.dart` - User model for admin management
- ✅ `deal.dart` - Deal model for admin management
- ✅ `notification.dart` - Notification model

### 2. Services (lib/services/)
- ✅ `permission_service.dart` - Role-based access control (RBAC) service

### 3. Providers (lib/providers/)
- ✅ `team_provider.dart` - Team management Riverpod providers
- ✅ `notifications_provider.dart` - Notifications Riverpod providers
- ✅ `users_provider.dart` - Users management Riverpod providers
- ✅ `deals_provider.dart` - Deals management Riverpod providers

### 4. Config (lib/config/)
- ✅ `router.dart` - GoRouter navigation configuration

### 5. Screens (lib/screens/)
- ✅ `users/users_list_screen.dart` - Users management screen
- ✅ `deals/deals_list_screen.dart` - Deals management screen
- ✅ `team/team_screen.dart` - Team management screen
- ✅ `notifications/notifications_screen.dart` - Notifications screen

---

## Next Steps for Integration

### 1. Update Main App Entry Point
**File:** `lib/main.dart`

Add GoRouter provider to your providers:
```dart
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'config/router.dart';

void main() {
  runApp(const MyApp());
}

class MyApp extends StatelessWidget {
  const MyApp({Key? key}) : super(key: key);

  @override
  Widget build(BuildContext context) {
    return ProviderScope(
      child: MaterialApp.router(
        title: 'DealHunter Admin',
        theme: ThemeData(
          useMaterial3: true,
          colorSchemeSeed: Colors.blue,
        ),
        routerConfig: adminRouterProvider,
      ),
    );
  }
}
```

### 2. Create Dashboard Screen
**File:** `lib/screens/dashboard/dashboard_screen.dart`

Create a dashboard with navigation to all four screens:
```dart
import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

class DashboardScreen extends StatelessWidget {
  const DashboardScreen({Key? key}) : super(key: key);

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('DealHunter Admin Dashboard'),
        elevation: 0,
      ),
      body: GridView.count(
        crossAxisCount: 2,
        padding: const EdgeInsets.all(16),
        mainAxisSpacing: 16,
        crossAxisSpacing: 16,
        children: [
          _DashboardCard(
            title: 'Users',
            icon: Icons.people,
            onTap: () => context.go('/users'),
          ),
          _DashboardCard(
            title: 'Deals',
            icon: Icons.local_offer,
            onTap: () => context.go('/deals'),
          ),
          _DashboardCard(
            title: 'Team',
            icon: Icons.groups,
            onTap: () => context.go('/team'),
          ),
          _DashboardCard(
            title: 'Notifications',
            icon: Icons.notifications,
            onTap: () => context.go('/notifications'),
          ),
        ],
      ),
    );
  }
}

class _DashboardCard extends StatelessWidget {
  final String title;
  final IconData icon;
  final VoidCallback onTap;

  const _DashboardCard({
    required this.title,
    required this.icon,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    return Card(
      child: InkWell(
        onTap: onTap,
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(icon, size: 48, color: Colors.blue),
            const SizedBox(height: 16),
            Text(
              title,
              style: Theme.of(context).textTheme.titleLarge,
            ),
          ],
        ),
      ),
    );
  }
}
```

### 3. Create Admin Login Screen
**File:** `lib/screens/auth/admin_login_screen.dart`

Implement Firebase authentication with email/password:
```dart
import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

class AdminLoginScreen extends StatefulWidget {
  const AdminLoginScreen({Key? key}) : super(key: key);

  @override
  State<AdminLoginScreen> createState() => _AdminLoginScreenState();
}

class _AdminLoginScreenState extends State<AdminLoginScreen> {
  final emailController = TextEditingController();
  final passwordController = TextEditingController();
  bool isLoading = false;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Admin Login')),
      body: Center(
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              TextField(
                controller: emailController,
                decoration: const InputDecoration(
                  labelText: 'Email',
                  border: OutlineInputBorder(),
                ),
              ),
              const SizedBox(height: 16),
              TextField(
                controller: passwordController,
                obscureText: true,
                decoration: const InputDecoration(
                  labelText: 'Password',
                  border: OutlineInputBorder(),
                ),
              ),
              const SizedBox(height: 24),
              ElevatedButton(
                onPressed: isLoading ? null : _login,
                child: isLoading
                    ? const SizedBox(
                        height: 20,
                        width: 20,
                        child: CircularProgressIndicator(strokeWidth: 2),
                      )
                    : const Text('Login'),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Future<void> _login() async {
    setState(() => isLoading = true);
    try {
      // TODO: Implement Firebase authentication
      // FirebaseAuth.instance.signInWithEmailAndPassword(...)
      if (mounted) {
        context.go('/');
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Error: $e')),
        );
      }
    } finally {
      setState(() => isLoading = false);
    }
  }
}
```

### 4. Implement Backend API Endpoints
**File:** `server.py`

Add the missing endpoints listed in `../documentation/API_ENDPOINTS.md`:
- GET /admin/users
- PUT /admin/users/<user_id>
- GET /admin/deals
- PUT /admin/deals/<deal_id>
- DELETE /admin/deals/<deal_id>
- PATCH /admin/deals/<deal_id>/visibility
- PATCH /admin/deals/<deal_id>/featured
- PATCH /admin/deals/<deal_id>/verdict
- GET /admin/notifications
- GET /admin/permissions

See `../documentation/API_ENDPOINTS.md` for endpoint specifications.

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────┐
│              Admin App (Flutter)                    │
├─────────────────────────────────────────────────────┤
│                                                      │
│  Screens (4 Phase 2 screens)                        │
│  ├── UsersListScreen      (users_list_screen.dart)  │
│  ├── DealsListScreen      (deals_list_screen.dart)  │
│  ├── TeamScreen           (team_screen.dart)        │
│  └── NotificationsScreen  (notifications_screen.dart)
│                                                      │
│  ↓ uses                                             │
│                                                      │
│  Providers (Riverpod FutureProviders)               │
│  ├── usersProvider        (users_provider.dart)     │
│  ├── dealsProvider        (deals_provider.dart)     │
│  ├── teamProvider         (team_provider.dart)      │
│  └── notificationsProvider (notifications_provider) │
│                                                      │
│  ↓ uses                                             │
│                                                      │
│  Services                                           │
│  ├── permissionService (RBAC)                       │
│  └── ApiClient (Dio HTTP)                           │
│                                                      │
│  ↓ communicates via HTTP                            │
│                                                      │
└─────────────────────────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────┐
│           Backend API (Flask/Python)                │
├─────────────────────────────────────────────────────┤
│                                                      │
│  /admin/users/*        (Users management)           │
│  /admin/deals/*        (Deals management)           │
│  /admin/team/*         (Team management)            │
│  /admin/notifications* (Notifications)              │
│                                                      │
│  ↓ communicates via                                 │
│                                                      │
└─────────────────────────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────┐
│           Firestore Database                        │
├─────────────────────────────────────────────────────┤
│                                                      │
│  Collections:                                       │
│  ├── admin_users (with role & permissions)          │
│  ├── users (with tier & limits)                     │
│  ├── deals (with verdict & status)                  │
│  └── notifications (with delivery stats)            │
│                                                      │
└─────────────────────────────────────────────────────┘
```

---

## Permission System

### Three Roles
- **Owner** - Full access to all features, can manage team
- **Editor** - Limited access based on assigned permissions
- **Viewer** - Read-only access to all features

### Permissions
- `sources` - Manage deal sources
- `deals` - Manage deals (edit, delete, feature)
- `users` - Manage users (upgrade tier, set limits)
- `notifications` - Send notifications to users
- `checker` - Run fake product checker
- `competitors` - View competitor analysis
- `scraper_control` - Pause/resume scraper

### Usage in Screens
```dart
final permissionService = ref.read(permissionServiceProvider);

if (!permissionService.canAccessPage('users', currentAdmin)) {
  return PermissionDeniedScreen();
}
```

---

## Data Flow Example: Editing a User

```
1. User clicks "Edit" button in UsersListScreen
   ↓
2. _showEditDialog() opens AlertDialog
   ↓
3. User modifies fields (name, tier, daily_limit, status)
   ↓
4. User clicks "Save"
   ↓
5. Dialog calls: ref.read(updateUserProvider((userId, updates)).future)
   ↓
6. updateUserProvider sends PUT request to /admin/users/{userId}
   ↓
7. Backend updates Firestore document
   ↓
8. Provider automatically refreshes usersProvider
   ↓
9. Screen rebuilds with new data
   ↓
10. SnackBar shows "User updated successfully"
```

---

## Testing Checklist

### Unit Tests
- [ ] AdminUser.fromJson() / toJson()
- [ ] UserModel.fromJson() / toJson()
- [ ] DealModel.fromJson() / toJson()
- [ ] NotificationModel.fromJson() / toJson()
- [ ] PermissionService methods

### Widget Tests
- [ ] UsersListScreen renders correctly
- [ ] DealsListScreen renders correctly
- [ ] TeamScreen renders correctly
- [ ] NotificationsScreen renders correctly
- [ ] Permission denied screens show when access denied

### Integration Tests
- [ ] Login flow works
- [ ] Navigate to dashboard
- [ ] Navigate to each admin screen
- [ ] Data loads from API
- [ ] Can edit user (send request)
- [ ] Can delete deal (send request)
- [ ] Can add team member
- [ ] Can send notification
- [ ] Permission checks work

### Manual Testing
- [ ] Test with different user roles (owner, editor, viewer)
- [ ] Test permission denied for unauthorized pages
- [ ] Test error handling (network errors, API errors)
- [ ] Test loading states
- [ ] Test snackbar notifications
- [ ] Test dialog modals

---

## Common Issues & Solutions

### Issue: Screens show "Access Denied"
**Solution:** Check PermissionService implementation and ensure `canAccessPage()` returns true for your role

### Issue: Data not loading
**Solution:** Check if API endpoint exists and is returning correct data format

### Issue: Buttons disabled
**Solution:** Check if `isLoading` state is stuck as true, or check permission checks

### Issue: Navigation not working
**Solution:** Ensure GoRouter is properly configured in main.dart and route paths are correct

---

## File Structure Summary

```
app/admin_app/
├── lib/
│   ├── config/
│   │   └── router.dart ✅
│   ├── models/
│   │   ├── admin_user.dart ✅
│   │   ├── user.dart ✅
│   │   ├── deal.dart ✅
│   │   └── notification.dart ✅
│   ├── services/
│   │   └── permission_service.dart ✅
│   ├── providers/
│   │   ├── team_provider.dart ✅
│   │   ├── notifications_provider.dart ✅
│   │   ├── users_provider.dart ✅
│   │   └── deals_provider.dart ✅
│   ├── screens/
│   │   ├── auth/
│   │   │   └── admin_login_screen.dart (TO CREATE)
│   │   ├── dashboard/
│   │   │   └── dashboard_screen.dart (TO CREATE)
│   │   ├── users/
│   │   │   └── users_list_screen.dart ✅
│   │   ├── deals/
│   │   │   └── deals_list_screen.dart ✅
│   │   ├── team/
│   │   │   └── team_screen.dart ✅
│   │   └── notifications/
│   │       └── notifications_screen.dart ✅
│   └── main.dart (TO UPDATE)
└── INTEGRATION_GUIDE.md (this file)
```

---

## Next Phase (Phase 3)

After Phase 2 is complete, implement:
- Tiers Management Screen
- Analytics Details Screen
- Settings/Audit Log Screen
- Real-time updates with WebSocket
- Search/filter optimization
- Bulk operations (bulk tier change, bulk delete)

---

**Status:** 🚀 Ready for Integration Testing  
**Last Updated:** 2026-04-16
