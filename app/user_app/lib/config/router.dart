import 'package:firebase_auth/firebase_auth.dart';
import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import '../models/deal_model.dart';
import '../screens/auth/login_screen.dart';
import '../screens/deals/deal_detail_screen.dart';
import '../screens/home/home_screen.dart';

final GoRouter appRouter = GoRouter(
  initialLocation: '/home',
  errorBuilder: (context, state) => Scaffold(
    appBar: AppBar(title: const Text('Page not found')),
    body: Center(
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          const Icon(Icons.error_outline, size: 48),
          const SizedBox(height: 12),
          Text('Route not found: ${state.uri}'),
          const SizedBox(height: 16),
          FilledButton(
            onPressed: () => appRouter.go('/home'),
            child: const Text('Go Home'),
          ),
        ],
      ),
    ),
  ),
  redirect: (BuildContext context, GoRouterState state) {
    final isLoggedIn = FirebaseAuth.instance.currentUser != null;
    final onLogin = state.matchedLocation == '/login';
    if (!isLoggedIn && !onLogin) return '/login';
    if (isLoggedIn && onLogin) return '/home';
    return null;
  },
  routes: [
    GoRoute(
      path: '/login',
      builder: (_, __) => const LoginScreen(),
    ),
    GoRoute(
      path: '/home',
      builder: (_, __) => const HomeScreen(),
      routes: [
        GoRoute(
          path: 'deal/:id',
          builder: (_, state) => DealDetailScreen(
            dealId: state.pathParameters['id']!,
            deal: state.extra as DealModel?,
          ),
        ),
      ],
    ),
  ],
);
