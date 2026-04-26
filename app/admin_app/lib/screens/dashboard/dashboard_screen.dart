import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:fl_chart/fl_chart.dart';
import 'package:go_router/go_router.dart';
import 'package:intl/intl.dart';
import '../../providers/admin_providers.dart';

class DashboardScreen extends ConsumerWidget {
  const DashboardScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final userStats    = ref.watch(userStatsProvider);
    final scraperHealth = ref.watch(scraperHealthProvider);
    final recentChanges = ref.watch(recentChangesCountProvider);
    final eventCounts  = ref.watch(eventCountsProvider);

    return Scaffold(
      appBar: AppBar(
        title: const Text('DealHunter Admin'),
        actions: [
          IconButton(
            icon: const Icon(Icons.refresh),
            onPressed: () {
              ref.invalidate(userStatsProvider);
              ref.invalidate(scraperHealthProvider);
              ref.invalidate(eventCountsProvider);
            },
          ),
          const SizedBox(width: 8),
        ],
      ),
      body: RefreshIndicator(
        onRefresh: () async {
          ref.invalidate(userStatsProvider);
          ref.invalidate(eventCountsProvider);
        },
        child: SingleChildScrollView(
          physics: const AlwaysScrollableScrollPhysics(),
          padding: const EdgeInsets.all(16),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [

              // ─── Top KPI row ────────────────────────────────────────────
              _SectionHeader('Overview — Live'),
              const SizedBox(height: 12),

              userStats.when(
                loading: () => _KpiRowSkeleton(),
                error: (e, _) => _ErrorTile('$e'),
                data: (stats) {
                  final total = stats['total'] as int? ?? 0;
                  final byTier = stats['by_tier'] as Map? ?? {};
                  return Column(
                    children: [
                      Row(children: [
                        _KpiCard(label: 'Total Users', value: '$total',
                            icon: Icons.people, color: Colors.blue),
                        const SizedBox(width: 12),
                        _KpiCard(
                          label: 'VIP',
                          value: '${byTier['vip'] ?? 0}',
                          icon: Icons.workspace_premium,
                          color: Colors.purple,
                        ),
                      ]),
                      const SizedBox(height: 12),
                      Row(children: [
                        _KpiCard(
                          label: 'Premium',
                          value: '${byTier['premium'] ?? 0}',
                          icon: Icons.star,
                          color: Colors.blue.shade700,
                        ),
                        const SizedBox(width: 12),
                        _KpiCard(
                          label: 'Basic',
                          value: '${byTier['basic'] ?? 0}',
                          icon: Icons.person,
                          color: Colors.teal,
                        ),
                      ]),
                      const SizedBox(height: 12),

                      // Tier distribution pie chart
                      if (total > 0)
                        _TierPieCard(byTier: Map<String, int>.from(byTier)),
                    ],
                  );
                },
              ),

              const SizedBox(height: 20),

              // ─── Engagement ─────────────────────────────────────────────
              _SectionHeader('Engagement (last 24h)'),
              const SizedBox(height: 12),

              Row(children: [
                Expanded(
                  child: recentChanges.when(
                    loading: () => _KpiCard(label: 'Price Changes',
                        value: '…', icon: Icons.trending_down, color: Colors.green),
                    error: (_, __) => _KpiCard(label: 'Price Changes',
                        value: '—', icon: Icons.trending_down, color: Colors.green),
                    data: (n) => _KpiCard(label: 'Price Changes',
                        value: '$n', icon: Icons.trending_down, color: Colors.green),
                  ),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: eventCounts.when(
                    loading: () => _KpiCard(label: 'Buy Clicks',
                        value: '…', icon: Icons.shopping_cart, color: Colors.orange),
                    error: (_, __) => _KpiCard(label: 'Buy Clicks',
                        value: '—', icon: Icons.shopping_cart, color: Colors.orange),
                    data: (counts) => _KpiCard(
                      label: 'Buy Clicks',
                      value: '${counts['buy_clicked'] ?? 0}',
                      icon: Icons.shopping_cart,
                      color: Colors.orange,
                    ),
                  ),
                ),
              ]),

              const SizedBox(height: 12),

              eventCounts.when(
                loading: () => const SizedBox(),
                error: (_, __) => const SizedBox(),
                data: (counts) => Row(children: [
                  Expanded(
                    child: _KpiCard(
                      label: 'Deals Viewed',
                      value: '${counts['deal_viewed'] ?? 0}',
                      icon: Icons.visibility,
                      color: Colors.indigo,
                    ),
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: _KpiCard(
                      label: 'Purchased',
                      value: '${counts['purchase_confirmed'] ?? 0}',
                      icon: Icons.check_circle,
                      color: Colors.green.shade700,
                    ),
                  ),
                ]),
              ),

              const SizedBox(height: 20),

              // ─── Scraper Health ──────────────────────────────────────────
              _SectionHeader('Scraper Health — Latest Cycle'),
              const SizedBox(height: 12),

              scraperHealth.when(
                loading: () => _LoadingCard(),
                error: (e, _) => _ErrorTile('$e'),
                data: (health) {
                  if (health.isEmpty) {
                    return _InfoCard('No scraper cycle recorded yet.');
                  }
                  final cycle = health['cycle'] as Map? ?? {};
                  final broken = (health['broken_scrapers'] as List?) ?? [];
                  final hasAlerts = health['has_alerts'] as bool? ?? false;
                  final ts = health['timestamp'];

                  return Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      if (ts != null)
                        Text('Last run: ${_formatTimestamp(ts)}',
                            style: const TextStyle(
                                fontSize: 12, color: Colors.grey)),
                      const SizedBox(height: 8),
                      if (hasAlerts)
                        _AlertBanner(broken: broken.cast<Map>()),
                      ...cycle.entries.map((e) => _ScraperRow(
                            name: e.key,
                            count: e.value as int? ?? 0,
                            isBroken: broken.any(
                                (b) => (b as Map)['scraper'] == e.key),
                          )),
                    ],
                  );
                },
              ),

              const SizedBox(height: 20),

              // ─── Quick actions ───────────────────────────────────────────
              _SectionHeader('Quick Actions'),
              const SizedBox(height: 12),

              GridView.count(
                crossAxisCount: 2,
                shrinkWrap: true,
                physics: const NeverScrollableScrollPhysics(),
                mainAxisSpacing: 12,
                crossAxisSpacing: 12,
                childAspectRatio: 1.5,
                children: [
                  _ActionCard(
                    icon: Icons.people,
                    label: 'Users',
                    color: Colors.blue,
                    onTap: () => context.go('/users'),
                  ),
                  _ActionCard(
                    icon: Icons.groups,
                    label: 'Groups',
                    color: Colors.teal,
                    onTap: () => context.go('/groups'),
                  ),
                  _ActionCard(
                    icon: Icons.storage,
                    label: 'Sources',
                    color: Colors.deepOrange,
                    onTap: () => context.go('/sources'),
                  ),
                  _ActionCard(
                    icon: Icons.campaign,
                    label: 'Broadcast',
                    color: Colors.purple,
                    onTap: () => context.go('/notifications'),
                  ),
                ],
              ),

              const SizedBox(height: 32),
            ],
          ),
        ),
      ),
    );
  }

  String _formatTimestamp(dynamic ts) {
    try {
      final dt = ts is String ? DateTime.parse(ts) : DateTime.now();
      return DateFormat('MMM d, HH:mm').format(dt.toLocal());
    } catch (_) {
      return '—';
    }
  }
}

// ─── Reusable widgets ─────────────────────────────────────────────────────

class _SectionHeader extends StatelessWidget {
  final String title;
  const _SectionHeader(this.title);

  @override
  Widget build(BuildContext context) {
    return Text(title,
        style: Theme.of(context).textTheme.titleMedium
            ?.copyWith(fontWeight: FontWeight.w700));
  }
}

class _KpiCard extends StatelessWidget {
  final String label;
  final String value;
  final IconData icon;
  final Color color;
  const _KpiCard(
      {required this.label,
      required this.value,
      required this.icon,
      required this.color});

  @override
  Widget build(BuildContext context) {
    return Expanded(
      child: Card(
        child: Padding(
          padding: const EdgeInsets.symmetric(vertical: 16, horizontal: 14),
          child: Row(
            children: [
              Container(
                padding: const EdgeInsets.all(10),
                decoration: BoxDecoration(
                  color: color.withOpacity(0.12),
                  borderRadius: BorderRadius.circular(10),
                ),
                child: Icon(icon, color: color, size: 22),
              ),
              const SizedBox(width: 12),
              Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(value,
                      style: TextStyle(
                          fontSize: 22,
                          fontWeight: FontWeight.w700,
                          color: color)),
                  Text(label,
                      style: const TextStyle(
                          fontSize: 12, color: Colors.grey)),
                ],
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _TierPieCard extends StatelessWidget {
  final Map<String, int> byTier;
  const _TierPieCard({required this.byTier});

  static const _colors = {
    'free': Colors.grey,
    'basic': Colors.teal,
    'premium': Colors.blue,
    'vip': Colors.purple,
  };

  @override
  Widget build(BuildContext context) {
    final total = byTier.values.fold(0, (a, b) => a + b);
    if (total == 0) return const SizedBox();

    final sections = byTier.entries.where((e) => e.value > 0).map((e) {
      final pct = e.value / total * 100;
      return PieChartSectionData(
        value: e.value.toDouble(),
        color: _colors[e.key] ?? Colors.grey,
        title: '${pct.toStringAsFixed(0)}%',
        radius: 60,
        titleStyle: const TextStyle(
            fontSize: 12, fontWeight: FontWeight.w700, color: Colors.white),
      );
    }).toList();

    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text('Membership Distribution',
                style: Theme.of(context).textTheme.titleSmall),
            const SizedBox(height: 12),
            SizedBox(
              height: 160,
              child: Row(
                children: [
                  Expanded(
                    child: PieChart(PieChartData(
                      sections: sections,
                      centerSpaceRadius: 30,
                      sectionsSpace: 2,
                    )),
                  ),
                  const SizedBox(width: 16),
                  Column(
                    mainAxisAlignment: MainAxisAlignment.center,
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: byTier.entries.map((e) => Padding(
                          padding: const EdgeInsets.only(bottom: 6),
                          child: Row(children: [
                            Container(
                              width: 12,
                              height: 12,
                              decoration: BoxDecoration(
                                color: _colors[e.key] ?? Colors.grey,
                                shape: BoxShape.circle,
                              ),
                            ),
                            const SizedBox(width: 6),
                            Text(
                              '${e.key.toUpperCase()}: ${e.value}',
                              style: const TextStyle(fontSize: 12),
                            ),
                          ]),
                        )).toList(),
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _AlertBanner extends StatelessWidget {
  final List<Map> broken;
  const _AlertBanner({required this.broken});

  @override
  Widget build(BuildContext context) {
    return Container(
      margin: const EdgeInsets.only(bottom: 10),
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: Colors.red.shade50,
        borderRadius: BorderRadius.circular(10),
        border: Border.all(color: Colors.red.shade300),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Row(children: [
            Icon(Icons.warning_amber_rounded, color: Colors.red, size: 18),
            SizedBox(width: 6),
            Text('Scraper Alert — HTML may have changed',
                style: TextStyle(fontWeight: FontWeight.w700, color: Colors.red)),
          ]),
          const SizedBox(height: 6),
          ...broken.map((b) => Text(
                '${b['scraper']}: ${b['current']} products (avg ${b['rolling_avg']}, -${b['drop_pct']}%)',
                style: const TextStyle(fontSize: 12, color: Colors.red),
              )),
        ],
      ),
    );
  }
}

class _ScraperRow extends StatelessWidget {
  final String name;
  final int count;
  final bool isBroken;
  const _ScraperRow(
      {required this.name, required this.count, required this.isBroken});

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 4),
      child: Row(children: [
        Icon(
          isBroken ? Icons.error_rounded : Icons.check_circle_rounded,
          size: 16,
          color: isBroken ? Colors.red : Colors.green,
        ),
        const SizedBox(width: 8),
        Expanded(
          child: Text(name,
              style: const TextStyle(fontFamily: 'monospace', fontSize: 13)),
        ),
        Text('$count products',
            style: TextStyle(
                fontSize: 12,
                color: isBroken ? Colors.red : Colors.grey.shade600)),
      ]),
    );
  }
}

class _ActionCard extends StatelessWidget {
  final IconData icon;
  final String label;
  final Color color;
  final VoidCallback onTap;
  const _ActionCard(
      {required this.icon,
      required this.label,
      required this.color,
      required this.onTap});

  @override
  Widget build(BuildContext context) {
    return Card(
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(16),
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Icon(icon, color: color, size: 32),
              const SizedBox(height: 8),
              Text(label,
                  style: TextStyle(
                      fontWeight: FontWeight.w600, color: color)),
            ],
          ),
        ),
      ),
    );
  }
}

class _KpiRowSkeleton extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return Column(children: [
      Row(children: [
        Expanded(child: _SkeletonCard()),
        const SizedBox(width: 12),
        Expanded(child: _SkeletonCard()),
      ]),
      const SizedBox(height: 12),
      Row(children: [
        Expanded(child: _SkeletonCard()),
        const SizedBox(width: 12),
        Expanded(child: _SkeletonCard()),
      ]),
    ]);
  }
}

class _SkeletonCard extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return Card(
      child: Container(height: 72, color: Colors.grey.shade100),
    );
  }
}

class _LoadingCard extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return const Card(
      child: Padding(
        padding: EdgeInsets.all(24),
        child: Center(child: CircularProgressIndicator()),
      ),
    );
  }
}

class _InfoCard extends StatelessWidget {
  final String message;
  const _InfoCard(this.message);

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Text(message, style: const TextStyle(color: Colors.grey)),
      ),
    );
  }
}

class _ErrorTile extends StatelessWidget {
  final String message;
  const _ErrorTile(this.message);

  @override
  Widget build(BuildContext context) {
    return Card(
      color: Colors.red.shade50,
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Row(children: [
          const Icon(Icons.error_outline, color: Colors.red, size: 18),
          const SizedBox(width: 8),
          Expanded(
              child: Text(message,
                  style: const TextStyle(color: Colors.red, fontSize: 12))),
        ]),
      ),
    );
  }
}
