// lib/config/router.dart

import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import '../screens/auth/admin_login_screen.dart';
import '../screens/dashboard/dashboard_screen.dart';
import '../screens/users/users_list_screen.dart';
import '../screens/deals/deals_list_screen.dart';
import '../screens/team/team_screen.dart';
import '../screens/notifications/notifications_screen.dart';

/// GoRouter configuration for admin app navigation
final adminRouterProvider = GoRouter(
  initialLocation: '/login',
  routes: [
    // Authentication routes
    GoRoute(
      path: '/login',
      name: 'login',
      builder: (context, state) => const AdminLoginScreen(),
    ),

    // Dashboard and main routes (protected)
    GoRoute(
      path: '/',
      name: 'dashboard',
      builder: (context, state) => const DashboardScreen(),
      routes: [
        // Users Management
        GoRoute(
          path: 'users',
          name: 'users',
          builder: (context, state) => const UsersListScreen(),
        ),

        // Deals Management
        GoRoute(
          path: 'deals',
          name: 'deals',
          builder: (context, state) => const DealsListScreen(),
        ),

        // Team Management
        GoRoute(
          path: 'team',
          name: 'team',
          builder: (context, state) => const TeamScreen(),
        ),

        // Notifications
        GoRoute(
          path: 'notifications',
          name: 'notifications',
          builder: (context, state) => const NotificationsScreen(),
        ),

        // Additional routes can be added here for other screens
        // (Sources, Analytics, Settings, Audit Log, etc.)
      ],
    ),
  ],

  // Error handling
  errorBuilder: (context, state) {
    return Scaffold(
      appBar: AppBar(title: const Text('Error')),
      body: Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            const Icon(Icons.error, size: 64, color: Colors.red),
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
    );
  },

  // Redirect logic for authentication
  redirect: (context, state) {
    // TODO: Implement authentication check
    // If no auth token, redirect to login
    // Except for login route itself
    return null; // No redirect needed
  },
);

/// Navigation helpers
extension GoRouterExtension on GoRouter {
  void goToDashboard() => go('/');

  void goToUsers() => go('/users');

  void goToDeals() => go('/deals');

  void goToTeam() => go('/team');

  void goToNotifications() => go('/notifications');

  void goToLogin() => go('/login');
}
