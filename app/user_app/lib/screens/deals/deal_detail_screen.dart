import 'package:cached_network_image/cached_network_image.dart';
import 'package:cloud_firestore/cloud_firestore.dart';
import 'package:firebase_auth/firebase_auth.dart';
import 'package:fl_chart/fl_chart.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:share_plus/share_plus.dart';
import 'package:url_launcher/url_launcher.dart';
import '../../models/deal_model.dart';
import '../../models/user_model.dart';
import '../../providers/app_providers.dart';

class DealDetailScreen extends ConsumerStatefulWidget {
  const DealDetailScreen({
    super.key,
    required this.dealId,
    this.deal,
  });

  final String dealId;
  final DealModel? deal;

  @override
  ConsumerState<DealDetailScreen> createState() => _DealDetailScreenState();
}

class _DealDetailScreenState extends ConsumerState<DealDetailScreen> {
  bool _saved = false;

  @override
  void initState() {
    super.initState();
    _checkSaved();
    _logView();
  }

  void _checkSaved() {
    final uid = FirebaseAuth.instance.currentUser?.uid;
    if (uid == null) return;
    FirebaseFirestore.instance
        .collection('users')
        .doc(uid)
        .get()
        .then((snap) {
      if (!mounted) return;
      final list = (snap.data()?['saved_deals'] as List?) ?? [];
      setState(() => _saved = list.contains(widget.dealId));
    });
  }

  void _logView() {
    ref.read(apiServiceProvider).logEvent('deal_view', {'deal_id': widget.dealId});
  }

  Future<void> _toggleSave(DealModel deal) async {
    final uid = FirebaseAuth.instance.currentUser?.uid;
    if (uid == null) return;
    final ref2 = FirebaseFirestore.instance.collection('users').doc(uid);
    if (_saved) {
      await ref2.set({
        'saved_deals': FieldValue.arrayRemove([deal.id]),
      }, SetOptions(merge: true));
    } else {
      await ref2.set({
        'saved_deals': FieldValue.arrayUnion([deal.id]),
      }, SetOptions(merge: true));
      ref.read(apiServiceProvider).logEvent('deal_save', {'deal_id': deal.id});
    }
    setState(() => _saved = !_saved);
  }

  Future<void> _launchBuy(DealModel deal) async {
    ref.read(apiServiceProvider).logEvent('buy_click', {'deal_id': deal.id});
    final uri = Uri.tryParse(deal.productUrl);
    if (uri != null) await launchUrl(uri, mode: LaunchMode.externalApplication);
  }

  @override
  Widget build(BuildContext context) {
    final dealAsync = widget.deal != null
        ? AsyncValue.data(widget.deal!)
        : ref.watch(dealDetailProvider(widget.dealId));

    return dealAsync.when(
      loading: () => const Scaffold(
          body: Center(child: CircularProgressIndicator())),
      error: (e, _) => Scaffold(
        appBar: AppBar(),
        body: Center(child: Text('Failed to load: $e')),
      ),
      data: (deal) => _DealDetailBody(
        deal: deal,
        saved: _saved,
        onSave: () => _toggleSave(deal),
        onBuy: () => _launchBuy(deal),
      ),
    );
  }
}

class _DealDetailBody extends ConsumerWidget {
  const _DealDetailBody({
    required this.deal,
    required this.saved,
    required this.onSave,
    required this.onBuy,
  });

  final DealModel deal;
  final bool saved;
  final VoidCallback onSave;
  final VoidCallback onBuy;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final cs = Theme.of(context).colorScheme;
    final user = ref.watch(currentUserProvider).valueOrNull;
    final membership = user?.membership ?? const MembershipInfo();

    return Scaffold(
      body: CustomScrollView(
        slivers: [
          // ── Hero image app bar ─────────────────────────────────────────────
          SliverAppBar(
            expandedHeight: 280,
            pinned: true,
            actions: [
              IconButton(
                icon: Icon(saved ? Icons.bookmark : Icons.bookmark_outline),
                onPressed: onSave,
              ),
              IconButton(
                icon: const Icon(Icons.share_outlined),
                onPressed: () => _showShareSheet(context, deal),
              ),
            ],
            flexibleSpace: FlexibleSpaceBar(
              background: deal.imageUrl.isNotEmpty
                  ? CachedNetworkImage(
                      imageUrl: deal.imageUrl,
                      fit: BoxFit.cover,
                      errorWidget: (_, __, ___) => Container(
                        color: cs.surfaceContainerHighest,
                        child: const Icon(Icons.image_not_supported_outlined,
                            size: 64),
                      ),
                    )
                  : Container(
                      color: cs.surfaceContainerHighest,
                      child: const Icon(Icons.image_outlined, size: 64),
                    ),
            ),
          ),

          SliverToBoxAdapter(
            child: Padding(
              padding: const EdgeInsets.all(16),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  // ── Title & store ──────────────────────────────────────────
                  Text(deal.title,
                      style: Theme.of(context).textTheme.titleLarge),
                  const SizedBox(height: 4),
                  Row(
                    children: [
                      Icon(Icons.storefront_outlined,
                          size: 14, color: cs.onSurfaceVariant),
                      const SizedBox(width: 4),
                      Text(deal.store,
                          style: TextStyle(
                              color: cs.onSurfaceVariant, fontSize: 13)),
                      if (deal.category.isNotEmpty) ...[
                        const SizedBox(width: 12),
                        Icon(Icons.category_outlined,
                            size: 14, color: cs.onSurfaceVariant),
                        const SizedBox(width: 4),
                        Text(deal.category,
                            style: TextStyle(
                                color: cs.onSurfaceVariant, fontSize: 13)),
                      ],
                    ],
                  ),

                  const SizedBox(height: 16),

                  // ── Price ──────────────────────────────────────────────────
                  Row(
                    crossAxisAlignment: CrossAxisAlignment.end,
                    children: [
                      Text(
                        deal.formattedPrice,
                        style: TextStyle(
                          fontSize: 28,
                          fontWeight: FontWeight.bold,
                          color: cs.primary,
                        ),
                      ),
                      const SizedBox(width: 10),
                      if (deal.originalPrice > deal.currentPrice) ...[
                        Text(
                          deal.formattedOriginal,
                          style: TextStyle(
                            fontSize: 16,
                            decoration: TextDecoration.lineThrough,
                            color: cs.onSurfaceVariant,
                          ),
                        ),
                        const SizedBox(width: 8),
                        Container(
                          padding: const EdgeInsets.symmetric(
                              horizontal: 8, vertical: 3),
                          decoration: BoxDecoration(
                            color: Colors.red.shade600,
                            borderRadius: BorderRadius.circular(6),
                          ),
                          child: Text(
                            '-${deal.discountPercent}%',
                            style: const TextStyle(
                                color: Colors.white,
                                fontWeight: FontWeight.bold),
                          ),
                        ),
                      ],
                    ],
                  ),
                  if (deal.savings > 0)
                    Text(
                      'You save ${deal.currency} ${deal.savings.toStringAsFixed(0)}',
                      style: TextStyle(color: Colors.green.shade700),
                    ),

                  const SizedBox(height: 20),

                  // ── Verify card ────────────────────────────────────────────
                  _VerifyCard(deal: deal),

                  const SizedBox(height: 20),

                  // ── Price history ──────────────────────────────────────────
                  _PriceHistoryCard(deal: deal, membership: membership),

                  const SizedBox(height: 24),

                  // ── Buy button ─────────────────────────────────────────────
                  SizedBox(
                    width: double.infinity,
                    child: FilledButton.icon(
                      icon: const Icon(Icons.shopping_cart_outlined),
                      label: const Text('Buy Now',
                          style: TextStyle(fontSize: 16)),
                      style: FilledButton.styleFrom(
                          padding: const EdgeInsets.all(16)),
                      onPressed: onBuy,
                    ),
                  ),

                  const SizedBox(height: 12),

                  // ── Set price alert ────────────────────────────────────────
                  SizedBox(
                    width: double.infinity,
                    child: OutlinedButton.icon(
                      icon: const Icon(Icons.notifications_active_outlined),
                      label: const Text('Set Price Alert'),
                      onPressed: () => _showAlertDialog(context, ref, deal),
                    ),
                  ),
                  const SizedBox(height: 24),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }

  void _showAlertDialog(
    BuildContext context,
    WidgetRef ref,
    DealModel deal,
  ) {
    final uid = FirebaseAuth.instance.currentUser?.uid;
    if (uid == null) {
      ScaffoldMessenger.of(context)
          .showSnackBar(const SnackBar(content: Text('Sign in to set alerts')));
      return;
    }
    final ctrl = TextEditingController(
        text: (deal.currentPrice * 0.9).toStringAsFixed(0));
    showDialog(
      context: context,
      builder: (_) => AlertDialog(
        title: const Text('Price Alert'),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Text(
              'Alert me when price drops below:',
              style: TextStyle(
                  color: Theme.of(context).colorScheme.onSurfaceVariant),
            ),
            const SizedBox(height: 12),
            TextField(
              controller: ctrl,
              keyboardType: TextInputType.number,
              decoration: InputDecoration(
                labelText: 'Target price',
                prefixText: '${deal.currency} ',
                border: const OutlineInputBorder(),
              ),
            ),
          ],
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('Cancel'),
          ),
          FilledButton(
            onPressed: () async {
              final target = double.tryParse(ctrl.text);
              if (target == null || target <= 0 || target >= deal.currentPrice) {
                ScaffoldMessenger.of(context).showSnackBar(
                  SnackBar(
                    content: Text(
                      'Enter a price between 0 and ${deal.formattedPrice}',
                    ),
                  ),
                );
                return;
              }
              Navigator.pop(context);
              try {
                await ref.read(apiServiceProvider).createAlert(
                      userId: uid,
                      marketplaceCountry: deal.source,
                      productId: deal.productId,
                      targetPrice: target,
                    );
                if (context.mounted) {
                  ScaffoldMessenger.of(context).showSnackBar(
                    const SnackBar(content: Text('Alert set!')),
                  );
                }
              } catch (_) {
                if (context.mounted) {
                  ScaffoldMessenger.of(context).showSnackBar(
                    const SnackBar(content: Text('Failed to set alert')),
                  );
                }
              }
            },
            child: const Text('Set Alert'),
          ),
        ],
      ),
    );
  }
}

// ─── Verify card ───────────────────────────────────────────────────────────

class _VerifyCard extends ConsumerStatefulWidget {
  const _VerifyCard({required this.deal});
  final DealModel deal;

  @override
  ConsumerState<_VerifyCard> createState() => _VerifyCardState();
}

class _VerifyCardState extends ConsumerState<_VerifyCard> {
  bool _checking = false;
  Map<String, dynamic>? _result;
  String? _error;

  Future<void> _verify() async {
    setState(() { _checking = true; _error = null; });
    try {
      final data = await ref.read(apiServiceProvider).verify(
        widget.deal.source,
        widget.deal.productId,
        productUrl: widget.deal.productUrl,
        originalPrice: widget.deal.originalPrice,
        currentPrice: widget.deal.currentPrice,
        discountPercent: widget.deal.discountPercent,
      );
      setState(() { _result = data; _checking = false; });
    } catch (e) {
      setState(() { _error = 'Verification failed. Try again.'; _checking = false; });
    }
  }

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;

    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: _checking
            ? const Row(children: [
                SizedBox(width: 20, height: 20,
                    child: CircularProgressIndicator(strokeWidth: 2)),
                SizedBox(width: 12),
                Expanded(child: Text(
                  'Checking Safqa & Kanbkam for real price history…',
                  style: TextStyle(fontSize: 13),
                )),
              ])
            : _result == null
                ? _VerifyPrompt(
                    deal: widget.deal,
                    onVerify: _verify,
                    error: _error,
                  )
                : _VerifyResult(data: _result!, currency: widget.deal.currency,
                    onRecheck: _verify),
      ),
    );
  }
}

class _VerifyPrompt extends StatelessWidget {
  const _VerifyPrompt({required this.deal, required this.onVerify, this.error});

  final DealModel deal;
  final VoidCallback onVerify;
  final String? error;

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(children: [
          Icon(Icons.shield_outlined, color: cs.primary),
          const SizedBox(width: 8),
          const Text('Is this discount real?',
              style: TextStyle(fontWeight: FontWeight.bold, fontSize: 15)),
        ]),
        const SizedBox(height: 6),
        Text(
          'We\'ll check Safqa & Kanbkam for the real price history to verify '
          'if the "was" price was ever genuine.',
          style: TextStyle(fontSize: 12, color: cs.onSurfaceVariant),
        ),
        if (error != null) ...[
          const SizedBox(height: 8),
          Text(error!, style: TextStyle(fontSize: 12, color: cs.error)),
        ],
        const SizedBox(height: 12),
        SizedBox(
          width: double.infinity,
          child: OutlinedButton.icon(
            icon: const Icon(Icons.search_rounded, size: 18),
            label: Text(error != null ? 'Try Again' : 'Verify Discount'),
            onPressed: onVerify,
          ),
        ),
      ],
    );
  }
}

class _VerifyResult extends StatelessWidget {
  const _VerifyResult({required this.data, required this.currency, required this.onRecheck});

  final Map<String, dynamic> data;
  final String currency;
  final VoidCallback onRecheck;

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    final verdict     = data['verdict'] as String? ?? 'uncertain';
    final confidence  = (data['confidence'] as num?)?.toDouble() ?? 50.0;
    final explanation = data['explanation'] as String? ?? '';
    final redFlags    = (data['red_flags'] as List?)?.map((e) => e.toString()).toList() ?? [];
    final recommendation = data['recommendation'] as String? ?? '';
    final histHigh    = (data['historical_high'] as num?)?.toDouble() ?? 0;
    final histLow     = (data['historical_low']  as num?)?.toDouble() ?? 0;
    final sourceUsed  = data['source_used'] as String? ?? '';
    final safqaFound  = data['safqa_found']   == true;
    final kanbkamFound = data['kanbkam_found'] == true;

    final (icon, color, label) = switch (verdict) {
      'genuine'  => (Icons.verified_rounded,  Colors.green,  'Genuine Deal'),
      'fake'     => (Icons.cancel_rounded,    Colors.red,    'Fake Discount'),
      _          => (Icons.warning_rounded,   Colors.orange, 'Suspicious'),
    };

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        // Verdict row
        Row(children: [
          Icon(icon, color: color, size: 26),
          const SizedBox(width: 8),
          Text(label, style: TextStyle(
              fontWeight: FontWeight.bold, color: color, fontSize: 16)),
          const Spacer(),
          Text('${confidence.toStringAsFixed(0)}% confident',
              style: TextStyle(fontSize: 11, color: cs.onSurfaceVariant)),
        ]),
        const SizedBox(height: 6),
        LinearProgressIndicator(
          value: confidence / 100,
          color: color,
          backgroundColor: color.withValues(alpha: 0.15),
        ),

        // Historical price boxes (show only when data found)
        if (histHigh > 0) ...[
          const SizedBox(height: 12),
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
            decoration: BoxDecoration(
              color: cs.surfaceContainerHighest,
              borderRadius: BorderRadius.circular(8),
            ),
            child: Row(
              mainAxisAlignment: MainAxisAlignment.spaceAround,
              children: [
                _PriceStat('Historical High',
                    '$currency ${histHigh.toStringAsFixed(0)}', Colors.red.shade600),
                if (histLow > 0)
                  _PriceStat('Historical Low',
                      '$currency ${histLow.toStringAsFixed(0)}', Colors.green.shade600),
                _PriceStat('Source', sourceUsed, cs.primary),
              ],
            ),
          ),
        ],

        // Source badges
        const SizedBox(height: 10),
        Wrap(spacing: 6, children: [
          if (safqaFound)
            _Badge('Safqa ✓', Colors.blue.shade700),
          if (kanbkamFound)
            _Badge('Kanbkam ✓', Colors.orange.shade700),
          if (!safqaFound && !kanbkamFound)
            _Badge('Ratio analysis only', Colors.grey.shade600),
        ]),

        // Explanation
        if (explanation.isNotEmpty) ...[
          const SizedBox(height: 10),
          Text(explanation,
              style: TextStyle(fontSize: 12, color: cs.onSurfaceVariant)),
        ],

        // Red flags
        for (final flag in redFlags) ...[
          const SizedBox(height: 6),
          Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Icon(Icons.flag_rounded, size: 13, color: Colors.red.shade400),
            const SizedBox(width: 6),
            Expanded(child: Text(flag, style: const TextStyle(fontSize: 12))),
          ]),
        ],

        // Recommendation
        if (recommendation.isNotEmpty) ...[
          const SizedBox(height: 10),
          Container(
            width: double.infinity,
            padding: const EdgeInsets.all(10),
            decoration: BoxDecoration(
              color: color.withValues(alpha: 0.08),
              borderRadius: BorderRadius.circular(8),
              border: Border.all(color: color.withValues(alpha: 0.3)),
            ),
            child: Text(recommendation,
                style: TextStyle(fontSize: 12, color: color,
                    fontWeight: FontWeight.w500)),
          ),
        ],

        // Recheck
        const SizedBox(height: 10),
        Align(
          alignment: Alignment.centerRight,
          child: TextButton.icon(
            icon: const Icon(Icons.refresh, size: 14),
            label: const Text('Re-check', style: TextStyle(fontSize: 12)),
            onPressed: onRecheck,
          ),
        ),
      ],
    );
  }
}

class _PriceStat extends StatelessWidget {
  const _PriceStat(this.label, this.value, this.color);
  final String label;
  final String value;
  final Color color;

  @override
  Widget build(BuildContext context) => Column(children: [
    Text(label, style: TextStyle(
        fontSize: 10, color: Theme.of(context).colorScheme.onSurfaceVariant)),
    const SizedBox(height: 2),
    Text(value, style: TextStyle(
        fontWeight: FontWeight.bold, fontSize: 13, color: color)),
  ]);
}

class _Badge extends StatelessWidget {
  const _Badge(this.label, this.color);
  final String label;
  final Color color;

  @override
  Widget build(BuildContext context) => Container(
    padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
    decoration: BoxDecoration(
      color: color.withValues(alpha: 0.12),
      borderRadius: BorderRadius.circular(12),
      border: Border.all(color: color.withValues(alpha: 0.4)),
    ),
    child: Text(label, style: TextStyle(fontSize: 11, color: color,
        fontWeight: FontWeight.w500)),
  );
}

// ─── Price history chart ───────────────────────────────────────────────────

class _PriceHistoryCard extends ConsumerStatefulWidget {
  const _PriceHistoryCard({
    required this.deal,
    required this.membership,
  });

  final DealModel deal;
  final MembershipInfo membership;

  @override
  ConsumerState<_PriceHistoryCard> createState() =>
      _PriceHistoryCardState();
}

class _PriceHistoryCardState extends ConsumerState<_PriceHistoryCard> {
  int _days = 30;

  @override
  void initState() {
    super.initState();
    _days = widget.membership.priceHistoryDays.clamp(30, 180);
  }

  @override
  Widget build(BuildContext context) {
    final key = (
      marketplaceCountry: widget.deal.source,
      productId: widget.deal.productId,
      days: _days,
    );
    final histAsync = ref.watch(priceHistoryProvider(key));
    final cs = Theme.of(context).colorScheme;

    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                const Text('Price History',
                    style: TextStyle(fontWeight: FontWeight.bold)),
                const Spacer(),
                _DaysPicker(
                  days: _days,
                  maxDays: widget.membership.priceHistoryDays,
                  onChange: (d) => setState(() => _days = d),
                ),
              ],
            ),
            const SizedBox(height: 16),
            histAsync.when(
              loading: () => const SizedBox(
                height: 150,
                child: Center(child: CircularProgressIndicator()),
              ),
              error: (_, __) => SizedBox(
                height: 80,
                child: Center(
                  child: Text('No history available',
                      style:
                          TextStyle(color: cs.onSurfaceVariant)),
                ),
              ),
              data: (history) {
                if (history.isEmpty) {
                  return SizedBox(
                    height: 80,
                    child: Center(
                      child: Text('No price history yet',
                          style: TextStyle(color: cs.onSurfaceVariant)),
                    ),
                  );
                }
                return _LineChart(history: history, currency: widget.deal.currency);
              },
            ),
          ],
        ),
      ),
    );
  }
}

class _DaysPicker extends StatelessWidget {
  const _DaysPicker(
      {required this.days, required this.maxDays, required this.onChange});

  final int days;
  final int maxDays;
  final ValueChanged<int> onChange;

  static const _options = [30, 60, 90, 180];

  @override
  Widget build(BuildContext context) {
    return SegmentedButton<int>(
      style: SegmentedButton.styleFrom(
        tapTargetSize: MaterialTapTargetSize.shrinkWrap,
        visualDensity: VisualDensity.compact,
      ),
      segments: _options
          .where((d) => d <= maxDays || d == 30)
          .map((d) => ButtonSegment(
                value: d,
                label: Text('${d}d', style: const TextStyle(fontSize: 11)),
              ))
          .toList(),
      selected: {days},
      onSelectionChanged: (s) => onChange(s.first),
    );
  }
}

class _LineChart extends StatelessWidget {
  const _LineChart({required this.history, required this.currency});

  final List<Map<String, dynamic>> history;
  final String currency;

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    final prices = history
        .map((e) => (e['price'] as num?)?.toDouble() ?? 0.0)
        .toList();

    if (prices.isEmpty) return const SizedBox.shrink();

    final spots = prices
        .asMap()
        .entries
        .map((e) => FlSpot(e.key.toDouble(), e.value))
        .toList();

    final minY = (prices.reduce((a, b) => a < b ? a : b) * 0.9);
    final maxY = (prices.reduce((a, b) => a > b ? a : b) * 1.1);

    // Stats row
    final avg = prices.reduce((a, b) => a + b) / prices.length;
    final low = prices.reduce((a, b) => a < b ? a : b);
    final high = prices.reduce((a, b) => a > b ? a : b);

    return Column(
      children: [
        SizedBox(
          height: 160,
          child: LineChart(
            LineChartData(
              minY: minY,
              maxY: maxY,
              gridData: const FlGridData(show: false),
              borderData: FlBorderData(show: false),
              titlesData: FlTitlesData(
                leftTitles: const AxisTitles(
                    sideTitles: SideTitles(showTitles: false)),
                rightTitles: AxisTitles(
                  sideTitles: SideTitles(
                    showTitles: true,
                    reservedSize: 52,
                    getTitlesWidget: (v, _) => Text(
                      '$currency ${v.toStringAsFixed(0)}',
                      style: const TextStyle(fontSize: 9),
                    ),
                  ),
                ),
                topTitles: const AxisTitles(
                    sideTitles: SideTitles(showTitles: false)),
                bottomTitles: const AxisTitles(
                    sideTitles: SideTitles(showTitles: false)),
              ),
              lineBarsData: [
                LineChartBarData(
                  spots: spots,
                  isCurved: true,
                  color: cs.primary,
                  barWidth: 2,
                  dotData: const FlDotData(show: false),
                  belowBarData: BarAreaData(
                    show: true,
                    color: cs.primary.withValues(alpha: 0.10),
                  ),
                ),
              ],
            ),
          ),
        ),
        const SizedBox(height: 12),
        Row(
          mainAxisAlignment: MainAxisAlignment.spaceAround,
          children: [
            _StatChip(label: 'Lowest', value: '$currency ${low.toStringAsFixed(0)}',
                color: Colors.green),
            _StatChip(label: 'Average', value: '$currency ${avg.toStringAsFixed(0)}',
                color: cs.primary),
            _StatChip(label: 'Highest', value: '$currency ${high.toStringAsFixed(0)}',
                color: Colors.red),
          ],
        ),
      ],
    );
  }
}

class _StatChip extends StatelessWidget {
  const _StatChip(
      {required this.label, required this.value, required this.color});

  final String label;
  final String value;
  final Color color;

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        Text(label,
            style: TextStyle(
                fontSize: 11,
                color: Theme.of(context).colorScheme.onSurfaceVariant)),
        Text(value,
            style: TextStyle(
                fontWeight: FontWeight.bold, color: color, fontSize: 13)),
      ],
    );
  }
}

// ─── Social share sheet ────────────────────────────────────────────────────

void _showShareSheet(BuildContext context, DealModel deal) {
  final text = '🔥 ${deal.discountPercent}% OFF: ${deal.title}\n'
      '${deal.formattedPrice} (was ${deal.formattedOriginal})\n'
      '${deal.productUrl}';
  final encodedText = Uri.encodeComponent(text);
  final encodedUrl = Uri.encodeComponent(deal.productUrl);

  showModalBottomSheet(
    context: context,
    shape: const RoundedRectangleBorder(
      borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
    ),
    builder: (ctx) => SafeArea(
      child: Padding(
        padding: const EdgeInsets.fromLTRB(20, 20, 20, 12),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text('Share via',
                style: TextStyle(fontWeight: FontWeight.bold, fontSize: 16)),
            const SizedBox(height: 20),
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceAround,
              children: [
                _ShareButton(
                  label: 'WhatsApp',
                  color: const Color(0xFF25D366),
                  icon: Icons.chat_rounded,
                  onTap: () {
                    Navigator.pop(ctx);
                    launchUrl(
                      Uri.parse('https://wa.me/?text=$encodedText'),
                      mode: LaunchMode.externalApplication,
                    );
                  },
                ),
                _ShareButton(
                  label: 'Telegram',
                  color: const Color(0xFF0088CC),
                  icon: Icons.send_rounded,
                  onTap: () {
                    Navigator.pop(ctx);
                    launchUrl(
                      Uri.parse(
                          'https://t.me/share/url?url=$encodedUrl&text=$encodedText'),
                      mode: LaunchMode.externalApplication,
                    );
                  },
                ),
                _ShareButton(
                  label: 'Facebook',
                  color: const Color(0xFF1877F2),
                  icon: Icons.facebook_rounded,
                  onTap: () {
                    Navigator.pop(ctx);
                    launchUrl(
                      Uri.parse(
                          'https://www.facebook.com/sharer/sharer.php?u=$encodedUrl'),
                      mode: LaunchMode.externalApplication,
                    );
                  },
                ),
                _ShareButton(
                  label: 'Instagram',
                  color: const Color(0xFFE1306C),
                  icon: Icons.camera_alt_rounded,
                  onTap: () {
                    Navigator.pop(ctx);
                    Clipboard.setData(ClipboardData(text: text));
                    ScaffoldMessenger.of(context).showSnackBar(
                      const SnackBar(
                        content:
                            Text('Copied! Open Instagram and paste in your story or message.'),
                      ),
                    );
                  },
                ),
                _ShareButton(
                  label: 'More',
                  color: Colors.grey.shade600,
                  icon: Icons.more_horiz_rounded,
                  onTap: () {
                    Navigator.pop(ctx);
                    Share.share(text);
                  },
                ),
              ],
            ),
          ],
        ),
      ),
    ),
  );
}

class _ShareButton extends StatelessWidget {
  const _ShareButton({
    required this.label,
    required this.color,
    required this.icon,
    required this.onTap,
  });

  final String label;
  final Color color;
  final IconData icon;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onTap,
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Container(
            width: 52,
            height: 52,
            decoration: BoxDecoration(color: color, shape: BoxShape.circle),
            child: Icon(icon, color: Colors.white, size: 26),
          ),
          const SizedBox(height: 6),
          Text(label, style: const TextStyle(fontSize: 11)),
        ],
      ),
    );
  }
}
