import 'package:flutter/material.dart';
import 'package:fl_chart/fl_chart.dart';
import '../models/price_point.dart';
import '../config/theme.dart';

class PriceHistoryChart extends StatefulWidget {
  final PriceHistory history;
  final double? lowestEver;

  const PriceHistoryChart({
    super.key,
    required this.history,
    this.lowestEver,
  });

  @override
  State<PriceHistoryChart> createState() => _PriceHistoryChartState();
}

class _PriceHistoryChartState extends State<PriceHistoryChart> {
  int? _touchedIndex;

  @override
  Widget build(BuildContext context) {
    if (widget.history.isEmpty) {
      return const SizedBox(
        height: 180,
        child: Center(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Icon(Icons.bar_chart, size: 48, color: Colors.grey),
              SizedBox(height: 8),
              Text('Price history not yet available',
                  style: TextStyle(color: Colors.grey)),
            ],
          ),
        ),
      );
    }

    final points = widget.history.points;
    final prices = points.map((p) => p.price).toList();
    final minY = (prices.reduce((a, b) => a < b ? a : b) * 0.95);
    final maxY = (prices.reduce((a, b) => a > b ? a : b) * 1.05);
    final spots = points.asMap().entries
        .map((e) => FlSpot(e.key.toDouble(), e.value.price))
        .toList();

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        // Stats row
        _StatsRow(history: widget.history),
        const SizedBox(height: 16),

        // Chart
        SizedBox(
          height: 200,
          child: LineChart(
            LineChartData(
              minY: minY,
              maxY: maxY,
              clipData: const FlClipData.all(),
              gridData: FlGridData(
                show: true,
                drawVerticalLine: false,
                getDrawingHorizontalLine: (_) => FlLine(
                  color: Colors.grey.withOpacity(0.15),
                  strokeWidth: 1,
                ),
              ),
              borderData: FlBorderData(show: false),
              titlesData: FlTitlesData(
                leftTitles: AxisTitles(
                  sideTitles: SideTitles(
                    showTitles: true,
                    reservedSize: 54,
                    getTitlesWidget: (value, _) => Text(
                      '${widget.history.currency} ${value.toStringAsFixed(0)}',
                      style: const TextStyle(fontSize: 10, color: Colors.grey),
                    ),
                  ),
                ),
                bottomTitles: AxisTitles(
                  sideTitles: SideTitles(
                    showTitles: true,
                    reservedSize: 28,
                    interval: (points.length / 4).ceilToDouble(),
                    getTitlesWidget: (value, _) {
                      final idx = value.toInt();
                      if (idx < 0 || idx >= points.length) return const SizedBox();
                      final dt = points[idx].timestamp;
                      return Text(
                        '${dt.day}/${dt.month}',
                        style: const TextStyle(fontSize: 10, color: Colors.grey),
                      );
                    },
                  ),
                ),
                rightTitles: const AxisTitles(
                    sideTitles: SideTitles(showTitles: false)),
                topTitles: const AxisTitles(
                    sideTitles: SideTitles(showTitles: false)),
              ),
              lineTouchData: LineTouchData(
                touchCallback: (event, response) {
                  setState(() {
                    _touchedIndex = response?.lineBarSpots?.first.spotIndex;
                  });
                },
                touchTooltipData: LineTouchTooltipData(
                  getTooltipColor: (_) => Colors.black87,
                  getTooltipItems: (spots) => spots.map((spot) {
                    final idx = spot.spotIndex;
                    final pt = points[idx];
                    final change = pt.changeAmount;
                    final changeStr = change != null && change != 0
                        ? (change > 0 ? ' ▲${change.toStringAsFixed(0)}' : ' ▼${change.abs().toStringAsFixed(0)}')
                        : '';
                    return LineTooltipItem(
                      '${widget.history.currency} ${pt.price.toStringAsFixed(0)}$changeStr\n${pt.timestamp.day}/${pt.timestamp.month}/${pt.timestamp.year}',
                      const TextStyle(color: Colors.white, fontSize: 12),
                    );
                  }).toList(),
                ),
              ),
              lineBarsData: [
                LineChartBarData(
                  spots: spots,
                  isCurved: true,
                  curveSmoothness: 0.25,
                  color: AppTheme.primary,
                  barWidth: 2.5,
                  dotData: FlDotData(
                    show: true,
                    getDotPainter: (spot, _, __, idx) {
                      final pt = points[idx];
                      Color dotColor;
                      if (pt.isPriceDecrease) dotColor = AppTheme.genuine;
                      else if (pt.isPriceIncrease) dotColor = AppTheme.fake;
                      else dotColor = AppTheme.primary;
                      return FlDotCirclePainter(
                        radius: idx == _touchedIndex ? 5 : 3,
                        color: dotColor,
                        strokeWidth: 0,
                      );
                    },
                  ),
                  belowBarData: BarAreaData(
                    show: true,
                    gradient: LinearGradient(
                      begin: Alignment.topCenter,
                      end: Alignment.bottomCenter,
                      colors: [
                        AppTheme.primary.withOpacity(0.25),
                        AppTheme.primary.withOpacity(0.01),
                      ],
                    ),
                  ),
                ),
              ],
              // Lowest ever price line
              extraLinesData: widget.lowestEver != null
                  ? ExtraLinesData(horizontalLines: [
                      HorizontalLine(
                        y: widget.lowestEver!,
                        color: AppTheme.genuine.withOpacity(0.6),
                        strokeWidth: 1.5,
                        dashArray: [6, 4],
                        label: HorizontalLineLabel(
                          show: true,
                          alignment: Alignment.topRight,
                          labelResolver: (_) => 'Lowest ever',
                          style: const TextStyle(
                              fontSize: 10, color: AppTheme.genuine),
                        ),
                      ),
                    ])
                  : null,
            ),
          ),
        ),

        const SizedBox(height: 12),

        // Legend
        Row(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            _LegendDot(color: AppTheme.genuine, label: 'Price drop'),
            const SizedBox(width: 16),
            _LegendDot(color: AppTheme.fake, label: 'Price rise'),
            const SizedBox(width: 16),
            _LegendDot(
                color: AppTheme.genuine.withOpacity(0.5),
                label: 'Lowest ever',
                dashed: true),
          ],
        ),
      ],
    );
  }
}

class _StatsRow extends StatelessWidget {
  final PriceHistory history;
  const _StatsRow({required this.history});

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        _StatChip(
          label: 'Current',
          value: '${history.currency} ${history.currentPrice?.toStringAsFixed(0) ?? "–"}',
          color: AppTheme.primary,
        ),
        const SizedBox(width: 8),
        _StatChip(
          label: 'Lowest',
          value: '${history.currency} ${history.lowestPrice?.toStringAsFixed(0) ?? "–"}',
          color: AppTheme.genuine,
        ),
        const SizedBox(width: 8),
        _StatChip(
          label: 'Average',
          value: '${history.currency} ${history.averagePrice?.toStringAsFixed(0) ?? "–"}',
          color: Colors.grey,
        ),
        const SizedBox(width: 8),
        _StatChip(
          label: 'Highest',
          value: '${history.currency} ${history.highestPrice?.toStringAsFixed(0) ?? "–"}',
          color: AppTheme.fake,
        ),
      ],
    );
  }
}

class _StatChip extends StatelessWidget {
  final String label;
  final String value;
  final Color color;
  const _StatChip({required this.label, required this.value, required this.color});

  @override
  Widget build(BuildContext context) {
    return Expanded(
      child: Container(
        padding: const EdgeInsets.symmetric(vertical: 8, horizontal: 4),
        decoration: BoxDecoration(
          color: color.withOpacity(0.08),
          borderRadius: BorderRadius.circular(10),
        ),
        child: Column(
          children: [
            Text(label,
                style: TextStyle(fontSize: 10, color: Colors.grey.shade600)),
            const SizedBox(height: 2),
            FittedBox(
              child: Text(value,
                  style: TextStyle(
                      fontSize: 12,
                      fontWeight: FontWeight.w700,
                      color: color)),
            ),
          ],
        ),
      ),
    );
  }
}

class _LegendDot extends StatelessWidget {
  final Color color;
  final String label;
  final bool dashed;
  const _LegendDot(
      {required this.color, required this.label, this.dashed = false});

  @override
  Widget build(BuildContext context) {
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        Container(width: 12, height: 12, decoration: BoxDecoration(color: color, shape: BoxShape.circle)),
        const SizedBox(width: 4),
        Text(label, style: const TextStyle(fontSize: 11, color: Colors.grey)),
      ],
    );
  }
}
