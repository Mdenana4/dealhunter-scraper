import 'package:cloud_firestore/cloud_firestore.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:intl/intl.dart';
import '../../providers/admin_providers.dart';

// ─── Source display helpers ───────────────────────────────────────────────────

const _sources = [
  ('all',       'All Sources'),
  ('amazon_eg', 'Amazon EG'),
  ('amazon_ae', 'Amazon AE'),
  ('amazon_sa', 'Amazon SA'),
  ('noon_eg',   'Noon EG'),
  ('noon_ae',   'Noon AE'),
  ('noon_sa',   'Noon SA'),
  ('jumia_eg',  'Jumia EG'),
  ('hyperone',  'HyperOne'),
  ('btech',     'B.Tech'),
  ('carrefour', 'Carrefour'),
  ('sharafdg',  'Sharaf DG'),
  ('sahla',     'Sahla'),
];

const _categories = [
  ('all',         'All'),
  ('electronics', 'Electronics'),
  ('fashion',     'Fashion'),
  ('home',        'Home'),
  ('beauty',      'Beauty'),
  ('sports',      'Sports'),
  ('general',     'General'),
];

const _sourceColors = {
  'amazon_eg': Color(0xFFFF9900),
  'amazon_ae': Color(0xFFFF9900),
  'amazon_sa': Color(0xFFFF9900),
  'noon_eg':   Color(0xFFFFEB00),
  'noon_ae':   Color(0xFFFFEB00),
  'noon_sa':   Color(0xFFFFEB00),
  'jumia_eg':  Color(0xFFEF6C00),
  'hyperone':  Color(0xFF1565C0),
  'btech':     Color(0xFF2E7D32),
  'carrefour': Color(0xFF1565C0),
  'sharafdg':  Color(0xFF6A1B9A),
  'sahla':     Color(0xFFAD1457),
};

// ─── Screen ───────────────────────────────────────────────────────────────────

class DealsScreen extends ConsumerStatefulWidget {
  const DealsScreen({super.key});

  @override
  ConsumerState<DealsScreen> createState() => _DealsScreenState();
}

class _DealsScreenState extends ConsumerState<DealsScreen> {
  String _source   = 'all';
  String _category = 'all';
  String _search   = '';
  bool   _loading  = false;
  bool   _hasMore  = true;

  final List<Map<String, dynamic>> _deals = [];
  DocumentSnapshot? _lastDoc;
  final _searchCtrl = TextEditingController();
  final _scrollCtrl = ScrollController();

  static const _pageSize = 30;

  @override
  void initState() {
    super.initState();
    _load(reset: true);
    _scrollCtrl.addListener(() {
      if (_scrollCtrl.position.pixels >= _scrollCtrl.position.maxScrollExtent - 200) {
        _load();
      }
    });
  }

  @override
  void dispose() {
    _searchCtrl.dispose();
    _scrollCtrl.dispose();
    super.dispose();
  }

  Future<void> _load({bool reset = false}) async {
    if (_loading || (!reset && !_hasMore)) return;
    setState(() => _loading = true);

    if (reset) {
      _deals.clear();
      _lastDoc = null;
      _hasMore = true;
    }

    try {
      final svc = ref.read(adminServiceProvider);
      final (docs, last) = await svc.getDeals(
        source:     _source   == 'all' ? null : _source,
        category:   _category == 'all' ? null : _category,
        startAfter: _lastDoc,
        limit:      _pageSize,
      );
      setState(() {
        _deals.addAll(docs);
        _lastDoc  = last;
        _hasMore  = docs.length == _pageSize;
        _loading  = false;
      });
    } catch (e) {
      setState(() => _loading = false);
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Error: $e'), backgroundColor: Colors.red),
        );
      }
    }
  }

  List<Map<String, dynamic>> get _filtered {
    if (_search.isEmpty) return _deals;
    final q = _search.toLowerCase();
    return _deals.where((d) =>
      (d['title'] as String? ?? '').toLowerCase().contains(q)).toList();
  }

  Future<void> _delete(String dealId) async {
    final ok = await showDialog<bool>(
      context: context,
      builder: (_) => AlertDialog(
        title: const Text('Delete deal?'),
        content: const Text('This removes it from the app permanently.'),
        actions: [
          TextButton(onPressed: () => Navigator.pop(context, false), child: const Text('Cancel')),
          FilledButton(
            style: FilledButton.styleFrom(backgroundColor: Colors.red),
            onPressed: () => Navigator.pop(context, true),
            child: const Text('Delete'),
          ),
        ],
      ),
    );
    if (ok != true) return;
    await ref.read(adminServiceProvider).deleteDeal(dealId);
    setState(() => _deals.removeWhere((d) => d['id'] == dealId));
    if (mounted) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Deal deleted')),
      );
    }
  }

  Future<void> _flagFake(String dealId) async {
    await ref.read(adminServiceProvider).flagDealAsFake(dealId);
    setState(() {
      final idx = _deals.indexWhere((d) => d['id'] == dealId);
      if (idx != -1) _deals[idx] = {..._deals[idx], 'fake_verdict': 'FAKE', 'manually_flagged': true};
    });
    if (mounted) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Flagged as fake')),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    final filtered = _filtered;

    return Scaffold(
      appBar: AppBar(
        title: Text('Deals  (${_deals.length}${_hasMore ? '+' : ''})'),
        actions: [
          IconButton(
            icon: const Icon(Icons.refresh),
            tooltip: 'Reload',
            onPressed: () => _load(reset: true),
          ),
        ],
      ),
      body: Column(
        children: [
          // ── Search bar ─────────────────────────────────────────────────
          Padding(
            padding: const EdgeInsets.fromLTRB(12, 10, 12, 4),
            child: TextField(
              controller: _searchCtrl,
              decoration: InputDecoration(
                hintText: 'Search title…',
                prefixIcon: const Icon(Icons.search, size: 20),
                suffixIcon: _search.isNotEmpty
                    ? IconButton(
                        icon: const Icon(Icons.clear, size: 18),
                        onPressed: () {
                          _searchCtrl.clear();
                          setState(() => _search = '');
                        })
                    : null,
                isDense: true,
                contentPadding: const EdgeInsets.symmetric(vertical: 10),
              ),
              onChanged: (v) => setState(() => _search = v),
            ),
          ),

          // ── Source filter ──────────────────────────────────────────────
          SizedBox(
            height: 36,
            child: ListView.separated(
              scrollDirection: Axis.horizontal,
              padding: const EdgeInsets.symmetric(horizontal: 12),
              itemCount: _sources.length,
              separatorBuilder: (_, __) => const SizedBox(width: 6),
              itemBuilder: (_, i) {
                final (val, label) = _sources[i];
                final selected = _source == val;
                return FilterChip(
                  label: Text(label, style: const TextStyle(fontSize: 12)),
                  selected: selected,
                  onSelected: (_) {
                    setState(() => _source = val);
                    _load(reset: true);
                  },
                  visualDensity: VisualDensity.compact,
                );
              },
            ),
          ),

          const SizedBox(height: 4),

          // ── Category filter ────────────────────────────────────────────
          SizedBox(
            height: 34,
            child: ListView.separated(
              scrollDirection: Axis.horizontal,
              padding: const EdgeInsets.symmetric(horizontal: 12),
              itemCount: _categories.length,
              separatorBuilder: (_, __) => const SizedBox(width: 6),
              itemBuilder: (_, i) {
                final (val, label) = _categories[i];
                final selected = _category == val;
                return FilterChip(
                  label: Text(label, style: const TextStyle(fontSize: 11)),
                  selected: selected,
                  onSelected: (_) {
                    setState(() => _category = val);
                    _load(reset: true);
                  },
                  visualDensity: VisualDensity.compact,
                );
              },
            ),
          ),

          const Divider(height: 8),

          // ── Deal list ──────────────────────────────────────────────────
          Expanded(
            child: filtered.isEmpty && !_loading
                ? const Center(child: Text('No deals found', style: TextStyle(color: Colors.grey)))
                : ListView.builder(
                    controller: _scrollCtrl,
                    padding: const EdgeInsets.only(bottom: 16),
                    itemCount: filtered.length + (_loading ? 1 : 0),
                    itemBuilder: (_, i) {
                      if (i == filtered.length) {
                        return const Padding(
                          padding: EdgeInsets.all(24),
                          child: Center(child: CircularProgressIndicator()),
                        );
                      }
                      return _DealTile(
                        deal: filtered[i],
                        onDelete: () => _delete(filtered[i]['id'] as String),
                        onFlagFake: () => _flagFake(filtered[i]['id'] as String),
                      );
                    },
                  ),
          ),
        ],
      ),
    );
  }
}

// ─── Deal tile ────────────────────────────────────────────────────────────────

class _DealTile extends StatelessWidget {
  final Map<String, dynamic> deal;
  final VoidCallback onDelete;
  final VoidCallback onFlagFake;

  const _DealTile({
    required this.deal,
    required this.onDelete,
    required this.onFlagFake,
  });

  @override
  Widget build(BuildContext context) {
    final title      = deal['title']         as String? ?? '—';
    final site       = deal['site']          as String? ?? '';
    final siteDisplay = deal['site_display'] as String? ?? site;
    final currency   = deal['currency']      as String? ?? '';
    final current    = (deal['current_price']  as num?)?.toDouble() ?? 0;
    final original   = (deal['original_price'] as num?)?.toDouble() ?? 0;
    final discount   = (deal['discount_percent'] as num?)?.toInt() ?? (deal['discount'] as num?)?.toInt() ?? 0;
    final imageUrl   = deal['image_url']     as String? ?? '';
    final isFake     = deal['fake_verdict']  == 'FAKE';
    final isManualFake = deal['manually_flagged'] == true;
    final ts         = deal['timestamp'];

    final fmt = NumberFormat('#,##0.##');
    final color = _sourceColors[site] ?? Colors.grey;

    return Card(
      margin: const EdgeInsets.symmetric(horizontal: 12, vertical: 4),
      child: Padding(
        padding: const EdgeInsets.all(10),
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // Image
            ClipRRect(
              borderRadius: BorderRadius.circular(8),
              child: imageUrl.isNotEmpty
                  ? Image.network(imageUrl, width: 72, height: 72, fit: BoxFit.cover,
                      errorBuilder: (_, __, ___) => _imagePlaceholder())
                  : _imagePlaceholder(),
            ),

            const SizedBox(width: 10),

            // Content
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  // Source badge + fake badge + time
                  Row(children: [
                    Container(
                      padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                      decoration: BoxDecoration(
                        color: color.withOpacity(0.15),
                        borderRadius: BorderRadius.circular(4),
                        border: Border.all(color: color.withOpacity(0.5)),
                      ),
                      child: Text(siteDisplay,
                          style: TextStyle(fontSize: 10, color: color, fontWeight: FontWeight.w600)),
                    ),
                    if (isFake) ...[
                      const SizedBox(width: 4),
                      Container(
                        padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                        decoration: BoxDecoration(
                          color: Colors.red.shade50,
                          borderRadius: BorderRadius.circular(4),
                        ),
                        child: Text(
                          isManualFake ? 'FAKE (manual)' : 'FAKE',
                          style: const TextStyle(fontSize: 10, color: Colors.red, fontWeight: FontWeight.w600),
                        ),
                      ),
                    ],
                    const Spacer(),
                    Text(_formatAge(ts),
                        style: const TextStyle(fontSize: 10, color: Colors.grey)),
                  ]),

                  const SizedBox(height: 4),

                  // Title
                  Text(title,
                    style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w500),
                    maxLines: 2,
                    overflow: TextOverflow.ellipsis,
                  ),

                  const SizedBox(height: 4),

                  // Prices
                  Row(children: [
                    Text('$currency ${fmt.format(current)}',
                        style: const TextStyle(fontSize: 14, fontWeight: FontWeight.bold)),
                    const SizedBox(width: 6),
                    if (original > current)
                      Text('$currency ${fmt.format(original)}',
                          style: const TextStyle(
                              fontSize: 11,
                              color: Colors.grey,
                              decoration: TextDecoration.lineThrough)),
                    const SizedBox(width: 6),
                    if (discount > 0)
                      Container(
                        padding: const EdgeInsets.symmetric(horizontal: 5, vertical: 1),
                        decoration: BoxDecoration(
                          color: Colors.green.shade700,
                          borderRadius: BorderRadius.circular(4),
                        ),
                        child: Text('-$discount%',
                            style: const TextStyle(
                                fontSize: 11, color: Colors.white, fontWeight: FontWeight.bold)),
                      ),
                  ]),
                ],
              ),
            ),

            // Actions menu
            PopupMenuButton<String>(
              icon: const Icon(Icons.more_vert, size: 18, color: Colors.grey),
              itemBuilder: (_) => [
                if (!isFake)
                  const PopupMenuItem(
                    value: 'fake',
                    child: Row(children: [
                      Icon(Icons.flag, size: 18, color: Colors.orange),
                      SizedBox(width: 8),
                      Text('Mark as Fake'),
                    ]),
                  ),
                const PopupMenuItem(
                  value: 'delete',
                  child: Row(children: [
                    Icon(Icons.delete_outline, size: 18, color: Colors.red),
                    SizedBox(width: 8),
                    Text('Delete', style: TextStyle(color: Colors.red)),
                  ]),
                ),
              ],
              onSelected: (v) {
                if (v == 'delete') onDelete();
                if (v == 'fake')   onFlagFake();
              },
            ),
          ],
        ),
      ),
    );
  }

  Widget _imagePlaceholder() => Container(
    width: 72, height: 72,
    color: Colors.grey.shade100,
    child: const Icon(Icons.image_not_supported_outlined, color: Colors.grey),
  );

  String _formatAge(dynamic ts) {
    try {
      DateTime dt;
      if (ts is Timestamp) {
        dt = ts.toDate();
      } else if (ts is String) {
        dt = DateTime.parse(ts);
      } else {
        return '';
      }
      final diff = DateTime.now().difference(dt.toLocal());
      if (diff.inMinutes < 60)  return '${diff.inMinutes}m ago';
      if (diff.inHours   < 24)  return '${diff.inHours}h ago';
      return '${diff.inDays}d ago';
    } catch (_) {
      return '';
    }
  }
}
