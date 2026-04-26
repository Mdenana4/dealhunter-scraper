import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:intl/intl.dart';
import '../../providers/admin_providers.dart';
import '../../services/admin_firestore_service.dart';

class NotificationsScreen extends ConsumerStatefulWidget {
  const NotificationsScreen({super.key});

  @override
  ConsumerState<NotificationsScreen> createState() =>
      _NotificationsScreenState();
}

class _NotificationsScreenState extends ConsumerState<NotificationsScreen>
    with SingleTickerProviderStateMixin {
  late TabController _tabController;

  @override
  void initState() {
    super.initState();
    _tabController = TabController(length: 2, vsync: this);
  }

  @override
  void dispose() {
    _tabController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Notifications'),
        bottom: TabBar(
          controller: _tabController,
          tabs: const [
            Tab(icon: Icon(Icons.campaign), text: 'Broadcast'),
            Tab(icon: Icon(Icons.history), text: 'History'),
          ],
        ),
      ),
      body: TabBarView(
        controller: _tabController,
        children: [
          _BroadcastTab(onSent: () => _tabController.animateTo(1)),
          const _HistoryTab(),
        ],
      ),
    );
  }
}

// ─── Broadcast Tab ────────────────────────────────────────────────────────

class _BroadcastTab extends ConsumerStatefulWidget {
  final VoidCallback onSent;
  const _BroadcastTab({required this.onSent});

  @override
  ConsumerState<_BroadcastTab> createState() => _BroadcastTabState();
}

class _BroadcastTabState extends ConsumerState<_BroadcastTab> {
  final _formKey = GlobalKey<FormState>();
  final _titleCtrl = TextEditingController();
  final _bodyCtrl = TextEditingController();
  final _imageCtrl = TextEditingController();

  String _targetType = 'all';
  String? _targetTier;
  String? _targetGroupId;
  String? _targetUid;
  bool _sending = false;
  Map<String, dynamic>? _lastResult;

  @override
  void dispose() {
    _titleCtrl.dispose();
    _bodyCtrl.dispose();
    _imageCtrl.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final groupsAsync = ref.watch(groupsStreamProvider);
    final usersAsync = ref.watch(usersStreamProvider);

    return SingleChildScrollView(
      padding: const EdgeInsets.all(20),
      child: Form(
        key: _formKey,
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // ── Target Section ──
            Text('Send To',
                style: Theme.of(context).textTheme.titleMedium?.copyWith(
                    fontWeight: FontWeight.bold)),
            const SizedBox(height: 12),
            _TargetTypeSelector(
              value: _targetType,
              onChanged: (v) => setState(() {
                _targetType = v;
                _targetTier = null;
                _targetGroupId = null;
                _targetUid = null;
              }),
            ),
            const SizedBox(height: 12),

            // Target ID picker
            if (_targetType == 'tier')
              DropdownButtonFormField<String>(
                value: _targetTier,
                decoration: const InputDecoration(labelText: 'Select Tier *'),
                validator: (v) => v == null ? 'Required' : null,
                items: const [
                  DropdownMenuItem(value: 'free', child: Text('Free')),
                  DropdownMenuItem(value: 'basic', child: Text('Basic')),
                  DropdownMenuItem(value: 'premium', child: Text('Premium')),
                  DropdownMenuItem(value: 'vip', child: Text('VIP')),
                ],
                onChanged: (v) => setState(() => _targetTier = v),
              )
            else if (_targetType == 'group')
              groupsAsync.when(
                data: (groups) => DropdownButtonFormField<String>(
                  value: _targetGroupId,
                  decoration:
                      const InputDecoration(labelText: 'Select Group *'),
                  validator: (v) => v == null ? 'Required' : null,
                  items: groups
                      .map((g) => DropdownMenuItem(
                            value: g['id'] as String,
                            child: Text(g['name'] as String? ?? g['id'] as String),
                          ))
                      .toList(),
                  onChanged: (v) => setState(() => _targetGroupId = v),
                ),
                loading: () => const LinearProgressIndicator(),
                error: (e, _) => Text('Error loading groups: $e'),
              )
            else if (_targetType == 'user')
              usersAsync.when(
                data: (users) => DropdownButtonFormField<String>(
                  value: _targetUid,
                  decoration: const InputDecoration(labelText: 'Select User *'),
                  validator: (v) => v == null ? 'Required' : null,
                  items: users
                      .map((u) => DropdownMenuItem(
                            value: u['id'] as String,
                            child: Text(
                              '${u['display_name'] ?? u['email'] ?? u['id']}',
                              overflow: TextOverflow.ellipsis,
                            ),
                          ))
                      .toList(),
                  onChanged: (v) => setState(() => _targetUid = v),
                ),
                loading: () => const LinearProgressIndicator(),
                error: (e, _) => Text('Error loading users: $e'),
              ),

            const SizedBox(height: 24),

            // ── Content Section ──
            Text('Message',
                style: Theme.of(context).textTheme.titleMedium?.copyWith(
                    fontWeight: FontWeight.bold)),
            const SizedBox(height: 12),
            TextFormField(
              controller: _titleCtrl,
              maxLength: 60,
              decoration: const InputDecoration(
                labelText: 'Title *',
                hintText: 'e.g., Flash Sale — 70% off today!',
                prefixIcon: Icon(Icons.title),
              ),
              validator: (v) =>
                  v == null || v.trim().isEmpty ? 'Required' : null,
            ),
            const SizedBox(height: 12),
            TextFormField(
              controller: _bodyCtrl,
              maxLength: 240,
              maxLines: 4,
              decoration: const InputDecoration(
                labelText: 'Body *',
                hintText: 'Notification body text...',
                alignLabelWithHint: true,
              ),
              validator: (v) =>
                  v == null || v.trim().isEmpty ? 'Required' : null,
            ),
            const SizedBox(height: 12),
            TextFormField(
              controller: _imageCtrl,
              decoration: const InputDecoration(
                labelText: 'Image URL (optional)',
                hintText: 'https://...',
                prefixIcon: Icon(Icons.image_outlined),
              ),
            ),

            const SizedBox(height: 24),

            // ── Preview ──
            _NotificationPreview(
              title: _titleCtrl.text,
              body: _bodyCtrl.text,
              targetType: _targetType,
              targetLabel: _targetTier ?? _targetGroupId ?? _targetUid ?? 'All Users',
            ),

            const SizedBox(height: 24),

            // ── Result Banner ──
            if (_lastResult != null) _ResultBanner(result: _lastResult!),

            const SizedBox(height: 12),

            // ── Send Button ──
            SizedBox(
              width: double.infinity,
              height: 52,
              child: ElevatedButton.icon(
                onPressed: _sending ? null : _send,
                icon: _sending
                    ? const SizedBox(
                        width: 18,
                        height: 18,
                        child:
                            CircularProgressIndicator(strokeWidth: 2, color: Colors.white))
                    : const Icon(Icons.send),
                label: Text(_sending ? 'Sending...' : 'Send Notification'),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Future<void> _send() async {
    if (!_formKey.currentState!.validate()) return;

    final targetId = _targetType == 'tier'
        ? _targetTier
        : _targetType == 'group'
            ? _targetGroupId
            : _targetType == 'user'
                ? _targetUid
                : null;

    setState(() {
      _sending = true;
      _lastResult = null;
    });

    try {
      final result = await ref.read(adminServiceProvider).sendNotification(
            title: _titleCtrl.text.trim(),
            body: _bodyCtrl.text.trim(),
            imageUrl: _imageCtrl.text.trim().isEmpty
                ? null
                : _imageCtrl.text.trim(),
            targetType: _targetType,
            targetId: targetId,
          );
      if (mounted) {
        setState(() => _lastResult = result);
        _titleCtrl.clear();
        _bodyCtrl.clear();
        _imageCtrl.clear();
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text(
                'Sent! ${result['success_count'] ?? 0} delivered, '
                '${result['failure_count'] ?? 0} failed'),
            backgroundColor: Colors.green,
          ),
        );
        widget.onSent();
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Error: $e'), backgroundColor: Colors.red),
        );
      }
    } finally {
      if (mounted) setState(() => _sending = false);
    }
  }
}

// ─── Target Type Selector ─────────────────────────────────────────────────

class _TargetTypeSelector extends StatelessWidget {
  final String value;
  final ValueChanged<String> onChanged;
  const _TargetTypeSelector({required this.value, required this.onChanged});

  @override
  Widget build(BuildContext context) {
    return Wrap(
      spacing: 8,
      children: [
        _option('all', Icons.public, 'All Users'),
        _option('tier', Icons.star_outline, 'By Tier'),
        _option('group', Icons.group_outlined, 'By Group'),
        _option('user', Icons.person_outline, 'Single User'),
      ],
    );
  }

  Widget _option(String v, IconData icon, String label) {
    final selected = value == v;
    return FilterChip(
      avatar: Icon(icon, size: 16),
      label: Text(label),
      selected: selected,
      onSelected: (_) => onChanged(v),
      showCheckmark: false,
    );
  }
}

// ─── Notification Preview ─────────────────────────────────────────────────

class _NotificationPreview extends StatelessWidget {
  final String title;
  final String body;
  final String targetType;
  final String targetLabel;

  const _NotificationPreview({
    required this.title,
    required this.body,
    required this.targetType,
    required this.targetLabel,
  });

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text('Preview',
            style: Theme.of(context)
                .textTheme
                .titleSmall
                ?.copyWith(color: Colors.grey.shade600)),
        const SizedBox(height: 8),
        Container(
          decoration: BoxDecoration(
            color: Colors.blueGrey.shade50,
            borderRadius: BorderRadius.circular(12),
            border: Border.all(color: Colors.blueGrey.shade200),
          ),
          padding: const EdgeInsets.all(14),
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Container(
                width: 40,
                height: 40,
                decoration: BoxDecoration(
                    color: Colors.blue.shade600,
                    borderRadius: BorderRadius.circular(8)),
                child: const Icon(Icons.local_offer,
                    color: Colors.white, size: 20),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      title.isEmpty ? 'Notification title' : title,
                      style: const TextStyle(
                          fontWeight: FontWeight.bold, fontSize: 14),
                    ),
                    const SizedBox(height: 3),
                    Text(
                      body.isEmpty ? 'Notification body will appear here.' : body,
                      style: TextStyle(
                          fontSize: 12, color: Colors.grey.shade700),
                      maxLines: 3,
                      overflow: TextOverflow.ellipsis,
                    ),
                    const SizedBox(height: 6),
                    Text(
                      'To: $targetLabel',
                      style: TextStyle(
                          fontSize: 10,
                          color: Colors.blue.shade600,
                          fontWeight: FontWeight.w500),
                    ),
                  ],
                ),
              ),
            ],
          ),
        ),
      ],
    );
  }
}

// ─── Result Banner ────────────────────────────────────────────────────────

class _ResultBanner extends StatelessWidget {
  final Map<String, dynamic> result;
  const _ResultBanner({required this.result});

  @override
  Widget build(BuildContext context) {
    final success = result['success_count'] as int? ?? 0;
    final failure = result['failure_count'] as int? ?? 0;
    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: Colors.green.shade50,
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: Colors.green.shade300),
      ),
      child: Row(
        children: [
          Icon(Icons.check_circle, color: Colors.green.shade600),
          const SizedBox(width: 12),
          Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Text('Notification Sent',
                  style: TextStyle(fontWeight: FontWeight.bold)),
              Text('$success delivered · $failure failed',
                  style: TextStyle(
                      fontSize: 12, color: Colors.grey.shade700)),
            ],
          ),
        ],
      ),
    );
  }
}

// ─── History Tab ──────────────────────────────────────────────────────────

class _HistoryTab extends ConsumerWidget {
  const _HistoryTab();

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final logAsync = ref.watch(notificationLogProvider);

    return logAsync.when(
      data: (log) {
        if (log.isEmpty) {
          return Center(
            child: Column(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                Icon(Icons.mail_outline, size: 64, color: Colors.grey.shade300),
                const SizedBox(height: 16),
                Text('No notifications sent yet',
                    style: Theme.of(context).textTheme.titleMedium),
              ],
            ),
          );
        }
        return ListView.builder(
          padding: const EdgeInsets.all(16),
          itemCount: log.length,
          itemBuilder: (context, i) => _LogTile(entry: log[i]),
        );
      },
      loading: () => const Center(child: CircularProgressIndicator()),
      error: (e, _) => Center(child: Text('Error: $e')),
    );
  }
}

class _LogTile extends StatelessWidget {
  final Map<String, dynamic> entry;
  const _LogTile({required this.entry});

  @override
  Widget build(BuildContext context) {
    final sentAt = entry['sent_at'] as String?;
    final successCount = entry['success_count'] as int? ?? 0;
    final failureCount = entry['failure_count'] as int? ?? 0;
    final targetType = entry['target_type'] as String? ?? 'all';
    final targetId = entry['target_id'] as String?;

    String targetLabel;
    switch (targetType) {
      case 'all':
        targetLabel = 'All Users';
      case 'tier':
        targetLabel = 'Tier: ${targetId ?? '?'}';
      case 'group':
        targetLabel = 'Group: ${targetId ?? '?'}';
      case 'user':
        targetLabel = 'User: ${targetId ?? '?'}';
      default:
        targetLabel = targetType;
    }

    return Card(
      margin: const EdgeInsets.only(bottom: 10),
      child: Padding(
        padding: const EdgeInsets.all(14),
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Container(
              padding: const EdgeInsets.all(8),
              decoration: BoxDecoration(
                color: Colors.blue.shade50,
                shape: BoxShape.circle,
              ),
              child: Icon(Icons.notifications_outlined,
                  size: 18, color: Colors.blue.shade600),
            ),
            const SizedBox(width: 12),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(entry['title'] as String? ?? '(no title)',
                      style: const TextStyle(fontWeight: FontWeight.bold)),
                  const SizedBox(height: 4),
                  Text(entry['body'] as String? ?? '',
                      style: TextStyle(
                          fontSize: 13, color: Colors.grey.shade700),
                      maxLines: 2,
                      overflow: TextOverflow.ellipsis),
                  const SizedBox(height: 6),
                  Wrap(
                    spacing: 12,
                    children: [
                      _meta(Icons.send, targetLabel),
                      _meta(Icons.check, '$successCount sent',
                          color: Colors.green),
                      if (failureCount > 0)
                        _meta(Icons.error_outline, '$failureCount failed',
                            color: Colors.red),
                      if (sentAt != null)
                        _meta(Icons.schedule, _fmt(sentAt)),
                    ],
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _meta(IconData icon, String label, {Color? color}) {
    final c = color ?? Colors.grey.shade600;
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        Icon(icon, size: 12, color: c),
        const SizedBox(width: 3),
        Text(label, style: TextStyle(fontSize: 11, color: c)),
      ],
    );
  }

  String _fmt(String iso) {
    try {
      return DateFormat('MMM d, HH:mm').format(DateTime.parse(iso).toLocal());
    } catch (_) {
      return iso;
    }
  }
}
