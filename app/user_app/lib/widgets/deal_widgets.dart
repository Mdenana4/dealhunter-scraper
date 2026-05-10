import 'package:flutter/material.dart';

class DiscountBadge extends StatelessWidget {
  const DiscountBadge({super.key, required this.percent});

  final int percent;

  @override
  Widget build(BuildContext context) {
    if (percent <= 0) return const SizedBox.shrink();
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
      decoration: BoxDecoration(
        color: Colors.red.shade600,
        borderRadius: BorderRadius.circular(4),
      ),
      child: Text(
        '-$percent%',
        style: const TextStyle(color: Colors.white, fontSize: 11),
      ),
    );
  }
}

class VerdictDot extends StatelessWidget {
  const VerdictDot({super.key, required this.verdict});

  final String verdict;

  @override
  Widget build(BuildContext context) {
    final color = switch (verdict) {
      'GENUINE' => Colors.green,
      'FAKE' => Colors.red,
      _ => Colors.orange,
    };
    final label = switch (verdict) {
      'GENUINE' => 'Genuine',
      'FAKE' => 'Fake',
      _ => 'Unverified',
    };
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        Container(
          width: 8,
          height: 8,
          decoration: BoxDecoration(color: color, shape: BoxShape.circle),
        ),
        const SizedBox(width: 4),
        Text(label, style: TextStyle(fontSize: 11, color: color)),
      ],
    );
  }
}

/// v10.0: Score-based recommendation badge
/// Displays: buy_now ✅ / good_deal / research_first 🔍 / wait ⏸️ / avoid ❌
class RecommendationBadge extends StatelessWidget {
  const RecommendationBadge({super.key, required this.recommendation});

  final String recommendation;

  @override
  Widget build(BuildContext context) {
    final (bgColor, textColor, label, icon) = switch (recommendation) {
      'buy_now' => (Colors.green.shade100, Colors.green.shade800, 'Buy Now', '✅'),
      'good_deal' => (Colors.teal.shade100, Colors.teal.shade800, 'Good Deal', '👍'),
      'research_first' => (Colors.amber.shade100, Colors.amber.shade800, 'Research', '🔍'),
      'wait' => (Colors.orange.shade100, Colors.orange.shade800, 'Wait', '⏸️'),
      'avoid' => (Colors.red.shade100, Colors.red.shade800, 'Avoid', '❌'),
      _ => (Colors.grey.shade200, Colors.grey.shade700, 'Check', '❓'),
    };

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
      decoration: BoxDecoration(
        color: bgColor,
        borderRadius: BorderRadius.circular(6),
        border: Border.all(color: textColor.withOpacity(0.3)),
      ),
      child: Text(
        label,
        style: TextStyle(
          fontSize: 11,
          fontWeight: FontWeight.w600,
          color: textColor,
        ),
      ),
    );
  }
}
