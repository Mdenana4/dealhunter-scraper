import 'package:flutter/material.dart';
import '../models/deal.dart';
import '../config/theme.dart';

class VerificationBadge extends StatelessWidget {
  final VerificationSummary verification;
  final bool expanded;

  const VerificationBadge({
    super.key,
    required this.verification,
    this.expanded = false,
  });

  @override
  Widget build(BuildContext context) {
    final color = AppTheme.verificationColor(verification.verdict);
    final icon = verification.isGenuine
        ? Icons.verified_rounded
        : verification.isFake
            ? Icons.dangerous_rounded
            : Icons.help_rounded;
    final title = verification.isGenuine
        ? 'GENUINE DEAL'
        : verification.isFake
            ? 'FAKE DISCOUNT'
            : 'UNCERTAIN';
    final bgColor = color.withOpacity(0.1);

    if (!expanded) {
      return Container(
        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
        decoration: BoxDecoration(
          color: bgColor,
          borderRadius: BorderRadius.circular(20),
          border: Border.all(color: color.withOpacity(0.4)),
        ),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(icon, size: 14, color: color),
            const SizedBox(width: 4),
            Text(title,
                style: TextStyle(
                    fontSize: 11, fontWeight: FontWeight.w700, color: color)),
            const SizedBox(width: 6),
            Text('${verification.confidence}%',
                style: TextStyle(fontSize: 11, color: color)),
          ],
        ),
      );
    }

    // Expanded version — shown on deal detail screen
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: bgColor,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: color.withOpacity(0.3)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Header row
          Row(
            children: [
              Icon(icon, color: color, size: 28),
              const SizedBox(width: 10),
              Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(title,
                      style: TextStyle(
                          fontSize: 16,
                          fontWeight: FontWeight.w700,
                          color: color)),
                  Text('${verification.confidence}% confidence',
                      style: TextStyle(fontSize: 13, color: color)),
                ],
              ),
              const Spacer(),
              // Confidence arc
              _ConfidenceArc(
                  value: verification.confidence / 100, color: color),
            ],
          ),

          const SizedBox(height: 12),

          // Confidence bar
          ClipRRect(
            borderRadius: BorderRadius.circular(4),
            child: LinearProgressIndicator(
              value: verification.confidence / 100,
              backgroundColor: color.withOpacity(0.15),
              valueColor: AlwaysStoppedAnimation(color),
              minHeight: 8,
            ),
          ),

          const SizedBox(height: 12),

          // Explanation
          Text(verification.explanation,
              style: Theme.of(context)
                  .textTheme
                  .bodyMedium
                  ?.copyWith(height: 1.5)),

          // Red flags
          if (verification.redFlags.isNotEmpty) ...[
            const SizedBox(height: 12),
            Text('Issues detected:',
                style: Theme.of(context)
                    .textTheme
                    .labelLarge
                    ?.copyWith(color: AppTheme.fake)),
            const SizedBox(height: 6),
            ...verification.redFlags.map((flag) => Padding(
                  padding: const EdgeInsets.only(bottom: 4),
                  child: Row(
                    children: [
                      const Icon(Icons.warning_amber_rounded,
                          size: 14, color: AppTheme.fake),
                      const SizedBox(width: 6),
                      Expanded(
                        child: Text(flag,
                            style: const TextStyle(
                                fontSize: 13, color: AppTheme.fake)),
                      ),
                    ],
                  ),
                )),
          ],

          const SizedBox(height: 12),

          // Recommendation chip
          _RecommendationChip(recommendation: verification.recommendation),
        ],
      ),
    );
  }
}

class _ConfidenceArc extends StatelessWidget {
  final double value;
  final Color color;
  const _ConfidenceArc({required this.value, required this.color});

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      width: 52,
      height: 52,
      child: Stack(
        children: [
          CircularProgressIndicator(
            value: value,
            backgroundColor: color.withOpacity(0.15),
            valueColor: AlwaysStoppedAnimation(color),
            strokeWidth: 5,
          ),
          Center(
            child: Text(
              '${(value * 100).toInt()}%',
              style: TextStyle(
                  fontSize: 12,
                  fontWeight: FontWeight.w700,
                  color: color),
            ),
          ),
        ],
      ),
    );
  }
}

class _RecommendationChip extends StatelessWidget {
  final String recommendation;
  const _RecommendationChip({required this.recommendation});

  @override
  Widget build(BuildContext context) {
    final (icon, label, color) = switch (recommendation) {
      'buy_now' => (Icons.thumb_up_rounded, '✅ Buy Now — Great Deal!', AppTheme.genuine),
      'not_recommended' => (Icons.thumb_down_rounded, '⚠️ Not Recommended', AppTheme.fake),
      _ => (Icons.info_rounded, 'ℹ️ Check Price History', AppTheme.uncertain),
    };

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
      decoration: BoxDecoration(
        color: color.withOpacity(0.12),
        borderRadius: BorderRadius.circular(10),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon, color: color, size: 16),
          const SizedBox(width: 8),
          Text(label,
              style: TextStyle(
                  fontWeight: FontWeight.w600, color: color, fontSize: 13)),
        ],
      ),
    );
  }
}

// Compact loading state while verification runs
class VerificationLoading extends StatelessWidget {
  const VerificationLoading({super.key});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: Colors.grey.shade100,
        borderRadius: BorderRadius.circular(16),
      ),
      child: Row(
        children: [
          const SizedBox(
            width: 24, height: 24,
            child: CircularProgressIndicator(strokeWidth: 2.5),
          ),
          const SizedBox(width: 14),
          Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Text('Verifying deal authenticity...',
                  style: TextStyle(fontWeight: FontWeight.w600)),
              Text('Checking 90-day price history',
                  style: TextStyle(fontSize: 12, color: Colors.grey.shade600)),
            ],
          ),
        ],
      ),
    );
  }
}
