import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../l10n/app_strings.dart';
import '../../models/user_model.dart';
import '../../providers/app_providers.dart';
import '../deals/deals_screen.dart';
import '../membership/membership_screen.dart';
import '../saved/saved_screen.dart';
import '../search/search_screen.dart';
import '../settings/settings_screen.dart';

class HomeScreen extends ConsumerWidget {
  const HomeScreen({super.key});

  static const _screens = [
    DealsScreen(),
    SearchScreen(),
    SavedScreen(),
    MembershipScreen(),
    SettingsScreen(),
  ];

  void _onTabTap(BuildContext context, WidgetRef ref, int i) {
    // Intercept Search tab for free users — show dialog instead of navigating
    if (i == 1) {
      final membership = ref.read(currentUserProvider).valueOrNull?.membership
          ?? const MembershipInfo();
      if (!membership.canSearch) {
        _showUpgradeDialog(context, ref);
        return;
      }
    }
    ref.read(homeTabIndexProvider.notifier).state = i;
  }

  void _showUpgradeDialog(BuildContext context, WidgetRef ref) {
    final cs = Theme.of(context).colorScheme;
    showDialog(
      context: context,
      builder: (_) => AlertDialog(
        icon: Icon(Icons.lock_outline, color: cs.primary, size: 40),
        title: Text(context.s('search_premium_title')),
        content: Text(context.s('search_premium_body')),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: Text(context.s('cancel')),
          ),
          FilledButton(
            onPressed: () {
              Navigator.pop(context);
              // Navigate to Membership tab (index 3)
              ref.read(homeTabIndexProvider.notifier).state = 3;
            },
            child: Text(context.s('upgrade_now')),
          ),
        ],
      ),
    );
  }

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final index = ref.watch(homeTabIndexProvider);
    ref.watch(localeProvider);
    return Scaffold(
      body: IndexedStack(
        index: index,
        children: _screens,
      ),
      bottomNavigationBar: NavigationBar(
        selectedIndex: index,
        onDestinationSelected: (i) => _onTabTap(context, ref, i),
        destinations: [
          NavigationDestination(
            icon: const Icon(Icons.local_fire_department_outlined),
            selectedIcon: const Icon(Icons.local_fire_department),
            label: context.s('nav_deals'),
          ),
          NavigationDestination(
            icon: const Icon(Icons.search_outlined),
            selectedIcon: const Icon(Icons.search),
            label: context.s('nav_search'),
          ),
          NavigationDestination(
            icon: const Icon(Icons.bookmark_outline),
            selectedIcon: const Icon(Icons.bookmark),
            label: context.s('nav_saved'),
          ),
          NavigationDestination(
            icon: const Icon(Icons.diamond_outlined),
            selectedIcon: const Icon(Icons.diamond),
            label: context.s('nav_membership'),
          ),
          NavigationDestination(
            icon: const Icon(Icons.settings_outlined),
            selectedIcon: const Icon(Icons.settings),
            label: context.s('nav_settings'),
          ),
        ],
      ),
    );
  }
}
