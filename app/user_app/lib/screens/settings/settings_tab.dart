import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import '../../models/membership.dart';
import '../../models/user_profile.dart';
import '../../providers/auth_provider.dart';
import '../../services/auth_service.dart';
import '../../config/theme.dart';

class SettingsTab extends ConsumerStatefulWidget {
  const SettingsTab({super.key});

  @override
  ConsumerState<SettingsTab> createState() => _SettingsTabState();
}

class _SettingsTabState extends ConsumerState<SettingsTab> {
  @override
  Widget build(BuildContext context) {
    final userProfile = ref.watch(userProfileProvider).value;
    final user = ref.watch(firebaseUserProvider).value;

    if (user == null) {
      return Scaffold(
        appBar: AppBar(title: const Text('Settings')),
        body: Center(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              const Icon(Icons.person_outline, size: 72, color: Colors.grey),
              const SizedBox(height: 16),
              const Text('Sign in to access settings'),
              const SizedBox(height: 16),
              ElevatedButton(
                onPressed: () => context.push('/login'),
                child: const Text('Sign In'),
              ),
            ],
          ),
        ),
      );
    }

    return Scaffold(
      appBar: AppBar(
        title: const Text('⚙️ Settings'),
        backgroundColor: AppTheme.primary,
      ),
      body: ListView(
        children: [
          // Profile card
          _ProfileCard(profile: userProfile, email: user.email),

          const SizedBox(height: 8),

          // Notification preferences
          if (userProfile != null)
            _NotificationSection(profile: userProfile),

          const SizedBox(height: 8),

          // App preferences
          _AppPreferencesSection(profile: userProfile),

          const SizedBox(height: 8),

          // Referral
          _ReferralSection(profile: userProfile),

          const SizedBox(height: 8),

          // Account actions
          _AccountSection(
            onSignOut: () async {
              await ref.read(authServiceProvider).signOut();
              if (!mounted) return;
              context.go('/login');
            },
          ),

          const SizedBox(height: 32),
        ],
      ),
    );
  }
}

class _ProfileCard extends StatelessWidget {
  final UserProfile? profile;
  final String? email;
  const _ProfileCard({this.profile, this.email});

  @override
  Widget build(BuildContext context) {
    final tier = profile?.membership.tier ?? MembershipTier.free;
    final tierColor = AppTheme.tierColor(tier.id);

    return Container(
      margin: const EdgeInsets.all(16),
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: AppTheme.primary,
        borderRadius: BorderRadius.circular(20),
      ),
      child: Row(
        children: [
          CircleAvatar(
            radius: 32,
            backgroundColor: Colors.white.withOpacity(0.2),
            backgroundImage: profile?.photoUrl != null
                ? NetworkImage(profile!.photoUrl!)
                : null,
            child: profile?.photoUrl == null
                ? const Icon(Icons.person, color: Colors.white, size: 36)
                : null,
          ),
          const SizedBox(width: 14),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  profile?.displayName ?? 'User',
                  style: const TextStyle(
                      color: Colors.white,
                      fontSize: 18,
                      fontWeight: FontWeight.w700),
                ),
                if (email != null)
                  Text(email!,
                      style: const TextStyle(
                          color: Colors.white70, fontSize: 13)),
                const SizedBox(height: 6),
                Container(
                  padding: const EdgeInsets.symmetric(
                      horizontal: 10, vertical: 3),
                  decoration: BoxDecoration(
                    color: tierColor,
                    borderRadius: BorderRadius.circular(12),
                  ),
                  child: Text(
                    '${tier.displayName} Member',
                    style: const TextStyle(
                        color: Colors.white,
                        fontSize: 11,
                        fontWeight: FontWeight.w600),
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class _NotificationSection extends ConsumerStatefulWidget {
  final UserProfile profile;
  const _NotificationSection({required this.profile});

  @override
  ConsumerState<_NotificationSection> createState() =>
      _NotificationSectionState();
}

class _NotificationSectionState extends ConsumerState<_NotificationSection> {
  late NotificationPreferences _prefs;
  bool _saving = false;

  @override
  void initState() {
    super.initState();
    _prefs = widget.profile.notifications;
  }

  Future<void> _save() async {
    setState(() => _saving = true);
    await ref.read(authServiceProvider).updateNotificationPreferences(
        widget.profile.uid, _prefs);
    setState(() => _saving = false);
  }

  @override
  Widget build(BuildContext context) {
    final tier = widget.profile.membership.tier;

    return _Section(
      title: '🔔 Notifications',
      children: [
        SwitchListTile(
          title: const Text('Enable notifications'),
          subtitle: const Text('Get alerts for new deals'),
          value: _prefs.enabled,
          onChanged: (v) {
            setState(() => _prefs = NotificationPreferences(
                enabled: v,
                quietHours: _prefs.quietHours,
                quietStart: _prefs.quietStart,
                quietEnd: _prefs.quietEnd,
                minDiscountPct: _prefs.minDiscountPct,
                categories: _prefs.categories,
                brands: _prefs.brands,
                sizes: _prefs.sizes,
                marketplaces: _prefs.marketplaces,
                groupNotifications: _prefs.groupNotifications));
            _save();
          },
          activeColor: AppTheme.primary,
        ),
        SwitchListTile(
          title: const Text('Quiet hours'),
          subtitle: const Text('No notifications 11 PM – 7 AM'),
          value: _prefs.quietHours,
          onChanged: (v) {
            setState(() => _prefs = NotificationPreferences(
                enabled: _prefs.enabled,
                quietHours: v,
                quietStart: _prefs.quietStart,
                quietEnd: _prefs.quietEnd,
                minDiscountPct: _prefs.minDiscountPct,
                categories: _prefs.categories,
                brands: _prefs.brands,
                sizes: _prefs.sizes,
                marketplaces: _prefs.marketplaces,
                groupNotifications: _prefs.groupNotifications));
            _save();
          },
          activeColor: AppTheme.primary,
        ),
        SwitchListTile(
          title: const Text('Group notifications'),
          subtitle: const Text('Batch multiple deals into one alert'),
          value: _prefs.groupNotifications,
          onChanged: (v) {
            setState(() => _prefs = NotificationPreferences(
                enabled: _prefs.enabled,
                quietHours: _prefs.quietHours,
                quietStart: _prefs.quietStart,
                quietEnd: _prefs.quietEnd,
                minDiscountPct: _prefs.minDiscountPct,
                categories: _prefs.categories,
                brands: _prefs.brands,
                sizes: _prefs.sizes,
                marketplaces: _prefs.marketplaces,
                groupNotifications: v));
            _save();
          },
          activeColor: AppTheme.primary,
        ),

        // Min discount slider
        ListTile(
          title: const Text('Minimum discount'),
          subtitle: Text('${_prefs.minDiscountPct.toStringAsFixed(0)}% or more'),
          trailing: SizedBox(
            width: 150,
            child: Slider(
              value: _prefs.minDiscountPct,
              min: 10,
              max: 80,
              divisions: 14,
              label: '${_prefs.minDiscountPct.toStringAsFixed(0)}%',
              onChanged: (v) {
                setState(() => _prefs = NotificationPreferences(
                    enabled: _prefs.enabled,
                    quietHours: _prefs.quietHours,
                    quietStart: _prefs.quietStart,
                    quietEnd: _prefs.quietEnd,
                    minDiscountPct: v,
                    categories: _prefs.categories,
                    brands: _prefs.brands,
                    sizes: _prefs.sizes,
                    marketplaces: _prefs.marketplaces,
                    groupNotifications: _prefs.groupNotifications));
              },
              onChangeEnd: (_) => _save(),
              activeColor: AppTheme.primary,
            ),
          ),
        ),

        // Category filter (Basic+)
        if (tier.canFilterCategory)
          ListTile(
            leading: const Icon(Icons.category_outlined),
            title: const Text('Category filter'),
            subtitle: Text(_prefs.categories.isEmpty
                ? 'All categories'
                : _prefs.categories.join(', ')),
            trailing: const Icon(Icons.chevron_right),
            onTap: () => _showCategoryPicker(context),
          ),

        // Brand / size filter (Premium+)
        if (tier.canFilterSize) ...[
          ListTile(
            leading: const Icon(Icons.label_outline),
            title: const Text('Brand filter'),
            subtitle: Text(_prefs.brands.isEmpty
                ? 'All brands'
                : _prefs.brands.join(', ')),
            trailing: const Icon(Icons.chevron_right),
            onTap: () {},
          ),
          ListTile(
            leading: const Icon(Icons.straighten_outlined),
            title: const Text('Size filter'),
            subtitle: Text(_prefs.sizes.isEmpty
                ? 'All sizes'
                : _prefs.sizes.join(', ')),
            trailing: const Icon(Icons.chevron_right),
            onTap: () {},
          ),
        ],
      ],
    );
  }

  void _showCategoryPicker(BuildContext context) {
    final all = ['Electronics', 'Fashion', 'Home', 'Sports',
                  'Beauty', 'Books', 'Toys', 'Grocery'];
    showDialog(
      context: context,
      builder: (_) => StatefulBuilder(
        builder: (ctx, setState2) => AlertDialog(
          title: const Text('Select categories'),
          content: SingleChildScrollView(
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: all.map((c) => CheckboxListTile(
                    title: Text(c),
                    value: _prefs.categories.contains(c),
                    onChanged: (v) {
                      setState2(() {
                        final list = List<String>.from(_prefs.categories);
                        if (v == true) list.add(c);
                        else list.remove(c);
                        _prefs = NotificationPreferences(
                          enabled: _prefs.enabled,
                          quietHours: _prefs.quietHours,
                          quietStart: _prefs.quietStart,
                          quietEnd: _prefs.quietEnd,
                          minDiscountPct: _prefs.minDiscountPct,
                          categories: list,
                          brands: _prefs.brands,
                          sizes: _prefs.sizes,
                          marketplaces: _prefs.marketplaces,
                          groupNotifications: _prefs.groupNotifications,
                        );
                      });
                      setState(() {});
                    },
                    activeColor: AppTheme.primary,
                  )).toList(),
            ),
          ),
          actions: [
            TextButton(onPressed: () => Navigator.pop(context),
                child: const Text('Done')),
          ],
        ),
      ),
    ).then((_) => _save());
  }
}

class _AppPreferencesSection extends ConsumerWidget {
  final UserProfile? profile;
  const _AppPreferencesSection({this.profile});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final prefs = profile?.preferences ?? const AppPreferences();

    return _Section(
      title: '🎨 App Settings',
      children: [
        ListTile(
          leading: const Icon(Icons.language),
          title: const Text('Language'),
          trailing: DropdownButton<String>(
            value: prefs.language,
            underline: const SizedBox(),
            items: const [
              DropdownMenuItem(value: 'en', child: Text('English')),
              DropdownMenuItem(value: 'ar', child: Text('العربية')),
            ],
            onChanged: (v) async {
              if (v == null || profile == null) return;
              await ref.read(authServiceProvider).updateAppPreferences(
                profile!.uid,
                AppPreferences(
                  language: v,
                  theme: prefs.theme,
                  currency: prefs.currency,
                  country: prefs.country,
                ),
              );
            },
          ),
        ),
        ListTile(
          leading: const Icon(Icons.dark_mode_outlined),
          title: const Text('Theme'),
          trailing: DropdownButton<String>(
            value: prefs.theme,
            underline: const SizedBox(),
            items: const [
              DropdownMenuItem(value: 'system', child: Text('System')),
              DropdownMenuItem(value: 'light', child: Text('Light')),
              DropdownMenuItem(value: 'dark', child: Text('Dark')),
            ],
            onChanged: (v) async {
              if (v == null || profile == null) return;
              await ref.read(authServiceProvider).updateAppPreferences(
                profile!.uid,
                AppPreferences(
                  language: prefs.language,
                  theme: v,
                  currency: prefs.currency,
                  country: prefs.country,
                ),
              );
            },
          ),
        ),
        ListTile(
          leading: const Icon(Icons.location_on_outlined),
          title: const Text('Country'),
          trailing: DropdownButton<String>(
            value: prefs.country,
            underline: const SizedBox(),
            items: const [
              DropdownMenuItem(value: 'eg', child: Text('🇪🇬 Egypt')),
              DropdownMenuItem(value: 'ae', child: Text('🇦🇪 UAE')),
              DropdownMenuItem(value: 'sa', child: Text('🇸🇦 Saudi Arabia')),
            ],
            onChanged: (v) async {
              if (v == null || profile == null) return;
              final currency = v == 'eg' ? 'EGP' : v == 'ae' ? 'AED' : 'SAR';
              await ref.read(authServiceProvider).updateAppPreferences(
                profile!.uid,
                AppPreferences(
                  language: prefs.language,
                  theme: prefs.theme,
                  currency: currency,
                  country: v,
                ),
              );
            },
          ),
        ),
      ],
    );
  }
}

class _ReferralSection extends StatelessWidget {
  final UserProfile? profile;
  const _ReferralSection({this.profile});

  @override
  Widget build(BuildContext context) {
    if (profile?.referralCode == null) return const SizedBox();

    return _Section(
      title: '🎁 Refer & Earn',
      children: [
        ListTile(
          title: const Text('Your referral code'),
          subtitle: Text(
            profile!.referralCode!,
            style: const TextStyle(
                fontSize: 22,
                fontWeight: FontWeight.w700,
                letterSpacing: 4,
                color: AppTheme.primary),
          ),
          trailing: IconButton(
            icon: const Icon(Icons.copy),
            onPressed: () {
              ScaffoldMessenger.of(context).showSnackBar(
                const SnackBar(content: Text('Referral code copied!')),
              );
            },
          ),
        ),
        const Padding(
          padding: EdgeInsets.fromLTRB(16, 0, 16, 12),
          child: Text(
            'Share your code. When a friend subscribes, you both get a bonus.',
            style: TextStyle(fontSize: 12, color: Colors.grey),
          ),
        ),
      ],
    );
  }
}

class _AccountSection extends StatelessWidget {
  final VoidCallback onSignOut;
  const _AccountSection({required this.onSignOut});

  @override
  Widget build(BuildContext context) {
    return _Section(
      title: '👤 Account',
      children: [
        ListTile(
          leading: const Icon(Icons.lock_outline),
          title: const Text('Change Password'),
          trailing: const Icon(Icons.chevron_right),
          onTap: () {},
        ),
        ListTile(
          leading: const Icon(Icons.privacy_tip_outlined),
          title: const Text('Privacy Policy'),
          trailing: const Icon(Icons.chevron_right),
          onTap: () {},
        ),
        ListTile(
          leading: const Icon(Icons.description_outlined),
          title: const Text('Terms of Service'),
          trailing: const Icon(Icons.chevron_right),
          onTap: () {},
        ),
        ListTile(
          leading: const Icon(Icons.feedback_outlined),
          title: const Text('Send Feedback'),
          trailing: const Icon(Icons.chevron_right),
          onTap: () {},
        ),
        const Divider(),
        ListTile(
          leading: const Icon(Icons.logout, color: AppTheme.fake),
          title: const Text('Sign Out',
              style: TextStyle(color: AppTheme.fake)),
          onTap: onSignOut,
        ),
        ListTile(
          leading: const Icon(Icons.delete_outline, color: Colors.grey),
          title: const Text('Delete Account',
              style: TextStyle(color: Colors.grey)),
          subtitle: const Text('Permanently delete your data'),
          onTap: () {},
        ),
      ],
    );
  }
}

class _Section extends StatelessWidget {
  final String title;
  final List<Widget> children;
  const _Section({required this.title, required this.children});

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Padding(
          padding: const EdgeInsets.fromLTRB(16, 16, 16, 8),
          child: Text(title,
              style: Theme.of(context).textTheme.titleMedium
                  ?.copyWith(fontWeight: FontWeight.w700)),
        ),
        Card(
          margin: const EdgeInsets.symmetric(horizontal: 16),
          child: Column(children: children),
        ),
      ],
    );
  }
}
