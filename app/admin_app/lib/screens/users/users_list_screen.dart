import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../providers/admin_providers.dart';

class UsersListScreen extends ConsumerStatefulWidget {
  const UsersListScreen({super.key});

  @override
  ConsumerState<UsersListScreen> createState() => _UsersListScreenState();
}

class _UsersListScreenState extends ConsumerState<UsersListScreen>
    with SingleTickerProviderStateMixin {
  late TabController _tabs;
  String _search = '';
  String _tierFilter = 'all';

  @override
  void initState() {
    super.initState();
    _tabs = TabController(length: 2, vsync: this);
  }

  @override
  void dispose() {
    _tabs.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Users'),
        bottom: TabBar(
          controller: _tabs,
          tabs: const [
            Tab(icon: Icon(Icons.person), text: 'All Users'),
            Tab(icon: Icon(Icons.tune), text: 'Bulk Actions'),
          ],
        ),
        actions: [
          IconButton(
            icon: const Icon(Icons.refresh),
            onPressed: () => ref.invalidate(usersStreamProvider),
          ),
        ],
      ),
      body: TabBarView(
        controller: _tabs,
        children: [
          _UserListTab(
            search: _search,
            tierFilter: _tierFilter,
            onSearchChanged: (v) => setState(() => _search = v),
            onTierChanged: (v) => setState(() => _tierFilter = v),
          ),
          const _BulkActionsTab(),
        ],
      ),
    );
  }
}

// ─── Tab 1: User list ──────────────────────────────────────────────────────

class _UserListTab extends ConsumerWidget {
  final String search;
  final String tierFilter;
  final ValueChanged<String> onSearchChanged;
  final ValueChanged<String> onTierChanged;

  const _UserListTab({
    required this.search,
    required this.tierFilter,
    required this.onSearchChanged,
    required this.onTierChanged,
  });

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final usersAsync = ref.watch(usersStreamProvider);

    return Column(
      children: [
        // Search + filter bar
        Container(
          color: Colors.grey.shade50,
          padding: const EdgeInsets.all(12),
          child: Column(children: [
            TextField(
              onChanged: onSearchChanged,
              decoration: InputDecoration(
                hintText: 'Search by email or name…',
                prefixIcon: const Icon(Icons.search),
                border: OutlineInputBorder(
                    borderRadius: BorderRadius.circular(8)),
                contentPadding: const EdgeInsets.symmetric(vertical: 8),
                fillColor: Colors.white,
                filled: true,
              ),
            ),
            const SizedBox(height: 8),
            SingleChildScrollView(
              scrollDirection: Axis.horizontal,
              child: Row(
                children: ['all', 'free', 'basic', 'premium', 'vip']
                    .map((t) => Padding(
                          padding: const EdgeInsets.only(right: 6),
                          child: FilterChip(
                            label: Text(t.toUpperCase()),
                            selected: tierFilter == t,
                            onSelected: (_) => onTierChanged(t),
                            selectedColor:
                                _tierColor(t).withOpacity(0.2),
                            labelStyle: TextStyle(
                                color: tierFilter == t
                                    ? _tierColor(t)
                                    : Colors.grey.shade700,
                                fontWeight: tierFilter == t
                                    ? FontWeight.w700
                                    : FontWeight.normal),
                          ),
                        ))
                    .toList(),
              ),
            ),
          ]),
        ),

        // List
        Expanded(
          child: usersAsync.when(
            loading: () => const Center(child: CircularProgressIndicator()),
            error: (e, _) => Center(child: Text('Error: $e')),
            data: (users) {
              final filtered = users.where((u) {
                final email = (u['email'] as String? ?? '').toLowerCase();
                final name = (u['display_name'] as String? ?? '').toLowerCase();
                final tier = (u['membership'] as Map?)?['tier'] as String? ?? 'free';
                final matchSearch = search.isEmpty ||
                    email.contains(search.toLowerCase()) ||
                    name.contains(search.toLowerCase());
                final matchTier =
                    tierFilter == 'all' || tier == tierFilter;
                return matchSearch && matchTier;
              }).toList();

              if (filtered.isEmpty) {
                return const Center(child: Text('No users found.'));
              }

              return ListView.separated(
                itemCount: filtered.length,
                separatorBuilder: (_, __) => const Divider(height: 1),
                itemBuilder: (ctx, i) {
                  final u = filtered[i];
                  return _UserTile(user: u);
                },
              );
            },
          ),
        ),
      ],
    );
  }
}

class _UserTile extends ConsumerWidget {
  final Map<String, dynamic> user;
  const _UserTile({required this.user});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final email = user['email'] as String? ?? '—';
    final name = user['display_name'] as String? ?? '';
    final membership = user['membership'] as Map? ?? {};
    final tier = membership['tier'] as String? ?? 'free';
    final customPrice = membership['custom_price'] as num?;
    final customLimit = membership['custom_daily_limit'] as num?;

    return ListTile(
      leading: CircleAvatar(
        backgroundColor: _tierColor(tier).withOpacity(0.15),
        child: Text(
          (name.isNotEmpty ? name[0] : email[0]).toUpperCase(),
          style: TextStyle(color: _tierColor(tier), fontWeight: FontWeight.w700),
        ),
      ),
      title: Text(name.isNotEmpty ? name : email,
          style: const TextStyle(fontWeight: FontWeight.w600)),
      subtitle: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          if (name.isNotEmpty) Text(email, style: const TextStyle(fontSize: 12)),
          Row(children: [
            _TierBadge(tier),
            if (customPrice != null) ...[
              const SizedBox(width: 6),
              _Badge('EGP ${customPrice.toStringAsFixed(0)}/mo', Colors.orange),
            ],
            if (customLimit != null) ...[
              const SizedBox(width: 6),
              _Badge('Limit: $customLimit/day', Colors.blue),
            ],
          ]),
        ],
      ),
      trailing: PopupMenuButton<String>(
        icon: const Icon(Icons.more_vert),
        onSelected: (action) => _handleAction(context, ref, action),
        itemBuilder: (_) => const [
          PopupMenuItem(value: 'tier', child: Text('Change Tier')),
          PopupMenuItem(value: 'price', child: Text('Override Price')),
          PopupMenuItem(value: 'limit', child: Text('Override Daily Limit')),
          PopupMenuItem(value: 'notify', child: Text('Send Notification')),
          PopupMenuDivider(),
          PopupMenuItem(
              value: 'delete',
              child: Text('Delete User',
                  style: TextStyle(color: Colors.red))),
        ],
      ),
    );
  }

  Future<void> _handleAction(
      BuildContext context, WidgetRef ref, String action) async {
    final uid = user['id'] as String;
    final svc = ref.read(adminServiceProvider);

    switch (action) {
      case 'tier':
        await _showTierDialog(context, ref, uid);
        break;
      case 'price':
        await _showPriceDialog(context, ref, uid);
        break;
      case 'limit':
        await _showLimitDialog(context, ref, uid);
        break;
      case 'notify':
        await _showNotifyDialog(context, ref, uid);
        break;
      case 'delete':
        final ok = await _confirmDelete(context);
        if (ok && context.mounted) {
          await svc.deleteUser(uid);
          ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(content: Text('User deleted.')));
        }
        break;
    }
  }

  Future<void> _showTierDialog(
      BuildContext context, WidgetRef ref, String uid) async {
    final membership = user['membership'] as Map? ?? {};
    String selected = membership['tier'] as String? ?? 'free';

    await showDialog(
      context: context,
      builder: (_) => StatefulBuilder(
        builder: (ctx, setState2) => AlertDialog(
          title: const Text('Change Membership Tier'),
          content: Column(
            mainAxisSize: MainAxisSize.min,
            children: ['free', 'basic', 'premium', 'vip'].map((t) {
              return RadioListTile<String>(
                value: t,
                groupValue: selected,
                onChanged: (v) => setState2(() => selected = v!),
                title: Text(t.toUpperCase()),
                activeColor: _tierColor(t),
              );
            }).toList(),
          ),
          actions: [
            TextButton(
                onPressed: () => Navigator.pop(ctx),
                child: const Text('Cancel')),
            ElevatedButton(
              onPressed: () async {
                await ref
                    .read(adminServiceProvider)
                    .updateUserMembership(uid, tier: selected);
                if (ctx.mounted) {
                  Navigator.pop(ctx);
                  ScaffoldMessenger.of(ctx).showSnackBar(SnackBar(
                    content: Text(
                        'Tier changed to ${selected.toUpperCase()}'),
                    backgroundColor: Colors.green,
                  ));
                }
              },
              child: const Text('Save'),
            ),
          ],
        ),
      ),
    );
  }

  Future<void> _showPriceDialog(
      BuildContext context, WidgetRef ref, String uid) async {
    final ctrl = TextEditingController();
    await showDialog(
      context: context,
      builder: (_) => AlertDialog(
        title: const Text('Override Monthly Price (EGP)'),
        content: TextField(
          controller: ctrl,
          keyboardType: TextInputType.number,
          decoration: const InputDecoration(
            labelText: 'Custom price (EGP/month)',
            hintText: 'e.g. 39',
          ),
          autofocus: true,
        ),
        actions: [
          TextButton(
              onPressed: () => Navigator.pop(context),
              child: const Text('Cancel')),
          ElevatedButton(
            onPressed: () async {
              final price = double.tryParse(ctrl.text);
              if (price == null) return;
              await ref
                  .read(adminServiceProvider)
                  .updateUserMembership(uid,
                      tier: (user['membership'] as Map?)?['tier'] ?? 'free',
                      customPrice: price);
              if (context.mounted) {
                Navigator.pop(context);
                ScaffoldMessenger.of(context).showSnackBar(SnackBar(
                  content: Text(
                      'Price set to EGP ${price.toStringAsFixed(0)}/mo'),
                  backgroundColor: Colors.green,
                ));
              }
            },
            child: const Text('Save'),
          ),
        ],
      ),
    );
  }

  Future<void> _showLimitDialog(
      BuildContext context, WidgetRef ref, String uid) async {
    final ctrl = TextEditingController();
    await showDialog(
      context: context,
      builder: (_) => AlertDialog(
        title: const Text('Override Daily Deal Limit'),
        content: TextField(
          controller: ctrl,
          keyboardType: TextInputType.number,
          decoration: const InputDecoration(
            labelText: 'Deals per day',
            hintText: 'e.g. 100',
          ),
          autofocus: true,
        ),
        actions: [
          TextButton(
              onPressed: () => Navigator.pop(context),
              child: const Text('Cancel')),
          ElevatedButton(
            onPressed: () async {
              final limit = int.tryParse(ctrl.text);
              if (limit == null) return;
              await ref
                  .read(adminServiceProvider)
                  .updateUserMembership(uid,
                      tier: (user['membership'] as Map?)?['tier'] ?? 'free',
                      customDailyLimit: limit);
              if (context.mounted) {
                Navigator.pop(context);
                ScaffoldMessenger.of(context).showSnackBar(SnackBar(
                  content: Text('Daily limit set to $limit'),
                  backgroundColor: Colors.green,
                ));
              }
            },
            child: const Text('Save'),
          ),
        ],
      ),
    );
  }

  Future<void> _showNotifyDialog(
      BuildContext context, WidgetRef ref, String uid) async {
    final titleCtrl = TextEditingController();
    final bodyCtrl = TextEditingController();

    await showDialog(
      context: context,
      builder: (_) => AlertDialog(
        title: const Text('Send Notification'),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            TextField(
              controller: titleCtrl,
              decoration: const InputDecoration(labelText: 'Title'),
            ),
            const SizedBox(height: 12),
            TextField(
              controller: bodyCtrl,
              maxLines: 3,
              decoration: const InputDecoration(labelText: 'Message'),
            ),
          ],
        ),
        actions: [
          TextButton(
              onPressed: () => Navigator.pop(context),
              child: const Text('Cancel')),
          ElevatedButton(
            onPressed: () async {
              if (titleCtrl.text.isEmpty || bodyCtrl.text.isEmpty) return;
              try {
                await ref.read(adminServiceProvider).sendNotification(
                      title: titleCtrl.text,
                      body: bodyCtrl.text,
                      targetType: 'user',
                      targetId: uid,
                    );
                if (context.mounted) {
                  Navigator.pop(context);
                  ScaffoldMessenger.of(context).showSnackBar(const SnackBar(
                    content: Text('Notification sent.'),
                    backgroundColor: Colors.green,
                  ));
                }
              } catch (e) {
                if (context.mounted) {
                  ScaffoldMessenger.of(context).showSnackBar(
                    SnackBar(content: Text('Error: $e'),
                        backgroundColor: Colors.red));
                }
              }
            },
            child: const Text('Send'),
          ),
        ],
      ),
    );
  }

  Future<bool> _confirmDelete(BuildContext context) async {
    return await showDialog<bool>(
          context: context,
          builder: (_) => AlertDialog(
            title: const Text('Delete User?'),
            content: const Text(
                'This permanently deletes the user. Cannot be undone.'),
            actions: [
              TextButton(
                  onPressed: () => Navigator.pop(context, false),
                  child: const Text('Cancel')),
              ElevatedButton(
                onPressed: () => Navigator.pop(context, true),
                style:
                    ElevatedButton.styleFrom(backgroundColor: Colors.red),
                child: const Text('Delete'),
              ),
            ],
          ),
        ) ??
        false;
  }
}

// ─── Tab 2: Bulk actions ──────────────────────────────────────────────────

class _BulkActionsTab extends ConsumerStatefulWidget {
  const _BulkActionsTab();

  @override
  ConsumerState<_BulkActionsTab> createState() => _BulkActionsTabState();
}

class _BulkActionsTabState extends ConsumerState<_BulkActionsTab> {
  String _fromTier = 'basic';
  String _toTier   = 'premium';
  final _priceCtrl = TextEditingController();
  final _limitCtrl = TextEditingController();
  bool _loading = false;

  @override
  void dispose() {
    _priceCtrl.dispose();
    _limitCtrl.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Section: Bulk tier upgrade
          _SectionCard(
            title: 'Bulk Tier Change',
            subtitle:
                'Move all users from one tier to another tier at once.',
            child: Column(
              children: [
                Row(children: [
                  Expanded(child: _TierDropdown(
                    label: 'From tier',
                    value: _fromTier,
                    onChanged: (v) => setState(() => _fromTier = v!),
                  )),
                  const Padding(
                    padding: EdgeInsets.symmetric(horizontal: 12),
                    child: Icon(Icons.arrow_forward),
                  ),
                  Expanded(child: _TierDropdown(
                    label: 'To tier',
                    value: _toTier,
                    onChanged: (v) => setState(() => _toTier = v!),
                  )),
                ]),
                const SizedBox(height: 8),
                TextField(
                  controller: _priceCtrl,
                  keyboardType: TextInputType.number,
                  decoration: const InputDecoration(
                    labelText: 'Custom price override (EGP, optional)',
                    border: OutlineInputBorder(),
                  ),
                ),
                const SizedBox(height: 8),
                TextField(
                  controller: _limitCtrl,
                  keyboardType: TextInputType.number,
                  decoration: const InputDecoration(
                    labelText: 'Custom daily limit override (optional)',
                    border: OutlineInputBorder(),
                  ),
                ),
                const SizedBox(height: 12),
                SizedBox(
                  width: double.infinity,
                  child: ElevatedButton.icon(
                    onPressed: _loading ? null : _runBulkTierChange,
                    icon: _loading
                        ? const SizedBox(
                            width: 18, height: 18,
                            child: CircularProgressIndicator(
                                strokeWidth: 2, color: Colors.white))
                        : const Icon(Icons.swap_horiz),
                    label: Text(
                        'Change All ${_fromTier.toUpperCase()} → ${_toTier.toUpperCase()}'),
                  ),
                ),
              ],
            ),
          ),

          const SizedBox(height: 16),

          // Section: Broadcast to tier
          _SectionCard(
            title: 'Broadcast Notification to Tier',
            subtitle: 'Send a push notification to all users in a tier.',
            child: _TierBroadcastForm(),
          ),

          const SizedBox(height: 16),

          // Section: Stats per tier
          _SectionCard(
            title: 'User Counts by Tier',
            subtitle: 'Live from Firestore.',
            child: _TierCountTable(),
          ),
        ],
      ),
    );
  }

  Future<void> _runBulkTierChange() async {
    if (_fromTier == _toTier) {
      ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('From and To tiers must differ.')));
      return;
    }

    final confirm = await showDialog<bool>(
      context: context,
      builder: (_) => AlertDialog(
        title: const Text('Confirm Bulk Change'),
        content: Text(
            'This will move ALL ${_fromTier.toUpperCase()} users to ${_toTier.toUpperCase()}. Continue?'),
        actions: [
          TextButton(
              onPressed: () => Navigator.pop(context, false),
              child: const Text('Cancel')),
          ElevatedButton(
              onPressed: () => Navigator.pop(context, true),
              child: const Text('Confirm')),
        ],
      ),
    );

    if (confirm != true) return;

    setState(() => _loading = true);
    try {
      final count = await ref.read(adminServiceProvider).bulkChangeTier(
            fromTier: _fromTier,
            toTier: _toTier,
            customPrice: double.tryParse(_priceCtrl.text),
            customDailyLimit: int.tryParse(_limitCtrl.text),
          );
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(
        content: Text('$count users updated to ${_toTier.toUpperCase()}.'),
        backgroundColor: Colors.green,
      ));
    } catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Error: $e'), backgroundColor: Colors.red));
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }
}

class _TierBroadcastForm extends ConsumerStatefulWidget {
  @override
  ConsumerState<_TierBroadcastForm> createState() =>
      _TierBroadcastFormState();
}

class _TierBroadcastFormState extends ConsumerState<_TierBroadcastForm> {
  String _tier = 'all';
  final _titleCtrl = TextEditingController();
  final _bodyCtrl  = TextEditingController();
  bool _loading = false;

  @override
  void dispose() {
    _titleCtrl.dispose();
    _bodyCtrl.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Column(children: [
      DropdownButtonFormField<String>(
        value: _tier,
        decoration: const InputDecoration(
            labelText: 'Target', border: OutlineInputBorder()),
        items: [
          const DropdownMenuItem(value: 'all', child: Text('All Users')),
          ...['free', 'basic', 'premium', 'vip'].map((t) =>
              DropdownMenuItem(
                  value: t, child: Text(t.toUpperCase()))),
        ],
        onChanged: (v) => setState(() => _tier = v!),
      ),
      const SizedBox(height: 8),
      TextField(
        controller: _titleCtrl,
        decoration: const InputDecoration(
            labelText: 'Title', border: OutlineInputBorder()),
      ),
      const SizedBox(height: 8),
      TextField(
        controller: _bodyCtrl,
        maxLines: 3,
        decoration: const InputDecoration(
            labelText: 'Message', border: OutlineInputBorder()),
      ),
      const SizedBox(height: 10),
      SizedBox(
        width: double.infinity,
        child: ElevatedButton.icon(
          onPressed: _loading ? null : _send,
          icon: _loading
              ? const SizedBox(
                  width: 18, height: 18,
                  child: CircularProgressIndicator(
                      strokeWidth: 2, color: Colors.white))
              : const Icon(Icons.send),
          label: Text('Send to ${_tier == 'all' ? 'All Users' : _tier.toUpperCase()}'),
          style: ElevatedButton.styleFrom(backgroundColor: Colors.purple),
        ),
      ),
    ]);
  }

  Future<void> _send() async {
    if (_titleCtrl.text.isEmpty || _bodyCtrl.text.isEmpty) return;
    setState(() => _loading = true);
    try {
      final result = await ref.read(adminServiceProvider).sendNotification(
            title: _titleCtrl.text,
            body: _bodyCtrl.text,
            targetType: _tier == 'all' ? 'all' : 'tier',
            targetId: _tier == 'all' ? null : _tier,
          );
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(
        content: Text(
            'Sent! Success: ${result['success_count']}, Failed: ${result['failure_count']}'),
        backgroundColor: Colors.green,
      ));
      _titleCtrl.clear();
      _bodyCtrl.clear();
    } catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Error: $e'), backgroundColor: Colors.red));
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }
}

class _TierCountTable extends ConsumerWidget {
  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final userStats = ref.watch(userStatsProvider);
    return userStats.when(
      loading: () => const Center(child: CircularProgressIndicator()),
      error: (e, _) => Text('$e', style: const TextStyle(color: Colors.red)),
      data: (stats) {
        final byTier = stats['by_tier'] as Map? ?? {};
        final total = stats['total'] as int? ?? 0;
        return Table(
          columnWidths: const {
            0: FlexColumnWidth(2),
            1: FlexColumnWidth(1),
            2: FlexColumnWidth(1),
          },
          children: [
            _tableRow('Tier', 'Users', '% of total', header: true),
            ...['free', 'basic', 'premium', 'vip'].map((t) {
              final count = byTier[t] as int? ?? 0;
              final pct = total > 0 ? (count / total * 100) : 0.0;
              return _tableRow(
                t.toUpperCase(), '$count', '${pct.toStringAsFixed(1)}%');
            }),
            _tableRow('TOTAL', '$total', '100%'),
          ],
        );
      },
    );
  }

  TableRow _tableRow(String a, String b, String c, {bool header = false}) {
    final style = header
        ? const TextStyle(fontWeight: FontWeight.w700, fontSize: 12)
        : const TextStyle(fontSize: 13);
    return TableRow(children: [a, b, c].map((t) => Padding(
          padding: const EdgeInsets.symmetric(vertical: 6, horizontal: 4),
          child: Text(t, style: style),
        )).toList());
  }
}

// ─── Helper widgets ───────────────────────────────────────────────────────

class _TierDropdown extends StatelessWidget {
  final String label;
  final String value;
  final ValueChanged<String?> onChanged;
  const _TierDropdown({required this.label, required this.value, required this.onChanged});

  @override
  Widget build(BuildContext context) {
    return DropdownButtonFormField<String>(
      value: value,
      decoration: InputDecoration(
          labelText: label, border: const OutlineInputBorder()),
      items: ['free', 'basic', 'premium', 'vip']
          .map((t) => DropdownMenuItem(value: t, child: Text(t.toUpperCase())))
          .toList(),
      onChanged: onChanged,
    );
  }
}

class _SectionCard extends StatelessWidget {
  final String title;
  final String subtitle;
  final Widget child;
  const _SectionCard(
      {required this.title, required this.subtitle, required this.child});

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Text(title,
              style: Theme.of(context).textTheme.titleMedium
                  ?.copyWith(fontWeight: FontWeight.w700)),
          const SizedBox(height: 2),
          Text(subtitle,
              style: const TextStyle(fontSize: 12, color: Colors.grey)),
          const SizedBox(height: 14),
          child,
        ]),
      ),
    );
  }
}

class _TierBadge extends StatelessWidget {
  final String tier;
  const _TierBadge(this.tier);

  @override
  Widget build(BuildContext context) {
    final color = _tierColor(tier);
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 7, vertical: 2),
      decoration: BoxDecoration(
          color: color.withOpacity(0.12),
          borderRadius: BorderRadius.circular(6)),
      child: Text(tier.toUpperCase(),
          style: TextStyle(
              fontSize: 10, fontWeight: FontWeight.w700, color: color)),
    );
  }
}

class _Badge extends StatelessWidget {
  final String label;
  final Color color;
  const _Badge(this.label, this.color);

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
      decoration: BoxDecoration(
          color: color.withOpacity(0.12),
          borderRadius: BorderRadius.circular(6)),
      child: Text(label,
          style: TextStyle(
              fontSize: 10, fontWeight: FontWeight.w600, color: color)),
    );
  }
}

Color _tierColor(String tier) => {
      'free': Colors.grey,
      'basic': Colors.teal,
      'premium': Colors.blue,
      'vip': Colors.purple,
    }[tier] ??
    Colors.grey;
