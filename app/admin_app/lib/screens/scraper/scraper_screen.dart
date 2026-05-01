import 'package:cloud_firestore/cloud_firestore.dart';
import 'package:fl_chart/fl_chart.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:intl/intl.dart';
import '../../providers/admin_providers.dart';

// ─── Source display config ────────────────────────────────────────────────────

const _sourceLabels = {
  'amazon_eg': 'Amazon EG',
  'amazon_ae': 'Amazon AE',
  'amazon_sa': 'Amazon SA',
  'noon_eg':   'Noon EG',
  'noon_ae':   'Noon AE',
  'noon_sa':   'Noon SA',
  'jumia_eg':  'Jumia EG',
  'hyperone':  'HyperOne',
  'btech':     'B.Tech',
  'carrefour': 'Carrefour',
  'sharafdg':  'Sharaf DG',
  'sahla':     'Sahla',
};

const _sourceColors = {
  'amazon_eg': Color(0xFFFF9900),
  'amazon_ae': Color(0xFFFF9900),
  'amazon_sa': Color(0xFFFF9900),
  'noon_eg':   Color(0xFFCCBB00),
  'noon_ae':   Color(0xFFCCBB00),
  'noon_sa':   Color(0xFFCCBB00),
  'jumia_eg':  Color(0xFFEF6C00),
  'hyperone':  Color(0xFF1565C0),
  'btech':     Color(0xFF2E7D32),
  'carrefour': Color(0xFF0D47A1),
  'sharafdg':  Color(0xFF6A1B9A),
  'sahla':     Color(0xFFAD1457),
};

// ─── Screen ───────────────────────────────────────────────────────────────────

class ScraperScreen extends ConsumerWidget {
  const ScraperScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final latestAsync  = ref.watch(scraperHealthProvider);
    final historyAsync = ref.watch(scraperHistoryProvider);

    return Scaffold(
      appBar: AppBar(
        title: const Text('Scraper Monitor'),
        actions: [
          IconButton(
            icon: const Icon(Icons.refresh),
            onPressed: () {
              ref.invalidate(scraperHealthProvider);
              ref.invalidate(scraperHistoryProvider);
            },
          ),
        ],
      ),
      body: RefreshIndicator(
        onRefresh: () async {
          ref.invalidate(scraperHealthProvider);
          ref.invalidate(scraperHistoryProvider);
        },
        child: SingleChildScrollView(
          physics: const AlwaysScrollableScrollPhysics(),
          padding: const EdgeInsets.all(16),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [

              // ── Latest cycle summary ─────────────────────────────────────
              latestAsync.when(
                loading: () => const _LoadingCard(),
                error:   (e, _) => _ErrorCard('$e'),
                data:    (health) => _LatestCycleCard(health: health),
              ),

              const SizedBox(height: 20),

              // ── Per-source breakdown ─────────────────────────────────────
              _SectionHeader('Per-Source Breakdown'),
              const SizedBox(height: 10),

              latestAsync.when(
                loading: () => const _LoadingCard(),
                error:   (e, _) => _ErrorCard('$e'),
                data:    (health) => _SourceGrid(health: health),
              ),

              const SizedBox(height: 20),

              // ── History chart ────────────────────────────────────────────
              _SectionHeader('Deal Count History (last 8 cycles)'),
              const SizedBox(height: 10),

              historyAsync.when(
                loading: () => const _LoadingCard(),
                error:   (e, _) => _ErrorCard('$e'),
                data:    (history) => _HistorySection(history: history),
              ),

              const SizedBox(height: 32),
            ],
          ),
        ),
      ),
    );
  }
}

// ─── Latest cycle summary card ────────────────────────────────────────────────

class _LatestCycleCard extends StatelessWidget {
  final Map<String, dynamic> health;
  const _LatestCycleCard({required this.health});

  @override
  Widget build(BuildContext context) {
    if (health.isEmpty) {
      return const Card(
        child: Padding(
          padding: EdgeInsets.all(16),
          child: Text('No scraper cycle recorded yet.',
              style: TextStyle(color: Colors.grey)),
        ),
      );
    }

    final ts       = health['timestamp'];
    final cycle    = health['cycle']    as Map? ?? {};
    final broken   = (health['broken_scrapers'] as List?)?.cast<Map>() ?? [];
    final hasAlert = health['has_alerts'] as bool? ?? false;

    final total = cycle.values.fold<int>(0, (sum, v) => sum + ((v as num?)?.toInt() ?? 0));

    final statusColor = hasAlert ? Colors.orange : Colors.green;
    final statusIcon  = hasAlert ? Icons.warning_amber_rounded : Icons.check_circle_rounded;
    final statusText  = hasAlert
        ? '${broken.length} scraper${broken.length > 1 ? 's' : ''} need attention'
        : 'All scrapers healthy';

    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(children: [
              Icon(statusIcon, color: statusColor, size: 22),
              const SizedBox(width: 8),
              Text(statusText,
                  style: TextStyle(
                      fontWeight: FontWeight.bold,
                      color: statusColor,
                      fontSize: 15)),
              const Spacer(),
              Text(_formatTs(ts),
                  style: const TextStyle(fontSize: 12, color: Colors.grey)),
            ]),

            const SizedBox(height: 12),

            Row(children: [
              _StatPill(label: 'Total deals', value: '$total', color: Colors.blue),
              const SizedBox(width: 10),
              _StatPill(label: 'Sources', value: '${cycle.length}', color: Colors.teal),
              const SizedBox(width: 10),
              _StatPill(label: 'Alerts', value: '${broken.length}',
                  color: broken.isEmpty ? Colors.grey : Colors.orange),
            ]),

            if (broken.isNotEmpty) ...[
              const SizedBox(height: 12),
              const Divider(height: 1),
              const SizedBox(height: 10),
              Text('Needs attention:', style: TextStyle(
                  fontSize: 12, color: Colors.orange.shade800,
                  fontWeight: FontWeight.w600)),
              const SizedBox(height: 6),
              ...broken.map((b) => _BrokenRow(broken: b)),
            ],
          ],
        ),
      ),
    );
  }

  String _formatTs(dynamic ts) {
    try {
      DateTime dt;
      if (ts is Timestamp) dt = ts.toDate().toLocal();
      else if (ts is String) dt = DateTime.parse(ts).toLocal();
      else return 'Unknown';
      return DateFormat('MMM d, HH:mm').format(dt);
    } catch (_) { return '—'; }
  }
}

// ─── Per-source grid ──────────────────────────────────────────────────────────

class _SourceGrid extends StatelessWidget {
  final Map<String, dynamic> health;
  const _SourceGrid({required this.health});

  @override
  Widget build(BuildContext context) {
    final cycle  = health['cycle']    as Map? ?? {};
    final broken = (health['broken_scrapers'] as List?)?.cast<Map>() ?? [];
    final brokenNames = broken.map((b) => b['scraper'] as String? ?? '').toSet();

    if (cycle.isEmpty) {
      return const Padding(
        padding: EdgeInsets.all(12),
        child: Text('No data', style: TextStyle(color: Colors.grey)),
      );
    }

    final sortedEntries = cycle.entries.toList()
      ..sort((a, b) => ((b.value as num?) ?? 0).compareTo((a.value as num?) ?? 0));

    return GridView.builder(
      shrinkWrap: true,
      physics: const NeverScrollableScrollPhysics(),
      gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
        crossAxisCount: 2,
        mainAxisSpacing: 8,
        crossAxisSpacing: 8,
        childAspectRatio: 2.4,
      ),
      itemCount: sortedEntries.length,
      itemBuilder: (_, i) {
        final entry = sortedEntries[i];
        final name  = entry.key;
        final count = (entry.value as num?)?.toInt() ?? 0;
        final isBroken = brokenNames.contains(name);

        final brokenData = isBroken
            ? broken.firstWhere((b) => b['scraper'] == name, orElse: () => {})
            : null;

        return _SourceCard(
          name:       name,
          count:      count,
          isBroken:   isBroken,
          brokenData: brokenData,
        );
      },
    );
  }
}

class _SourceCard extends StatelessWidget {
  final String name;
  final int    count;
  final bool   isBroken;
  final Map?   brokenData;

  const _SourceCard({
    required this.name,
    required this.count,
    required this.isBroken,
    this.brokenData,
  });

  @override
  Widget build(BuildContext context) {
    final label = _sourceLabels[name] ?? name;
    final color = _sourceColors[name] ?? Colors.grey;
    final borderColor = isBroken ? Colors.orange : color.withOpacity(0.3);

    return Container(
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: borderColor, width: isBroken ? 2 : 1),
        color: isBroken
            ? Colors.orange.shade50
            : color.withOpacity(0.06),
      ),
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
      child: Row(children: [
        Container(
          width: 36, height: 36,
          decoration: BoxDecoration(
            color: color.withOpacity(0.15),
            borderRadius: BorderRadius.circular(8),
          ),
          child: Center(
            child: isBroken
                ? const Icon(Icons.warning_amber_rounded, color: Colors.orange, size: 20)
                : Icon(Icons.store_rounded, color: color, size: 20),
          ),
        ),
        const SizedBox(width: 10),
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Text(label, style: const TextStyle(
                  fontSize: 12, fontWeight: FontWeight.w600),
                  maxLines: 1, overflow: TextOverflow.ellipsis),
              const SizedBox(height: 2),
              Row(children: [
                Text('$count deals',
                    style: TextStyle(
                        fontSize: 13,
                        fontWeight: FontWeight.bold,
                        color: count == 0 ? Colors.red.shade400 : Colors.black87)),
                if (isBroken && brokenData != null) ...[
                  const SizedBox(width: 4),
                  Text('-${brokenData!['drop_pct']?.toStringAsFixed(0) ?? '?'}%',
                      style: const TextStyle(fontSize: 11, color: Colors.orange)),
                ],
              ]),
            ],
          ),
        ),
      ]),
    );
  }
}

// ─── History section ──────────────────────────────────────────────────────────

class _HistorySection extends StatefulWidget {
  final List<Map<String, dynamic>> history;
  const _HistorySection({required this.history});

  @override
  State<_HistorySection> createState() => _HistorySectionState();
}

class _HistorySectionState extends State<_HistorySection> {
  String? _highlightSource;

  @override
  Widget build(BuildContext context) {
    if (widget.history.isEmpty) {
      return const Card(
        child: Padding(
          padding: EdgeInsets.all(16),
          child: Text('No history yet — runs every 60 minutes.',
              style: TextStyle(color: Colors.grey)),
        ),
      );
    }

    // Collect all source names across all cycles
    final allSources = <String>{};
    for (final h in widget.history) {
      final cycle = h['cycle'] as Map? ?? {};
      allSources.addAll(cycle.keys.cast<String>());
    }

    // Sort history oldest → newest for chart
    final sorted = List<Map<String, dynamic>>.from(widget.history.reversed);

    return Column(
      children: [
        // Source selector
        SizedBox(
          height: 32,
          child: ListView(
            scrollDirection: Axis.horizontal,
            children: [
              _HistoryChip(
                label: 'Total',
                selected: _highlightSource == null,
                color: Colors.blue,
                onTap: () => setState(() => _highlightSource = null),
              ),
              const SizedBox(width: 6),
              ...allSources.map((s) => Padding(
                padding: const EdgeInsets.only(right: 6),
                child: _HistoryChip(
                  label: _sourceLabels[s] ?? s,
                  selected: _highlightSource == s,
                  color: _sourceColors[s] ?? Colors.grey,
                  onTap: () => setState(() =>
                      _highlightSource = _highlightSource == s ? null : s),
                ),
              )),
            ],
          ),
        ),

        const SizedBox(height: 12),

        // Bar chart
        Card(
          child: Padding(
            padding: const EdgeInsets.fromLTRB(12, 16, 12, 8),
            child: SizedBox(
              height: 180,
              child: _buildBarChart(sorted),
            ),
          ),
        ),

        const SizedBox(height: 12),

        // History list (newest first)
        ...widget.history.take(8).map((h) => _CycleTile(cycle: h)),
      ],
    );
  }

  Widget _buildBarChart(List<Map<String, dynamic>> sorted) {
    final barGroups = <BarChartGroupData>[];

    for (int i = 0; i < sorted.length; i++) {
      final cycle = sorted[i]['cycle'] as Map? ?? {};
      int value;

      if (_highlightSource == null) {
        value = cycle.values.fold<int>(0, (s, v) => s + ((v as num?)?.toInt() ?? 0));
      } else {
        value = (cycle[_highlightSource] as num?)?.toInt() ?? 0;
      }

      barGroups.add(BarChartGroupData(
        x: i,
        barRods: [
          BarChartRodData(
            toY: value.toDouble(),
            color: _highlightSource != null
                ? (_sourceColors[_highlightSource] ?? Colors.blue)
                : Colors.blue.shade400,
            width: 18,
            borderRadius: const BorderRadius.vertical(top: Radius.circular(4)),
          ),
        ],
      ));
    }

    return BarChart(BarChartData(
      barGroups: barGroups,
      gridData: const FlGridData(show: false),
      borderData: FlBorderData(show: false),
      titlesData: FlTitlesData(
        leftTitles: const AxisTitles(sideTitles: SideTitles(showTitles: false)),
        topTitles:  const AxisTitles(sideTitles: SideTitles(showTitles: false)),
        rightTitles: AxisTitles(
          sideTitles: SideTitles(
            showTitles: true,
            reservedSize: 36,
            getTitlesWidget: (v, _) => Text(
              '${v.toInt()}',
              style: const TextStyle(fontSize: 10, color: Colors.grey),
            ),
          ),
        ),
        bottomTitles: AxisTitles(
          sideTitles: SideTitles(
            showTitles: true,
            getTitlesWidget: (v, _) {
              final idx = v.toInt();
              if (idx < 0 || idx >= sorted.length) return const SizedBox();
              final ts = sorted[idx]['timestamp'];
              return Text(_shortTs(ts),
                  style: const TextStyle(fontSize: 9, color: Colors.grey));
            },
          ),
        ),
      ),
    ));
  }

  String _shortTs(dynamic ts) {
    try {
      DateTime dt;
      if (ts is Timestamp) dt = ts.toDate().toLocal();
      else if (ts is String) dt = DateTime.parse(ts).toLocal();
      else return '';
      return DateFormat('d/M\nHH:mm').format(dt);
    } catch (_) { return ''; }
  }
}

// ─── Cycle history tile ───────────────────────────────────────────────────────

class _CycleTile extends StatelessWidget {
  final Map<String, dynamic> cycle;
  const _CycleTile({required this.cycle});

  @override
  Widget build(BuildContext context) {
    final ts      = cycle['timestamp'];
    final data    = cycle['cycle']    as Map? ?? {};
    final broken  = (cycle['broken_scrapers'] as List?)?.cast<Map>() ?? [];
    final total   = data.values.fold<int>(0, (s, v) => s + ((v as num?)?.toInt() ?? 0));
    final hasAlert = cycle['has_alerts'] as bool? ?? false;

    return Card(
      margin: const EdgeInsets.only(bottom: 6),
      child: ListTile(
        dense: true,
        leading: Icon(
          hasAlert ? Icons.warning_amber_rounded : Icons.check_circle_outline,
          color: hasAlert ? Colors.orange : Colors.green,
          size: 22,
        ),
        title: Text(_formatTs(ts),
            style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w500)),
        subtitle: Text(
          data.entries
            .map((e) => '${_sourceLabels[e.key] ?? e.key}: ${e.value}')
            .join('  •  '),
          style: const TextStyle(fontSize: 11),
          maxLines: 2,
          overflow: TextOverflow.ellipsis,
        ),
        trailing: Text('$total total',
            style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 13)),
      ),
    );
  }

  String _formatTs(dynamic ts) {
    try {
      DateTime dt;
      if (ts is Timestamp) dt = ts.toDate().toLocal();
      else if (ts is String) dt = DateTime.parse(ts).toLocal();
      else return '—';
      return DateFormat('MMM d, HH:mm').format(dt);
    } catch (_) { return '—'; }
  }
}

// ─── Small reusable widgets ───────────────────────────────────────────────────

class _BrokenRow extends StatelessWidget {
  final Map broken;
  const _BrokenRow({required this.broken});

  @override
  Widget build(BuildContext context) {
    final name    = broken['scraper']     as String? ?? '?';
    final current = broken['current']     as num?    ?? 0;
    final avg     = broken['rolling_avg'] as num?    ?? 0;
    final drop    = broken['drop_pct']    as num?    ?? 0;
    final label   = _sourceLabels[name]   ?? name;

    return Padding(
      padding: const EdgeInsets.only(bottom: 4),
      child: Row(children: [
        const Icon(Icons.arrow_right, size: 16, color: Colors.orange),
        const SizedBox(width: 4),
        Text(label, style: const TextStyle(fontSize: 12, fontWeight: FontWeight.w600)),
        const SizedBox(width: 6),
        Text('$current deals (avg ${avg.toStringAsFixed(0)}, -${drop.toStringAsFixed(0)}%)',
            style: const TextStyle(fontSize: 12, color: Colors.grey)),
      ]),
    );
  }
}

class _StatPill extends StatelessWidget {
  final String label;
  final String value;
  final Color  color;
  const _StatPill({required this.label, required this.value, required this.color});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
      decoration: BoxDecoration(
        color: color.withOpacity(0.1),
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: color.withOpacity(0.3)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(value,
              style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold, color: color)),
          Text(label, style: const TextStyle(fontSize: 10, color: Colors.grey)),
        ],
      ),
    );
  }
}

class _HistoryChip extends StatelessWidget {
  final String   label;
  final bool     selected;
  final Color    color;
  final VoidCallback onTap;
  const _HistoryChip({
    required this.label, required this.selected,
    required this.color, required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onTap,
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
        decoration: BoxDecoration(
          color: selected ? color.withOpacity(0.15) : Colors.transparent,
          borderRadius: BorderRadius.circular(20),
          border: Border.all(color: selected ? color : Colors.grey.shade300),
        ),
        child: Text(label,
            style: TextStyle(
                fontSize: 11,
                color: selected ? color : Colors.grey,
                fontWeight: selected ? FontWeight.w600 : FontWeight.normal)),
      ),
    );
  }
}

class _SectionHeader extends StatelessWidget {
  final String text;
  const _SectionHeader(this.text);

  @override
  Widget build(BuildContext context) {
    return Text(text,
        style: const TextStyle(fontSize: 14, fontWeight: FontWeight.bold, color: Colors.black87));
  }
}

class _LoadingCard extends StatelessWidget {
  const _LoadingCard();

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

class _ErrorCard extends StatelessWidget {
  final String message;
  const _ErrorCard(this.message);

  @override
  Widget build(BuildContext context) {
    return Card(
      color: Colors.red.shade50,
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Row(children: [
          const Icon(Icons.error_outline, color: Colors.red, size: 18),
          const SizedBox(width: 8),
          Expanded(child: Text(message,
              style: const TextStyle(color: Colors.red, fontSize: 12))),
        ]),
      ),
    );
  }
}
