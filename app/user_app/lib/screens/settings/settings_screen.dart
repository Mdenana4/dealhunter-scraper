import 'package:cloud_firestore/cloud_firestore.dart';
import 'package:firebase_auth/firebase_auth.dart';
import 'package:firebase_messaging/firebase_messaging.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:shared_preferences/shared_preferences.dart';
import '../../models/user_model.dart';
import '../../providers/app_providers.dart';

class SettingsScreen extends ConsumerStatefulWidget {
  const SettingsScreen({super.key});

  @override
  ConsumerState<SettingsScreen> createState() => _SettingsScreenState();
}

class _SettingsScreenState extends ConsumerState<SettingsScreen> {
  final _referralCtrl = TextEditingController();
  bool _applyingReferral = false;
  bool _notificationsEnabled = true;
  String _language = 'en'; // 'en' or 'ar'

  @override
  void initState() {
    super.initState();
    _loadNotificationPref();
  }

  Future<void> _loadNotificationPref() async {
    final prefs = await SharedPreferences.getInstance();
    if (mounted) {
      setState(() {
        _notificationsEnabled = prefs.getBool('notifications_enabled') ?? true;
        _language = prefs.getString('language') ?? 'en';
      });
    }
  }

  Future<void> _pickLanguage() async {
    final picked = await showDialog<String>(
      context: context,
      builder: (_) => SimpleDialog(
        title: const Text('Select Language'),
        children: [
          RadioListTile<String>(
            value: 'en',
            groupValue: _language,
            title: const Text('English'),
            onChanged: (v) => Navigator.pop(context, v),
          ),
          RadioListTile<String>(
            value: 'ar',
            groupValue: _language,
            title: const Text('العربية'),
            onChanged: (v) => Navigator.pop(context, v),
          ),
        ],
      ),
    );
    if (picked == null || picked == _language) return;
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString('language', picked);
    // Update locale provider — takes effect immediately, no restart needed.
    ref.read(localeProvider.notifier).state = Locale(picked);
    if (mounted) {
      setState(() => _language = picked);
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(picked == 'ar'
              ? 'تم تغيير اللغة إلى العربية'
              : 'Language changed to English'),
        ),
      );
    }
  }

  Future<void> _toggleNotifications(bool value) async {
    if (value) {
      final status = await FirebaseMessaging.instance.requestPermission();
      if (status.authorizationStatus != AuthorizationStatus.authorized &&
          status.authorizationStatus != AuthorizationStatus.provisional) {
        return; // User denied — don't update the toggle
      }
    }
    final prefs = await SharedPreferences.getInstance();
    await prefs.setBool('notifications_enabled', value);
    if (mounted) setState(() => _notificationsEnabled = value);
  }

  @override
  void dispose() {
    _referralCtrl.dispose();
    super.dispose();
  }

  Future<void> _signOut() async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (_) => AlertDialog(
        title: const Text('Sign Out'),
        content: const Text('Are you sure you want to sign out?'),
        actions: [
          TextButton(
              onPressed: () => Navigator.pop(context, false),
              child: const Text('Cancel')),
          FilledButton(
              onPressed: () => Navigator.pop(context, true),
              child: const Text('Sign Out')),
        ],
      ),
    );
    if (confirmed == true) {
      await FirebaseAuth.instance.signOut();
      if (mounted) context.go('/login');
    }
  }

  Future<void> _applyReferral(String uid) async {
    final code = _referralCtrl.text.trim().toUpperCase();
    if (code.isEmpty) return;
    setState(() => _applyingReferral = true);
    try {
      final result = await ref.read(apiServiceProvider).applyReferral(uid, code);
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(result['message'] as String? ?? 'Referral applied!'),
        ),
      );
      _referralCtrl.clear();
    } catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Failed: $e')),
      );
    } finally {
      if (mounted) setState(() => _applyingReferral = false);
    }
  }

  Future<void> _updateField(String uid, String field, dynamic value) async {
    await FirebaseFirestore.instance
        .collection('users')
        .doc(uid)
        .update({field: value});
  }

  @override
  Widget build(BuildContext context) {
    final userAsync = ref.watch(currentUserProvider);
    final user = userAsync.valueOrNull;
    final cs = Theme.of(context).colorScheme;

    return Scaffold(
      appBar: AppBar(title: const Text('Settings')),
      body: ListView(
        children: [
          // User info
          if (user != null) ...[
            ListTile(
              leading: CircleAvatar(
                backgroundColor: cs.primaryContainer,
                child: Text(
                  (user.displayName.isNotEmpty
                          ? user.displayName[0]
                          : user.email.isNotEmpty
                              ? user.email[0]
                              : '?')
                      .toUpperCase(),
                  style: TextStyle(color: cs.onPrimaryContainer),
                ),
              ),
              title: Text(user.displayName.isNotEmpty
                  ? user.displayName
                  : user.email),
              subtitle: Text(
                  '${user.membership.displayLabel} plan  •  ${user.email}'),
            ),
            const Divider(),
          ],

          // Region & Language
          _SectionHeader(label: 'Region & Language'),
          ListTile(
            leading: const Icon(Icons.public_outlined),
            title: const Text('Country'),
            subtitle: Text(user?.country ?? 'AE'),
            trailing: const Icon(Icons.chevron_right),
            onTap: user == null ? null : () => _pickCountry(context, user),
          ),
          ListTile(
            leading: const Icon(Icons.language_outlined),
            title: const Text('Language'),
            subtitle: Text(_language == 'ar' ? 'العربية' : 'English'),
            trailing: const Icon(Icons.chevron_right),
            onTap: _pickLanguage,
          ),

          const Divider(),

          // Notifications
          _SectionHeader(label: 'Notifications'),
          ListTile(
            leading: const Icon(Icons.notifications_outlined),
            title: const Text('Price drop alerts'),
            subtitle: const Text('Get notified when deals drop in price'),
            trailing: Switch(
              value: _notificationsEnabled,
              onChanged: _toggleNotifications,
            ),
          ),

          const Divider(),

          // Referral
          if (user != null) ...[
            _SectionHeader(label: 'Referral'),
            if (user.referralCode != null)
              ListTile(
                leading: const Icon(Icons.card_giftcard_outlined),
                title: const Text('Your referral code'),
                subtitle: Text(
                  user.referralCode!,
                  style: TextStyle(
                      fontWeight: FontWeight.bold,
                      color: cs.primary,
                      fontSize: 16),
                ),
                trailing: IconButton(
                  icon: const Icon(Icons.copy_outlined),
                  onPressed: () {
                    ScaffoldMessenger.of(context).showSnackBar(
                      const SnackBar(content: Text('Code copied')),
                    );
                  },
                ),
              ),
            if (user.referralCode == null)
              Padding(
                padding: const EdgeInsets.symmetric(
                    horizontal: 16, vertical: 8),
                child: Row(
                  children: [
                    Expanded(
                      child: TextField(
                        controller: _referralCtrl,
                        textCapitalization: TextCapitalization.characters,
                        decoration: const InputDecoration(
                          labelText: 'Enter referral code',
                          border: OutlineInputBorder(),
                          isDense: true,
                        ),
                      ),
                    ),
                    const SizedBox(width: 8),
                    FilledButton(
                      onPressed:
                          _applyingReferral ? null : () => _applyReferral(user.uid),
                      child: _applyingReferral
                          ? const SizedBox(
                              width: 18,
                              height: 18,
                              child: CircularProgressIndicator(
                                  strokeWidth: 2,
                                  color: Colors.white),
                            )
                          : const Text('Apply'),
                    ),
                  ],
                ),
              ),
            const Divider(),
          ],

          // About
          _SectionHeader(label: 'About'),
          ListTile(
            leading: const Icon(Icons.info_outline),
            title: const Text('Version'),
            trailing: const Text('1.0.0'),
          ),

          const SizedBox(height: 8),

          // Sign out
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
            child: OutlinedButton.icon(
              icon: const Icon(Icons.logout),
              label: const Text('Sign Out'),
              style: OutlinedButton.styleFrom(
                foregroundColor: cs.error,
              ),
              onPressed: _signOut,
            ),
          ),
          const SizedBox(height: 24),
        ],
      ),
    );
  }

  void _pickCountry(BuildContext context, UserModel user) {
    const countries = [
      ('AE', 'United Arab Emirates'),
      ('SA', 'Saudi Arabia'),
      ('KW', 'Kuwait'),
      ('BH', 'Bahrain'),
      ('QA', 'Qatar'),
      ('OM', 'Oman'),
      ('EG', 'Egypt'),
    ];
    showModalBottomSheet(
      context: context,
      builder: (_) => SafeArea(
        child: ListView(
          shrinkWrap: true,
          children: [
            const ListTile(
              title: Text('Select Country',
                  style: TextStyle(fontWeight: FontWeight.bold)),
            ),
            for (final (code, name) in countries)
              ListTile(
                title: Text(name),
                trailing: user.country == code
                    ? Icon(Icons.check,
                        color: Theme.of(context).colorScheme.primary)
                    : null,
                onTap: () {
                  Navigator.pop(context);
                  _updateField(user.uid, 'country', code);
                },
              ),
          ],
        ),
      ),
    );
  }
}

class _SectionHeader extends StatelessWidget {
  const _SectionHeader({required this.label});

  final String label;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.fromLTRB(16, 12, 16, 4),
      child: Text(
        label.toUpperCase(),
        style: TextStyle(
          fontSize: 11,
          fontWeight: FontWeight.w600,
          color: Theme.of(context).colorScheme.primary,
          letterSpacing: 0.8,
        ),
      ),
    );
  }
}
