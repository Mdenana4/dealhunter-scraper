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
