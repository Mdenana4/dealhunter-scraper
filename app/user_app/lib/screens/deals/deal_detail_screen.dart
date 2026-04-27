import 'package:cached_network_image/cached_network_image.dart';
import 'package:cloud_firestore/cloud_firestore.dart';
import 'package:firebase_auth/firebase_auth.dart';
import 'package:fl_chart/fl_chart.dart';
import 'package:flutter/material.dart';
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
      await ref2.update({
        'saved_deals': FieldValue.arrayRemove([deal.id]),
      });
    } else {
      await ref2.update({
        'saved_deals': FieldValue.arrayUnion([deal.id]),
      });
      ref.read(apiServiceProvider).logEvent('deal_save', {'deal_id': deal.id});
    }
    setState(() => _saved = !_saved);
  }

  Future<void> _launchBuy(DealModel deal) async {
    ref.read(apiServiceProvider).logEvent('buy_click', {'deal_id': deal.id});
    final uri = Uri.tryParse(deal.productUrl);
    if (uri != null) await launchUrl(uri, mode: LaunchMode.externalApplication);
  }

  void _share(DealModel deal) {
    Share.share(
      '🔥 ${deal.discountPercent}% OFF: ${deal.title}\n'
      '${deal.formattedPrice} (was ${deal.formattedOriginal})\n'
      '${deal.productUrl}',
    );
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
        onShare: () => _share(deal),
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
    required this.onShare,
  });

  final DealModel deal;
  final bool saved;
  final VoidCallback onSave;
  final VoidCallback onBuy;
  final VoidCallback onShare;

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
                onPressed: onShare,
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
                      productId: deal.id,
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

class _VerifyCard extends ConsumerWidget {
  const _VerifyCard({required this.deal});

  final DealModel deal;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final key = (
      marketplaceCountry: deal.source,
      productId: deal.id,
    );
    final verifyAsync = ref.watch(verifyProvider(key));
    final cs = Theme.of(context).colorScheme;

    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: verifyAsync.when(
          loading: () => const Row(
            children: [
              SizedBox(
                  width: 20,
                  height: 20,
                  child: CircularProgressIndicator(strokeWidth: 2)),
              SizedBox(width: 12),
              Text('Verifying discount...'),
            ],
          ),
          error: (_, __) => Row(
            children: [
              Icon(Icons.help_outline, color: cs.onSurfaceVariant),
              const SizedBox(width: 12),
              const Text('Verification unavailable'),
            ],
          ),
          data: (data) {
            final verdict = data['verdict'] as String? ?? 'uncertain';
            final confidence =
                (data['confidence'] as num?)?.toDouble() ?? 50.0;
            final explanation =
                data['explanation'] as String? ?? '';
            final redFlags =
                (data['red_flags'] as List?)?.map((e) => e.toString()).toList() ??
                    [];

            final (icon, color, label) = switch (verdict) {
              'genuine' => (
                  Icons.verified_rounded,
                  Colors.green,
                  'Genuine Deal'
                ),
              'fake' => (Icons.cancel_rounded, Colors.red, 'Fake Discount'),
              _ => (Icons.warning_rounded, Colors.orange, 'Uncertain'),
            };

            return Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    Icon(icon, color: color, size: 24),
                    const SizedBox(width: 8),
                    Text(label,
                        style: TextStyle(
                            fontWeight: FontWeight.bold, color: color)),
                    const Spacer(),
                    Text(
                      '${confidence.toStringAsFixed(0)}% confidence',
                      style: TextStyle(
                          fontSize: 12, color: cs.onSurfaceVariant),
                    ),
                  ],
                ),
                const SizedBox(height: 6),
                LinearProgressIndicator(
                  value: confidence / 100,
                  color: color,
                  backgroundColor: color.withValues(alpha: 0.16),
                ),
                if (explanation.isNotEmpty) ...[
                  const SizedBox(height: 8),
                  Text(explanation,
                      style: TextStyle(
                          fontSize: 13, color: cs.onSurfaceVariant)),
                ],
                for (final flag in redFlags) ...[
                  const SizedBox(height: 4),
                  Row(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Icon(Icons.flag_outlined,
                          size: 14, color: Colors.red.shade400),
                      const SizedBox(width: 6),
                      Expanded(
                        child: Text(flag,
                            style: const TextStyle(fontSize: 12)),
                      ),
                    ],
                  ),
                ],
              ],
            );
          },
        ),
      ),
    );
  }
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
      productId: widget.deal.id,
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
