import 'package:firebase_auth/firebase_auth.dart';
import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import '../models/deal_model.dart';
import '../screens/auth/login_screen.dart';
import '../screens/deals/deal_detail_screen.dart';
import '../screens/home/home_screen.dart';

final appRouter = GoRouter(
  initialLocation: '/home',
  // Handle dealhunter://deal/<id> deep links from FCM
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
