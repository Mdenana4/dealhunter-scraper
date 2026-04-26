import 'package:flutter/material.dart';
import '../deals/deals_screen.dart';
import '../membership/membership_screen.dart';
import '../saved/saved_screen.dart';
import '../search/search_screen.dart';
import '../settings/settings_screen.dart';

class HomeScreen extends StatefulWidget {
  const HomeScreen({super.key});

  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> {
  int _index = 0;

  static const _destinations = [
    NavigationDestination(
      icon: Icon(Icons.local_fire_department_outlined),
      selectedIcon: Icon(Icons.local_fire_department),
      label: 'Deals',
    ),
    NavigationDestination(
      icon: Icon(Icons.search_outlined),
      selectedIcon: Icon(Icons.search),
      label: 'Search',
    ),
    NavigationDestination(
      icon: Icon(Icons.bookmark_outline),
      selectedIcon: Icon(Icons.bookmark),
      label: 'Saved',
    ),
    NavigationDestination(
      icon: Icon(Icons.diamond_outlined),
      selectedIcon: Icon(Icons.diamond),
      label: 'Membership',
    ),
    NavigationDestination(
      icon: Icon(Icons.settings_outlined),
      selectedIcon: Icon(Icons.settings),
      label: 'Settings',
    ),
  ];

  static const _screens = [
    DealsScreen(),
    SearchScreen(),
    SavedScreen(),
    MembershipScreen(),
    SettingsScreen(),
  ];

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: IndexedStack(
        index: _index,
        children: _screens,
      ),
      bottomNavigationBar: NavigationBar(
        selectedIndex: _index,
        onDestinationSelected: (i) => setState(() => _index = i),
        destinations: _destinations,
      ),
    );
  }
}
