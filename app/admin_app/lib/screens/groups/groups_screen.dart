import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../providers/admin_providers.dart';
import '../../services/admin_firestore_service.dart';

class GroupsScreen extends ConsumerWidget {
  const GroupsScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final groupsAsync = ref.watch(groupsStreamProvider);
    final usersAsync = ref.watch(usersStreamProvider);

    return Scaffold(
      appBar: AppBar(
        title: const Text('User Groups'),
        actions: [
          IconButton(
            icon: const Icon(Icons.add),
            tooltip: 'Create Group',
            onPressed: () => _showCreateGroupDialog(context, ref),
          ),
        ],
      ),
      body: groupsAsync.when(
        data: (groups) {
          if (groups.isEmpty) {
            return Center(
              child: Column(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  Icon(Icons.group_off, size: 64, color: Colors.grey.shade300),
                  const SizedBox(height: 16),
                  Text('No groups yet',
                      style: Theme.of(context).textTheme.titleMedium),
                  const SizedBox(height: 8),
                  ElevatedButton.icon(
                    icon: const Icon(Icons.add),
                    label: const Text('Create First Group'),
                    onPressed: () => _showCreateGroupDialog(context, ref),
                  ),
                ],
              ),
            );
          }
          return ListView.builder(
            padding: const EdgeInsets.all(16),
            itemCount: groups.length,
            itemBuilder: (context, i) {
              final g = groups[i];
              final members =
                  (g['member_uids'] as List?)?.cast<String>() ?? [];
              return _GroupCard(
                group: g,
                memberCount: members.length,
                allUsers: usersAsync.valueOrNull ?? [],
                ref: ref,
              );
            },
          );
        },
        loading: () => const Center(child: CircularProgressIndicator()),
        error: (e, _) => Center(child: Text('Error: $e')),
      ),
    );
  }

  void _showCreateGroupDialog(BuildContext context, WidgetRef ref) {
    showDialog(
      context: context,
      builder: (_) => _CreateGroupDialog(ref: ref),
    );
  }
}

// ─── Group Card ────────────────────────────────────────────────────────────

class _GroupCard extends StatelessWidget {
  final Map<String, dynamic> group;
  final int memberCount;
  final List<Map<String, dynamic>> allUsers;
  final WidgetRef ref;

  const _GroupCard({
    required this.group,
    required this.memberCount,
    required this.allUsers,
    required this.ref,
  });

  @override
  Widget build(BuildContext context) {
    final tier = group['tier_override'] as String?;
    final price = group['custom_price'] as num?;
    final limit = group['custom_daily_limit'] as num?;

    return Card(
      margin: const EdgeInsets.only(bottom: 12),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          ListTile(
            leading: CircleAvatar(
              backgroundColor: Colors.indigo.shade100,
              child: const Icon(Icons.group, color: Colors.indigo),
            ),
            title: Text(group['name'] ?? 'Unnamed',
                style: const TextStyle(fontWeight: FontWeight.bold)),
            subtitle: Text(group['description'] ?? ''),
            trailing: PopupMenuButton<String>(
              onSelected: (action) =>
                  _handleAction(context, action),
              itemBuilder: (_) => [
                const PopupMenuItem(
                    value: 'members', child: Text('Manage Members')),
                const PopupMenuItem(
                    value: 'overrides', child: Text('Edit Overrides')),
                const PopupMenuItem(
                    value: 'apply', child: Text('Apply Overrides to Members')),
                const PopupMenuDivider(),
                const PopupMenuItem(
                    value: 'delete',
                    child: Text('Delete', style: TextStyle(color: Colors.red))),
              ],
            ),
          ),
          Padding(
            padding: const EdgeInsets.fromLTRB(16, 0, 16, 12),
            child: Wrap(
              spacing: 8,
              runSpacing: 4,
              children: [
                _chip(Icons.people, '$memberCount members', Colors.blue),
                if (tier != null)
                  _chip(Icons.star, tier.toUpperCase(), Colors.orange),
                if (price != null)
                  _chip(Icons.attach_money, 'EGP ${price.toStringAsFixed(0)}/mo',
                      Colors.green),
                if (limit != null)
                  _chip(Icons.notifications, '$limit/day', Colors.purple),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _chip(IconData icon, String label, Color color) => Chip(
        avatar: Icon(icon, size: 14, color: color),
        label: Text(label, style: TextStyle(fontSize: 12, color: color)),
        backgroundColor: color.withValues(alpha: 0.1),
        side: BorderSide(color: color.withValues(alpha: 0.3)),
        materialTapTargetSize: MaterialTapTargetSize.shrinkWrap,
        padding: const EdgeInsets.symmetric(horizontal: 4),
      );

  void _handleAction(BuildContext context, String action) {
    switch (action) {
      case 'members':
        showDialog(
          context: context,
          builder: (_) => _MembersDialog(
            group: group,
            allUsers: allUsers,
            ref: ref,
          ),
        );
      case 'overrides':
        showDialog(
          context: context,
          builder: (_) => _OverridesDialog(group: group, ref: ref),
        );
      case 'apply':
        _applyOverrides(context);
      case 'delete':
        _confirmDelete(context);
    }
  }

  Future<void> _applyOverrides(BuildContext context) async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (_) => AlertDialog(
        title: const Text('Apply Group Overrides'),
        content: Text(
            'Apply tier/price/limit overrides to all ${memberCount} members of "${group['name']}"?'),
        actions: [
          TextButton(
              onPressed: () => Navigator.pop(context, false),
              child: const Text('Cancel')),
          ElevatedButton(
              onPressed: () => Navigator.pop(context, true),
              child: const Text('Apply')),
        ],
      ),
    );
    if (confirmed != true) return;

    try {
      final count = await ref
          .read(adminServiceProvider)
          .applyGroupOverridesToMembers(group['id'] as String);
      if (context.mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Updated $count members'), backgroundColor: Colors.green),
        );
      }
    } catch (e) {
      if (context.mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Error: $e'), backgroundColor: Colors.red),
        );
      }
    }
  }

  Future<void> _confirmDelete(BuildContext context) async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (_) => AlertDialog(
        title: const Text('Delete Group'),
        content: Text('Delete group "${group['name']}"? Members are not deleted.'),
        actions: [
          TextButton(
              onPressed: () => Navigator.pop(context, false),
              child: const Text('Cancel')),
          ElevatedButton(
              style: ElevatedButton.styleFrom(backgroundColor: Colors.red),
              onPressed: () => Navigator.pop(context, true),
              child: const Text('Delete')),
        ],
      ),
    );
    if (confirmed != true) return;

    try {
      await ref
          .read(adminServiceProvider)
          .deleteGroup(group['id'] as String);
    } catch (e) {
      if (context.mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Error: $e'), backgroundColor: Colors.red),
        );
      }
    }
  }
}

// ─── Create Group Dialog ────────────────────────────────────────────────────

class _CreateGroupDialog extends ConsumerStatefulWidget {
  final WidgetRef ref;
  const _CreateGroupDialog({required this.ref});

  @override
  ConsumerState<_CreateGroupDialog> createState() => _CreateGroupDialogState();
}

class _CreateGroupDialogState extends ConsumerState<_CreateGroupDialog> {
  final _nameCtrl = TextEditingController();
  final _descCtrl = TextEditingController();
  String? _tier;
  final _priceCtrl = TextEditingController();
  final _limitCtrl = TextEditingController();
  bool _saving = false;

  @override
  void dispose() {
    _nameCtrl.dispose();
    _descCtrl.dispose();
    _priceCtrl.dispose();
    _limitCtrl.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return AlertDialog(
      title: const Text('Create Group'),
      content: SizedBox(
        width: 400,
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            TextField(
              controller: _nameCtrl,
              decoration: const InputDecoration(labelText: 'Group Name *'),
            ),
            const SizedBox(height: 12),
            TextField(
              controller: _descCtrl,
              decoration: const InputDecoration(labelText: 'Description'),
              maxLines: 2,
            ),
            const SizedBox(height: 12),
            DropdownButtonFormField<String>(
              value: _tier,
              decoration: const InputDecoration(labelText: 'Tier Override'),
              items: const [
                DropdownMenuItem(value: null, child: Text('— None —')),
                DropdownMenuItem(value: 'free', child: Text('Free')),
                DropdownMenuItem(value: 'basic', child: Text('Basic')),
                DropdownMenuItem(value: 'premium', child: Text('Premium')),
                DropdownMenuItem(value: 'vip', child: Text('VIP')),
              ],
              onChanged: (v) => setState(() => _tier = v),
            ),
            const SizedBox(height: 12),
            Row(
              children: [
                Expanded(
                  child: TextField(
                    controller: _priceCtrl,
                    decoration:
                        const InputDecoration(labelText: 'Price (EGP/mo)'),
                    keyboardType: TextInputType.number,
                  ),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: TextField(
                    controller: _limitCtrl,
                    decoration:
                        const InputDecoration(labelText: 'Daily Limit'),
                    keyboardType: TextInputType.number,
                  ),
                ),
              ],
            ),
          ],
        ),
      ),
      actions: [
        TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('Cancel')),
        ElevatedButton(
          onPressed: _saving ? null : _create,
          child: _saving
              ? const SizedBox(
                  width: 16,
                  height: 16,
                  child: CircularProgressIndicator(strokeWidth: 2))
              : const Text('Create'),
        ),
      ],
    );
  }

  Future<void> _create() async {
    if (_nameCtrl.text.trim().isEmpty) return;
    setState(() => _saving = true);
    try {
      await ref.read(adminServiceProvider).createGroup(
            name: _nameCtrl.text.trim(),
            description: _descCtrl.text.trim(),
            tier: _tier,
            customPrice: double.tryParse(_priceCtrl.text),
            customDailyLimit: int.tryParse(_limitCtrl.text),
          );
      if (mounted) Navigator.pop(context);
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Error: $e'), backgroundColor: Colors.red),
        );
      }
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }
}

// ─── Members Dialog ────────────────────────────────────────────────────────

class _MembersDialog extends ConsumerStatefulWidget {
  final Map<String, dynamic> group;
  final List<Map<String, dynamic>> allUsers;
  final WidgetRef ref;

  const _MembersDialog({
    required this.group,
    required this.allUsers,
    required this.ref,
  });

  @override
  ConsumerState<_MembersDialog> createState() => _MembersDialogState();
}

class _MembersDialogState extends ConsumerState<_MembersDialog> {
  String _search = '';

  List<String> get _memberIds =>
      (widget.group['member_uids'] as List?)?.cast<String>() ?? [];

  @override
  Widget build(BuildContext context) {
    final filtered = widget.allUsers
        .where((u) {
          final name = (u['display_name'] ?? '').toString().toLowerCase();
          final email = (u['email'] ?? '').toString().toLowerCase();
          return _search.isEmpty ||
              name.contains(_search) ||
              email.contains(_search);
        })
        .toList();

    return AlertDialog(
      title: Text('Members — ${widget.group['name']}'),
      content: SizedBox(
        width: 480,
        height: 480,
        child: Column(
          children: [
            TextField(
              decoration: const InputDecoration(
                hintText: 'Search users...',
                prefixIcon: Icon(Icons.search),
              ),
              onChanged: (v) => setState(() => _search = v.toLowerCase()),
            ),
            const SizedBox(height: 8),
            Expanded(
              child: ListView.builder(
                itemCount: filtered.length,
                itemBuilder: (context, i) {
                  final u = filtered[i];
                  final uid = u['id'] as String;
                  final isMember = _memberIds.contains(uid);
                  return ListTile(
                    dense: true,
                    leading: CircleAvatar(
                      radius: 16,
                      child: Text(
                        ((u['display_name'] ?? u['email'] ?? '?') as String)
                            .substring(0, 1)
                            .toUpperCase(),
                      ),
                    ),
                    title: Text(u['display_name'] ?? u['email'] ?? uid,
                        style: const TextStyle(fontSize: 13)),
                    subtitle: Text(u['email'] ?? '',
                        style: const TextStyle(fontSize: 11)),
                    trailing: isMember
                        ? TextButton(
                            onPressed: () => _remove(uid),
                            child: const Text('Remove',
                                style: TextStyle(color: Colors.red)),
                          )
                        : TextButton(
                            onPressed: () => _add(uid),
                            child: const Text('Add'),
                          ),
                  );
                },
              ),
            ),
          ],
        ),
      ),
      actions: [
        TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('Done')),
      ],
    );
  }

  Future<void> _add(String uid) async {
    try {
      await ref
          .read(adminServiceProvider)
          .addUserToGroup(widget.group['id'] as String, uid);
      setState(() {});
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Error: $e'), backgroundColor: Colors.red),
        );
      }
    }
  }

  Future<void> _remove(String uid) async {
    try {
      await ref
          .read(adminServiceProvider)
          .removeUserFromGroup(widget.group['id'] as String, uid);
      setState(() {});
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Error: $e'), backgroundColor: Colors.red),
        );
      }
    }
  }
}

// ─── Overrides Dialog ─────────────────────────────────────────────────────

class _OverridesDialog extends ConsumerStatefulWidget {
  final Map<String, dynamic> group;
  final WidgetRef ref;
  const _OverridesDialog({required this.group, required this.ref});

  @override
  ConsumerState<_OverridesDialog> createState() => _OverridesDialogState();
}

class _OverridesDialogState extends ConsumerState<_OverridesDialog> {
  late String? _tier;
  late TextEditingController _priceCtrl;
  late TextEditingController _limitCtrl;
  bool _saving = false;

  @override
  void initState() {
    super.initState();
    _tier = widget.group['tier_override'] as String?;
    _priceCtrl = TextEditingController(
        text: (widget.group['custom_price'] as num?)?.toString() ?? '');
    _limitCtrl = TextEditingController(
        text: (widget.group['custom_daily_limit'] as num?)?.toString() ?? '');
  }

  @override
  void dispose() {
    _priceCtrl.dispose();
    _limitCtrl.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return AlertDialog(
      title: Text('Edit Overrides — ${widget.group['name']}'),
      content: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          DropdownButtonFormField<String>(
            value: _tier,
            decoration: const InputDecoration(labelText: 'Tier Override'),
            items: const [
              DropdownMenuItem(value: null, child: Text('— None —')),
              DropdownMenuItem(value: 'free', child: Text('Free')),
              DropdownMenuItem(value: 'basic', child: Text('Basic')),
              DropdownMenuItem(value: 'premium', child: Text('Premium')),
              DropdownMenuItem(value: 'vip', child: Text('VIP')),
            ],
            onChanged: (v) => setState(() => _tier = v),
          ),
          const SizedBox(height: 12),
          TextField(
            controller: _priceCtrl,
            decoration: const InputDecoration(
                labelText: 'Custom Price (EGP/mo)', prefixText: 'EGP '),
            keyboardType: TextInputType.number,
          ),
          const SizedBox(height: 12),
          TextField(
            controller: _limitCtrl,
            decoration:
                const InputDecoration(labelText: 'Custom Daily Limit'),
            keyboardType: TextInputType.number,
          ),
        ],
      ),
      actions: [
        TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('Cancel')),
        ElevatedButton(
          onPressed: _saving ? null : _save,
          child: _saving
              ? const SizedBox(
                  width: 16,
                  height: 16,
                  child: CircularProgressIndicator(strokeWidth: 2))
              : const Text('Save'),
        ),
      ],
    );
  }

  Future<void> _save() async {
    setState(() => _saving = true);
    try {
      final updates = <String, dynamic>{
        'tier_override': _tier,
        'custom_price': double.tryParse(_priceCtrl.text),
        'custom_daily_limit': int.tryParse(_limitCtrl.text),
      };
      await ref
          .read(adminServiceProvider)
          .updateGroup(widget.group['id'] as String, updates);
      if (mounted) Navigator.pop(context);
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Error: $e'), backgroundColor: Colors.red),
        );
      }
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }
}
