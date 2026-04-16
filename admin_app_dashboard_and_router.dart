// lib/config/router.dart
import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../screens/auth/admin_login_screen.dart';
import '../screens/dashboard/dashboard_screen.dart';
import '../screens/users/users_list_screen.dart';
import '../screens/deals/deals_list_screen.dart';
import '../screens/notifications/notifications_screen.dart';
import '../screens/team/team_screen.dart';
import '../screens/shared/app_shell.dart';

final routerProvider = Provider<GoRouter>((ref) {
  return GoRouter(
    routes: [
      // Auth routes
      GoRoute(
        path: '/login',
        builder: (context, state) => const AdminLoginScreen(),
      ),

      // Protected routes (shell with navigation)
      ShellRoute(
        builder: (context, state, child) => AppShell(child: child),
        routes: [
          GoRoute(
            path: '/dashboard',
            builder: (context, state) => const DashboardScreen(),
          ),
          GoRoute(
            path: '/users',
            builder: (context, state) => const UsersListScreen(),
          ),
          GoRoute(
            path: '/deals',
            builder: (context, state) => const DealsListScreen(),
          ),
          GoRoute(
            path: '/notifications',
            builder: (context, state) => const NotificationsScreen(),
          ),
          GoRoute(
            path: '/team',
            builder: (context, state) => const TeamScreen(),
          ),
          // Add more routes as needed
        ],
      ),
    ],
    initialLocation: '/login',
    redirect: (context, state) {
      // Check if user is authenticated
      final isAuth = false; // TODO: Check auth state from provider

      if (isAuth) {
        return state.matchedLocation;
      }

      if (state.matchedLocation == '/login') {
        return null;
      }

      return '/login';
    },
  );
});

// ============================================================================
// lib/screens/shared/app_shell.dart
import 'package:flutter/material.dart';

class AppShell extends StatelessWidget {
  final Widget child;

  const AppShell({required this.child, Key? key}) : super(key: key);

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: Row(
        children: [
          // Sidebar navigation
          NavigationRail(
            selectedIndex: _getSelectedIndex(context),
            onDestinationSelected: (int index) {
              _navigateTo(context, index);
            },
            labelType: NavigationRailLabelType.selected,
            destinations: const [
              NavigationRailDestination(
                icon: Icon(Icons.dashboard),
                selectedIcon: Icon(Icons.dashboard),
                label: Text('Dashboard'),
              ),
              NavigationRailDestination(
                icon: Icon(Icons.people),
                selectedIcon: Icon(Icons.people),
                label: Text('Users'),
              ),
              NavigationRailDestination(
                icon: Icon(Icons.local_offer),
                selectedIcon: Icon(Icons.local_offer),
                label: Text('Deals'),
              ),
              NavigationRailDestination(
                icon: Icon(Icons.notifications),
                selectedIcon: Icon(Icons.notifications),
                label: Text('Notifications'),
              ),
              NavigationRailDestination(
                icon: Icon(Icons.group),
                selectedIcon: Icon(Icons.group),
                label: Text('Team'),
              ),
            ],
          ),

          // Main content
          Expanded(child: child),
        ],
      ),
    );
  }

  int _getSelectedIndex(BuildContext context) {
    final location = GoRouter.of(context).location;
    if (location.startsWith('/dashboard')) return 0;
    if (location.startsWith('/users')) return 1;
    if (location.startsWith('/deals')) return 2;
    if (location.startsWith('/notifications')) return 3;
    if (location.startsWith('/team')) return 4;
    return 0;
  }

  void _navigateTo(BuildContext context, int index) {
    switch (index) {
      case 0:
        GoRouter.of(context).go('/dashboard');
        break;
      case 1:
        GoRouter.of(context).go('/users');
        break;
      case 2:
        GoRouter.of(context).go('/deals');
        break;
      case 3:
        GoRouter.of(context).go('/notifications');
        break;
      case 4:
        GoRouter.of(context).go('/team');
        break;
    }
  }
}

// ============================================================================
// lib/screens/dashboard/dashboard_screen.dart
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:fl_chart/fl_chart.dart';
import '../../providers/analytics_provider.dart';
import '../../providers/scraper_provider.dart';
import '../../widgets/stat_tile.dart';

class DashboardScreen extends ConsumerWidget {
  const DashboardScreen({Key? key}) : super(key: key);

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final analyticsAsync = ref.watch(analyticsProvider);
    final scraperStatusAsync = ref.watch(scraperStatusProvider);

    return Scaffold(
      appBar: AppBar(
        title: const Text('Dashboard'),
        centerTitle: true,
        elevation: 0,
      ),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(24),
        child: analyticsAsync.when(
          data: (analytics) => Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              // Key metrics row
              GridView.count(
                crossAxisCount: 4,
                shrinkWrap: true,
                mainAxisSpacing: 16,
                crossAxisSpacing: 16,
                childAspectRatio: 1.5,
                children: [
                  StatTile(
                    title: 'Total Users',
                    value: analytics.totalUsers.toString(),
                    icon: Icons.people,
                    trend: '+12%',
                  ),
                  StatTile(
                    title: 'Total Deals',
                    value: analytics.totalDeals.toString(),
                    icon: Icons.local_offer,
                    trend: '+8%',
                  ),
                  StatTile(
                    title: 'Total Revenue',
                    value: 'EGP ${analytics.totalRevenue.toStringAsFixed(0)}',
                    icon: Icons.attach_money,
                    trend: '+15%',
                  ),
                  StatTile(
                    title: 'Active Subscriptions',
                    value: analytics.activeSubscriptions.toString(),
                    icon: Icons.subscriptions,
                    trend: '+5%',
                  ),
                ],
              ),
              const SizedBox(height: 32),

              // Charts row
              Row(
                children: [
                  // User growth chart
                  Expanded(
                    child: Card(
                      child: Padding(
                        padding: const EdgeInsets.all(16),
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            const Text(
                              'User Growth (7 Days)',
                              style: TextStyle(
                                fontSize: 16,
                                fontWeight: FontWeight.bold,
                              ),
                            ),
                            const SizedBox(height: 16),
                            SizedBox(
                              height: 250,
                              child: LineChart(
                                LineChartData(
                                  gridData: FlGridData(show: true),
                                  titlesData: FlTitlesData(show: true),
                                  borderData: FlBorderData(show: true),
                                  lineBarsData: [
                                    LineChartBarData(
                                      spots: List.generate(
                                        analytics.userGrowthData.length,
                                        (index) => FlSpot(
                                          index.toDouble(),
                                          analytics.userGrowthData[index].toDouble(),
                                        ),
                                      ),
                                      isCurved: true,
                                      color: Colors.blue,
                                      barWidth: 3,
                                      dotData: FlDotData(show: true),
                                    ),
                                  ],
                                ),
                              ),
                            ),
                          ],
                        ),
                      ),
                    ),
                  ),
                  const SizedBox(width: 16),

                  // Revenue chart
                  Expanded(
                    child: Card(
                      child: Padding(
                        padding: const EdgeInsets.all(16),
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            const Text(
                              'Revenue (7 Days)',
                              style: TextStyle(
                                fontSize: 16,
                                fontWeight: FontWeight.bold,
                              ),
                            ),
                            const SizedBox(height: 16),
                            SizedBox(
                              height: 250,
                              child: BarChart(
                                BarChartData(
                                  gridData: FlGridData(show: true),
                                  titlesData: FlTitlesData(show: true),
                                  borderData: FlBorderData(show: true),
                                  barGroups: List.generate(
                                    analytics.revenueData.length,
                                    (index) => BarChartGroupData(
                                      x: index,
                                      barRods: [
                                        BarChartRodData(
                                          toY: analytics.revenueData[index].toDouble(),
                                          color: Colors.green,
                                          width: 16,
                                        ),
                                      ],
                                    ),
                                  ),
                                ),
                              ),
                            ),
                          ],
                        ),
                      ),
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 32),

              // Scraper status card
              scraperStatusAsync.when(
                data: (scraperStatus) => Card(
                  child: Padding(
                    padding: const EdgeInsets.all(16),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Row(
                          mainAxisAlignment: MainAxisAlignment.spaceBetween,
                          children: [
                            const Text(
                              'Scraper Status',
                              style: TextStyle(
                                fontSize: 16,
                                fontWeight: FontWeight.bold,
                              ),
                            ),
                            Chip(
                              label: Text(
                                scraperStatus.isRunning ? 'RUNNING' : 'PAUSED',
                              ),
                              backgroundColor: scraperStatus.isRunning
                                  ? Colors.green.shade100
                                  : Colors.orange.shade100,
                              labelStyle: TextStyle(
                                color: scraperStatus.isRunning
                                    ? Colors.green.shade700
                                    : Colors.orange.shade700,
                                fontWeight: FontWeight.bold,
                              ),
                            ),
                          ],
                        ),
                        const SizedBox(height: 16),
                        Text(
                          'Last run: ${scraperStatus.lastRun != null ? _formatTime(scraperStatus.lastRun!) : 'Never'}',
                          style: TextStyle(color: Colors.grey.shade600),
                        ),
                        Text(
                          'Deals added today: ${scraperStatus.dealsAddedToday}',
                          style: TextStyle(color: Colors.grey.shade600),
                        ),
                        const SizedBox(height: 16),
                        Row(
                          children: [
                            ElevatedButton.icon(
                              onPressed: scraperStatus.isRunning ? null : () {
                                ref.refresh(scraperStatusProvider);
                              },
                              icon: const Icon(Icons.play_arrow),
                              label: const Text('Resume'),
                            ),
                            const SizedBox(width: 8),
                            ElevatedButton.icon(
                              onPressed: !scraperStatus.isRunning ? null : () {
                                ref.refresh(scraperStatusProvider);
                              },
                              icon: const Icon(Icons.pause),
                              label: const Text('Pause'),
                            ),
                          ],
                        ),
                      ],
                    ),
                  ),
                ),
                loading: () => const Card(
                  child: Padding(
                    padding: EdgeInsets.all(16),
                    child: CircularProgressIndicator(),
                  ),
                ),
                error: (error, stack) => Card(
                  child: Padding(
                    padding: const EdgeInsets.all(16),
                    child: Text('Error loading scraper status: $error'),
                  ),
                ),
              ),
            ],
          ),
          loading: () => const Center(child: CircularProgressIndicator()),
          error: (error, stack) => Center(
            child: Text('Error: $error'),
          ),
        ),
      ),
    );
  }

  String _formatTime(DateTime time) {
    final diff = DateTime.now().difference(time);
    if (diff.inMinutes < 1) return 'just now';
    if (diff.inMinutes < 60) return '${diff.inMinutes}m ago';
    if (diff.inHours < 24) return '${diff.inHours}h ago';
    return '${diff.inDays}d ago';
  }
}

// ============================================================================
// lib/widgets/stat_tile.dart

class StatTile extends StatelessWidget {
  final String title;
  final String value;
  final IconData icon;
  final String? trend;
  final Color? backgroundColor;

  const StatTile({
    required this.title,
    required this.value,
    required this.icon,
    this.trend,
    this.backgroundColor,
    Key? key,
  }) : super(key: key);

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.spaceBetween,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                Text(
                  title,
                  style: TextStyle(
                    fontSize: 14,
                    color: Colors.grey.shade600,
                    fontWeight: FontWeight.w500,
                  ),
                ),
                Icon(
                  icon,
                  color: Colors.blue,
                  size: 24,
                ),
              ],
            ),
            const SizedBox(height: 8),
            Text(
              value,
              style: const TextStyle(
                fontSize: 24,
                fontWeight: FontWeight.bold,
              ),
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
            ),
            if (trend != null)
              Text(
                trend!,
                style: TextStyle(
                  fontSize: 12,
                  color: Colors.green,
                  fontWeight: FontWeight.w500,
                ),
              ),
          ],
        ),
      ),
    );
  }
}

// ============================================================================
// lib/main.dart (Entry point)

import 'package:flutter/material.dart';
import 'config/firebase_config.dart';
import 'config/router.dart';
import 'config/theme.dart';

void main() async {
  WidgetsFlutterBinding.ensureInitialized();
  await FirebaseConfig.initialize();
  runApp(const DealHunterAdminApp());
}

class DealHunterAdminApp extends ConsumerWidget {
  const DealHunterAdminApp({Key? key}) : super(key: key);

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final router = ref.watch(routerProvider);

    return MaterialApp.router(
      title: 'DealHunter Admin',
      theme: AppTheme.lightTheme,
      darkTheme: AppTheme.darkTheme,
      themeMode: ThemeMode.light,
      routerConfig: router,
    );
  }
}

// lib/config/theme.dart
import 'package:flutter/material.dart';

class AppTheme {
  static ThemeData get lightTheme {
    return ThemeData(
      useMaterial3: true,
      colorScheme: ColorScheme.fromSeed(
        seedColor: Colors.blue,
      ),
      appBarTheme: const AppBarTheme(
        elevation: 0,
        centerTitle: true,
      ),
      cardTheme: CardTheme(
        elevation: 1,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(8),
        ),
      ),
    );
  }

  static ThemeData get darkTheme {
    return ThemeData.dark(useMaterial3: true);
  }
}
