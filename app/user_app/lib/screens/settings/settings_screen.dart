import 'package:cloud_firestore/cloud_firestore.dart';
import 'package:firebase_auth/firebase_auth.dart';
import 'package:firebase_messaging/firebase_messaging.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:shared_preferences/shared_preferences.dart';
import '../../l10n/app_strings.dart';
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
      });
    }
  }

  Future<void> _pickLanguage() async {
    final currentLang = ref.read(localeProvider).languageCode;
    final picked = await showDialog<String>(
      context: context,
      builder: (_) => SimpleDialog(
        title: Text(context.s('select_language')),
        children: [
          RadioListTile<String>(
            value: 'en',
            groupValue: currentLang,
            title: const Text('English'),
            onChanged: (v) => Navigator.pop(context, v),
          ),
          RadioListTile<String>(
            value: 'ar',
            groupValue: currentLang,
            title: const Text('العربية'),
            onChanged: (v) => Navigator.pop(context, v),
          ),
        ],
      ),
    );
    if (picked == null || picked == currentLang) return;
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString('language', picked);
    ref.read(localeProvider.notifier).state = Locale(picked);
    if (mounted) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(picked == 'ar'
              ? context.s('lang_changed_ar')
              : context.s('lang_changed_en')),
        ),
      );
    }
  }

  Future<void> _toggleNotifications(bool value) async {
    final fcm = FirebaseMessaging.instance;

    if (value) {
      // Request permission first; abort if denied.
      final status = await fcm.requestPermission();
      if (status.authorizationStatus != AuthorizationStatus.authorized &&
          status.authorizationStatus != AuthorizationStatus.provisional) {
        return;
      }
      // Subscribe to deal-broadcast topics + personal alert topic.
      final uid = FirebaseAuth.instance.currentUser?.uid;
      final user = ref.read(currentUserProvider).valueOrNull;
      final tier = user?.membership.tier ?? 'free';

      await Future.wait([
        fcm.subscribeToTopic('tier_free'),
        if (tier == 'premium' || tier == 'vip') fcm.subscribeToTopic('tier_premium'),
        if (tier == 'vip') fcm.subscribeToTopic('tier_vip'),
        if (uid != null) fcm.subscribeToTopic('user_$uid'),
      ]);
    } else {
      // Unsubscribe from all deal topics.
      final uid = FirebaseAuth.instance.currentUser?.uid;
      await Future.wait([
        fcm.unsubscribeFromTopic('tier_free'),
        fcm.unsubscribeFromTopic('tier_premium'),
        fcm.unsubscribeFromTopic('tier_vip'),
        if (uid != null) fcm.unsubscribeFromTopic('user_$uid'),
      ]);
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
        title: Text(context.s('sign_out')),
        content: Text(context.s('sign_out_confirm')),
        actions: [
          TextButton(
              onPressed: () => Navigator.pop(context, false),
              child: Text(context.s('cancel'))),
          FilledButton(
              onPressed: () => Navigator.pop(context, true),
              child: Text(context.s('sign_out'))),
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
    final currentLang = ref.watch(localeProvider).languageCode;

    return Scaffold(
      appBar: AppBar(title: Text(context.s('settings_title'))),
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
          _SectionHeader(label: context.s('region_language')),
          ListTile(
            leading: const Icon(Icons.public_outlined),
            title: Text(context.s('country')),
            subtitle: Text(user?.country ?? 'AE'),
            trailing: const Icon(Icons.chevron_right),
            onTap: user == null ? null : () => _pickCountry(context, user),
          ),
          ListTile(
            leading: const Icon(Icons.language_outlined),
            title: Text(context.s('language')),
            subtitle: Text(currentLang == 'ar' ? 'العربية' : 'English'),
            trailing: const Icon(Icons.chevron_right),
            onTap: _pickLanguage,
          ),

          const Divider(),

          // Notifications
          _SectionHeader(label: context.s('notifications_section')),
          ListTile(
            leading: const Icon(Icons.notifications_outlined),
            title: Text(context.s('price_drop_alerts')),
            subtitle: Text(context.s('price_drop_subtitle')),
            trailing: Switch(
              value: _notificationsEnabled,
              onChanged: _toggleNotifications,
            ),
          ),

          const Divider(),

          // Referral
          if (user != null) ...[
            _SectionHeader(label: context.s('referral_section')),
            if (user.referralCode != null)
              ListTile(
                leading: const Icon(Icons.card_giftcard_outlined),
                title: Text(context.s('your_referral_code')),
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
                      SnackBar(content: Text(context.s('code_copied'))),
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
                        decoration: InputDecoration(
                          labelText: context.s('enter_referral'),
                          border: const OutlineInputBorder(),
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
                          : Text(context.s('apply')),
                    ),
                  ],
                ),
              ),
            const Divider(),
          ],

          // About
          _SectionHeader(label: context.s('about_section')),
          ListTile(
            leading: const Icon(Icons.info_outline),
            title: Text(context.s('version')),
            trailing: const Text('1.0.0'),
          ),

          const SizedBox(height: 8),

          // Sign out
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
            child: OutlinedButton.icon(
              icon: const Icon(Icons.logout),
              label: Text(context.s('sign_out')),
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
            ListTile(
              title: Text(context.s('select_country'),
                  style: const TextStyle(fontWeight: FontWeight.bold)),
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
