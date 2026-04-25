import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:intl/intl.dart';
import '../../providers/admin_providers.dart';
import '../../services/admin_firestore_service.dart';

class SourcesScreen extends ConsumerWidget {
  const SourcesScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final sourcesAsync = ref.watch(sourcesStreamProvider);

    return Scaffold(
      appBar: AppBar(
        title: const Text('Scraper Sources'),
        actions: [
          IconButton(
            icon: const Icon(Icons.add),
            tooltip: 'Add Source',
            onPressed: () => _showAddDialog(context, ref),
          ),
        ],
      ),
      body: sourcesAsync.when(
        data: (sources) {
          if (sources.isEmpty) {
            return Center(
              child: Column(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  Icon(Icons.source_outlined,
                      size: 64, color: Colors.grey.shade300),
                  const SizedBox(height: 16),
                  Text('No sources configured',
                      style: Theme.of(context).textTheme.titleMedium),
                  const SizedBox(height: 8),
                  ElevatedButton.icon(
                    icon: const Icon(Icons.add),
                    label: const Text('Add First Source'),
                    onPressed: () => _showAddDialog(context, ref),
                  ),
                ],
              ),
            );
          }

          final enabled = sources.where((s) => s['enabled'] == true).length;
          return Column(
            children: [
              _SummaryBar(total: sources.length, enabled: enabled),
              Expanded(
                child: ListView.builder(
                  padding: const EdgeInsets.all(16),
                  itemCount: sources.length,
                  itemBuilder: (context, i) =>
                      _SourceCard(source: sources[i], ref: ref),
                ),
              ),
            ],
          );
        },
        loading: () => const Center(child: CircularProgressIndicator()),
        error: (e, _) => Center(child: Text('Error: $e')),
      ),
    );
  }

  void _showAddDialog(BuildContext context, WidgetRef ref) {
    showDialog(
      context: context,
      builder: (_) => _AddSourceDialog(ref: ref),
    );
  }
}

// ─── Summary Bar ──────────────────────────────────────────────────────────

class _SummaryBar extends StatelessWidget {
  final int total;
  final int enabled;
  const _SummaryBar({required this.total, required this.enabled});

  @override
  Widget build(BuildContext context) {
    return Container(
      color: Colors.grey.shade50,
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
      child: Row(
        children: [
          _stat('Total', total, Colors.blue),
          const SizedBox(width: 24),
          _stat('Active', enabled, Colors.green),
          const SizedBox(width: 24),
          _stat('Disabled', total - enabled, Colors.red),
        ],
      ),
    );
  }

  Widget _stat(String label, int value, Color color) => Row(
        children: [
          Container(
              width: 8,
              height: 8,
              decoration:
                  BoxDecoration(shape: BoxShape.circle, color: color)),
          const SizedBox(width: 6),
          Text('$label: ',
              style: TextStyle(fontSize: 12, color: Colors.grey.shade600)),
          Text('$value',
              style: TextStyle(
                  fontSize: 12,
                  fontWeight: FontWeight.bold,
                  color: color)),
        ],
      );
}

// ─── Source Card ──────────────────────────────────────────────────────────

class _SourceCard extends StatelessWidget {
  final Map<String, dynamic> source;
  final WidgetRef ref;

  const _SourceCard({required this.source, required this.ref});

  @override
  Widget build(BuildContext context) {
    final enabled = source['enabled'] == true;
    final lastScraped = source['last_scraped_at'] as String?;
    final productsCount = source['products_count'] as int? ?? 0;

    return Card(
      margin: const EdgeInsets.only(bottom: 10),
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // Status indicator
            Container(
              width: 10,
              height: 10,
              margin: const EdgeInsets.only(top: 4),
              decoration: BoxDecoration(
                shape: BoxShape.circle,
                color: enabled ? Colors.green : Colors.red,
              ),
            ),
            const SizedBox(width: 12),

            // Info
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      Text(source['name'] ?? '',
                          style: const TextStyle(
                              fontWeight: FontWeight.bold, fontSize: 15)),
                      const SizedBox(width: 8),
                      Container(
                        padding: const EdgeInsets.symmetric(
                            horizontal: 6, vertical: 2),
                        decoration: BoxDecoration(
                          color: Colors.blue.shade50,
                          borderRadius: BorderRadius.circular(4),
                          border: Border.all(color: Colors.blue.shade200),
                        ),
                        child: Text(
                          source['marketplace_country'] ?? '',
                          style: TextStyle(
                              fontSize: 10, color: Colors.blue.shade700),
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 2),
                  Text(source['base_url'] ?? '',
                      style: TextStyle(
                          fontSize: 12, color: Colors.grey.shade500)),
                  const SizedBox(height: 6),
                  Wrap(
                    spacing: 12,
                    children: [
                      _infoChip(Icons.inventory_2_outlined,
                          '$productsCount products'),
                      _infoChip(Icons.currency_exchange,
                          source['currency'] ?? '—'),
                      if (lastScraped != null)
                        _infoChip(
                          Icons.schedule,
                          _formatDate(lastScraped),
                        ),
                    ],
                  ),
                ],
              ),
            ),

            // Actions
            Column(
              children: [
                Switch(
                  value: enabled,
                  onChanged: (v) => _toggle(context, v),
                ),
                PopupMenuButton<String>(
                  iconSize: 18,
                  onSelected: (a) => _handleAction(context, a),
                  itemBuilder: (_) => [
                    const PopupMenuItem(value: 'edit', child: Text('Edit')),
                    const PopupMenuDivider(),
                    const PopupMenuItem(
                        value: 'delete',
                        child: Text('Delete',
                            style: TextStyle(color: Colors.red))),
                  ],
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }

  Widget _infoChip(IconData icon, String label) => Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon, size: 12, color: Colors.grey.shade500),
          const SizedBox(width: 3),
          Text(label,
              style:
                  TextStyle(fontSize: 11, color: Colors.grey.shade600)),
        ],
      );

  String _formatDate(String iso) {
    try {
      final dt = DateTime.parse(iso).toLocal();
      return DateFormat('MMM d, HH:mm').format(dt);
    } catch (_) {
      return iso;
    }
  }

  Future<void> _toggle(BuildContext context, bool value) async {
    try {
      await ref
          .read(adminServiceProvider)
          .toggleSource(source['id'] as String, value);
    } catch (e) {
      if (context.mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Error: $e'), backgroundColor: Colors.red),
        );
      }
    }
  }

  void _handleAction(BuildContext context, String action) {
    switch (action) {
      case 'edit':
        showDialog(
          context: context,
          builder: (_) => _EditSourceDialog(source: source, ref: ref),
        );
      case 'delete':
        _confirmDelete(context);
    }
  }

  Future<void> _confirmDelete(BuildContext context) async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (_) => AlertDialog(
        title: const Text('Delete Source'),
        content: Text(
            'Delete "${source['name']}"? This will not delete already-scraped products.'),
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
          .deleteSource(source['id'] as String);
    } catch (e) {
      if (context.mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Error: $e'), backgroundColor: Colors.red),
        );
      }
    }
  }
}

// ─── Add Source Dialog ────────────────────────────────────────────────────

class _AddSourceDialog extends ConsumerStatefulWidget {
  final WidgetRef ref;
  const _AddSourceDialog({required this.ref});

  @override
  ConsumerState<_AddSourceDialog> createState() => _AddSourceDialogState();
}

class _AddSourceDialogState extends ConsumerState<_AddSourceDialog> {
  final _nameCtrl = TextEditingController();
  final _urlCtrl = TextEditingController();
  final _logoCtrl = TextEditingController();
  String _country = 'EG';
  String _currency = 'EGP';
  bool _enabled = true;
  bool _saving = false;

  static const _countries = ['EG', 'SA', 'AE', 'US', 'UK'];
  static const _currencies = ['EGP', 'SAR', 'AED', 'USD', 'GBP'];

  @override
  void dispose() {
    _nameCtrl.dispose();
    _urlCtrl.dispose();
    _logoCtrl.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return AlertDialog(
      title: const Text('Add Source'),
      content: SizedBox(
        width: 420,
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            TextField(
              controller: _nameCtrl,
              decoration: const InputDecoration(
                  labelText: 'Source Name *',
                  hintText: 'e.g., Jumia Egypt'),
            ),
            const SizedBox(height: 12),
            TextField(
              controller: _urlCtrl,
              decoration: const InputDecoration(
                  labelText: 'Base URL *',
                  hintText: 'https://www.jumia.com.eg'),
            ),
            const SizedBox(height: 12),
            TextField(
              controller: _logoCtrl,
              decoration: const InputDecoration(
                  labelText: 'Logo URL',
                  hintText: 'https://...'),
            ),
            const SizedBox(height: 12),
            Row(
              children: [
                Expanded(
                  child: DropdownButtonFormField<String>(
                    value: _country,
                    decoration:
                        const InputDecoration(labelText: 'Country'),
                    items: _countries
                        .map((c) => DropdownMenuItem(value: c, child: Text(c)))
                        .toList(),
                    onChanged: (v) => setState(() => _country = v!),
                  ),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: DropdownButtonFormField<String>(
                    value: _currency,
                    decoration:
                        const InputDecoration(labelText: 'Currency'),
                    items: _currencies
                        .map((c) => DropdownMenuItem(value: c, child: Text(c)))
                        .toList(),
                    onChanged: (v) => setState(() => _currency = v!),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 8),
            SwitchListTile(
              title: const Text('Enabled'),
              value: _enabled,
              onChanged: (v) => setState(() => _enabled = v),
              contentPadding: EdgeInsets.zero,
            ),
          ],
        ),
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
              : const Text('Add'),
        ),
      ],
    );
  }

  Future<void> _save() async {
    if (_nameCtrl.text.trim().isEmpty || _urlCtrl.text.trim().isEmpty) return;
    setState(() => _saving = true);
    try {
      await ref.read(adminServiceProvider).addSource(
            name: _nameCtrl.text.trim(),
            marketplaceCountry: _country,
            baseUrl: _urlCtrl.text.trim(),
            currency: _currency,
            logoUrl: _logoCtrl.text.trim().isEmpty
                ? null
                : _logoCtrl.text.trim(),
            enabled: _enabled,
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

// ─── Edit Source Dialog ────────────────────────────────────────────────────

class _EditSourceDialog extends ConsumerStatefulWidget {
  final Map<String, dynamic> source;
  final WidgetRef ref;
  const _EditSourceDialog({required this.source, required this.ref});

  @override
  ConsumerState<_EditSourceDialog> createState() => _EditSourceDialogState();
}

class _EditSourceDialogState extends ConsumerState<_EditSourceDialog> {
  late TextEditingController _nameCtrl;
  late TextEditingController _urlCtrl;
  late TextEditingController _logoCtrl;
  bool _saving = false;

  @override
  void initState() {
    super.initState();
    _nameCtrl =
        TextEditingController(text: widget.source['name'] as String? ?? '');
    _urlCtrl =
        TextEditingController(text: widget.source['base_url'] as String? ?? '');
    _logoCtrl =
        TextEditingController(text: widget.source['logo_url'] as String? ?? '');
  }

  @override
  void dispose() {
    _nameCtrl.dispose();
    _urlCtrl.dispose();
    _logoCtrl.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return AlertDialog(
      title: Text('Edit — ${widget.source['name']}'),
      content: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          TextField(
            controller: _nameCtrl,
            decoration: const InputDecoration(labelText: 'Source Name'),
          ),
          const SizedBox(height: 12),
          TextField(
            controller: _urlCtrl,
            decoration: const InputDecoration(labelText: 'Base URL'),
          ),
          const SizedBox(height: 12),
          TextField(
            controller: _logoCtrl,
            decoration: const InputDecoration(labelText: 'Logo URL'),
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
      await ref.read(adminServiceProvider).updateSource(
        widget.source['id'] as String,
        {
          'name': _nameCtrl.text.trim(),
          'base_url': _urlCtrl.text.trim(),
          'logo_url': _logoCtrl.text.trim().isEmpty
              ? null
              : _logoCtrl.text.trim(),
        },
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
