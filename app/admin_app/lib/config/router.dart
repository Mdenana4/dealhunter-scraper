import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import '../screens/auth/admin_login_screen.dart';
import '../screens/dashboard/dashboard_screen.dart';
import '../screens/users/users_list_screen.dart';
import '../screens/groups/groups_screen.dart';
import '../screens/sources/sources_screen.dart';
import '../screens/notifications/notifications_screen.dart';

final adminRouter = GoRouter(
  initialLocation: '/',
  errorBuilder: (context, state) => Scaffold(
    appBar: AppBar(title: const Text('Error')),
    body: Center(
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          const Icon(Icons.error_outline, size: 64, color: Colors.red),
          const SizedBox(height: 16),
          Text('Page not found: ${state.uri}'),
          const SizedBox(height: 24),
          ElevatedButton(
            onPressed: () => context.go('/'),
            child: const Text('Go to Dashboard'),
          ),
        ],
      ),
    ),
  ),
  routes: [
    GoRoute(
      path: '/login',
      name: 'login',
      builder: (_, __) => const AdminLoginScreen(),
    ),
    GoRoute(
      path: '/',
      name: 'dashboard',
      builder: (_, __) => const DashboardScreen(),
    ),
    GoRoute(
      path: '/users',
      name: 'users',
      builder: (_, __) => const UsersListScreen(),
    ),
    GoRoute(
      path: '/groups',
      name: 'groups',
      builder: (_, __) => const GroupsScreen(),
    ),
    GoRoute(
      path: '/sources',
      name: 'sources',
      builder: (_, __) => const SourcesScreen(),
    ),
    GoRoute(
      path: '/notifications',
      name: 'notifications',
      builder: (_, __) => const NotificationsScreen(),
    ),
  ],
);
