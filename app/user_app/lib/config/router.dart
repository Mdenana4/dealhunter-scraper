import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import '../providers/auth_provider.dart';
import '../screens/auth/login_screen.dart';
import '../screens/auth/register_screen.dart';
import '../screens/auth/forgot_password_screen.dart';
import '../screens/main/main_shell.dart';

final routerProvider = Provider<GoRouter>((ref) {
  final authState = ref.watch(firebaseUserProvider);

  return GoRouter(
    initialLocation: '/deals',
    redirect: (context, state) {
      final isLoggedIn = authState.maybeWhen(
          data: (u) => u != null, orElse: () => false);
      final isLoading = authState is AsyncLoading;

      if (isLoading) return null;

      final isAuthRoute = state.matchedLocation == '/login' ||
          state.matchedLocation == '/register' ||
          state.matchedLocation == '/forgot-password';

      // Protected routes require login
      final isProtected = state.matchedLocation == '/saved' ||
          state.matchedLocation == '/membership' ||
          state.matchedLocation == '/settings';

      if (!isLoggedIn && isProtected) return '/login';

      // If logged in and on auth screen, go home
      if (isLoggedIn && isAuthRoute) return '/deals';

      return null;
    },
    routes: [
      // Auth routes
      GoRoute(
        path: '/login',
        builder: (_, __) => const LoginScreen(),
      ),
      GoRoute(
        path: '/register',
        builder: (_, __) => const RegisterScreen(),
      ),
      GoRoute(
        path: '/forgot-password',
        builder: (_, __) => const ForgotPasswordScreen(),
      ),

      // Main shell (tabs)
      ShellRoute(
        builder: (context, state, child) => const MainShell(),
        routes: [
          GoRoute(
            path: '/deals',
            builder: (_, __) => const SizedBox(), // handled by MainShell
          ),
          GoRoute(
            path: '/search',
            builder: (_, __) => const SizedBox(),
          ),
          GoRoute(
            path: '/saved',
            builder: (_, __) => const SizedBox(),
          ),
          GoRoute(
            path: '/membership',
            builder: (_, __) => const SizedBox(),
          ),
          GoRoute(
            path: '/settings',
            builder: (_, __) => const SizedBox(),
          ),
        ],
      ),
    ],
  );
});
