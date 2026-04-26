import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../models/user_model.dart';
import '../../providers/app_providers.dart';

// Tap Payments AED pricing (matches server-side TIER_PRICES_AED)
const _prices = {
  'basic': {'monthly': 14.99, '6months': 80.94, 'yearly': 134.91},
  'premium': {'monthly': 29.99, '6months': 161.94, 'yearly': 269.91},
  'vip': {'monthly': 59.99, '6months': 323.94, 'yearly': 539.91},
};

const _features = {
  'basic': [
    'Category filter',
    '60-day price history',
    'Save up to 50 deals',
    'Basic support',
  ],
  'premium': [
    'Product search',
    '180-day price history',
    'Unlimited saved deals',
    'Priority support',
    'All Basic features',
  ],
  'vip': [
    'Lifetime price history',
    'Early deal alerts',
    'Dedicated support',
    'All Premium features',
  ],
};

class MembershipScreen extends ConsumerStatefulWidget {
  const MembershipScreen({super.key});

  @override
  ConsumerState<MembershipScreen> createState() => _MembershipScreenState();
}

class _MembershipScreenState extends ConsumerState<MembershipScreen> {
  String _cycle = 'monthly';

  @override
  Widget build(BuildContext context) {
    final user = ref.watch(currentUserProvider).valueOrNull;
    final membership = user?.membership ?? const MembershipInfo();
    final cs = Theme.of(context).colorScheme;

    return Scaffold(
      appBar: AppBar(title: const Text('Membership')),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          // Current plan
          _CurrentPlanCard(membership: membership),
          const SizedBox(height: 20),

          // Billing cycle picker
          Center(
            child: SegmentedButton<String>(
              segments: const [
                ButtonSegment(value: 'monthly', label: Text('Monthly')),
                ButtonSegment(value: '6months', label: Text('6 Months')),
                ButtonSegment(value: 'yearly', label: Text('Yearly')),
              ],
              selected: {_cycle},
              onSelectionChanged: (s) => setState(() => _cycle = s.first),
            ),
          ),
          if (_cycle == '6months')
            Padding(
              padding: const EdgeInsets.only(top: 6),
              child: Text(
                'Save 10% vs monthly',
                textAlign: TextAlign.center,
                style:
                    TextStyle(color: Colors.green.shade700, fontSize: 12),
              ),
            ),
          if (_cycle == 'yearly')
            Padding(
              padding: const EdgeInsets.only(top: 6),
              child: Text(
                'Save 25% vs monthly',
                textAlign: TextAlign.center,
                style:
                    TextStyle(color: Colors.green.shade700, fontSize: 12),
              ),
            ),
          const SizedBox(height: 16),

          // Plan cards
          for (final tier in ['basic', 'premium', 'vip']) ...[
            _PlanCard(
              tier: tier,
              cycle: _cycle,
              currentTier: membership.tier,
              userId: user?.uid ?? '',
            ),
            const SizedBox(height: 12),
          ],

          // Free features summary
          const SizedBox(height: 8),
          Card(
            color: cs.surfaceContainerLowest,
            child: Padding(
              padding: const EdgeInsets.all(16),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Text('Free Plan includes:',
                      style: TextStyle(fontWeight: FontWeight.w500)),
                  const SizedBox(height: 8),
                  for (final f in [
                    'Browse all deals',
                    '30-day price history',
                    'Save up to 10 deals',
                    'Basic fraud detection',
                  ])
                    Padding(
                      padding: const EdgeInsets.symmetric(vertical: 2),
                      child: Row(
                        children: [
                          Icon(Icons.check_circle_outline,
                              size: 16, color: cs.onSurfaceVariant),
                          const SizedBox(width: 8),
                          Text(f,
                              style: TextStyle(
                                  color: cs.onSurfaceVariant,
                                  fontSize: 13)),
                        ],
                      ),
                    ),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }
}

// ─── Current plan ──────────────────────────────────────────────────────────

class _CurrentPlanCard extends StatelessWidget {
  const _CurrentPlanCard({required this.membership});

  final MembershipInfo membership;

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    final color = switch (membership.tier) {
      'vip' => Colors.amber,
      'premium' => cs.primary,
      'basic' => Colors.teal,
      _ => cs.onSurfaceVariant,
    };
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Row(
          children: [
            Icon(Icons.diamond_rounded, color: color, size: 36),
            const SizedBox(width: 12),
            Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text('Current Plan',
                    style: TextStyle(
                        color: cs.onSurfaceVariant, fontSize: 12)),
                Text(
                  membership.displayLabel,
                  style: TextStyle(
                    fontSize: 22,
                    fontWeight: FontWeight.bold,
                    color: color,
                  ),
                ),
              ],
            ),
            const Spacer(),
            if (membership.activatedAt != null)
              Text(
                'Active since\n'
                '${membership.activatedAt!.day}/${membership.activatedAt!.month}/${membership.activatedAt!.year}',
                textAlign: TextAlign.right,
                style: TextStyle(
                    fontSize: 11, color: cs.onSurfaceVariant),
              ),
          ],
        ),
      ),
    );
  }
}

// ─── Plan card ─────────────────────────────────────────────────────────────

class _PlanCard extends StatelessWidget {
  const _PlanCard({
    required this.tier,
    required this.cycle,
    required this.currentTier,
    required this.userId,
  });

  final String tier;
  final String cycle;
  final String currentTier;
  final String userId;

  bool get _isCurrent => tier == currentTier;
  bool get _isUpgrade => _tierRank(tier) > _tierRank(currentTier);

  static int _tierRank(String t) =>
      const {'free': 0, 'basic': 1, 'premium': 2, 'vip': 3}[t] ?? 0;

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    final color = switch (tier) {
      'vip' => Colors.amber,
      'premium' => cs.primary,
      _ => Colors.teal,
    };
    final price = (_prices[tier]?[cycle] ?? 0.0) as double;
    final label = tier[0].toUpperCase() + tier.substring(1);
    final features = _features[tier] ?? [];

    return Card(
      elevation: tier == 'premium' ? 4 : 1,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(12),
        side: tier == 'premium'
            ? BorderSide(color: cs.primary, width: 2)
            : BorderSide.none,
      ),
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Icon(Icons.diamond_rounded, color: color, size: 20),
                const SizedBox(width: 8),
                Text(label,
                    style: TextStyle(
                        fontWeight: FontWeight.bold,
                        fontSize: 16,
                        color: color)),
                if (tier == 'premium') ...[
                  const SizedBox(width: 8),
                  Container(
                    padding: const EdgeInsets.symmetric(
                        horizontal: 6, vertical: 2),
                    decoration: BoxDecoration(
                      color: cs.primary,
                      borderRadius: BorderRadius.circular(4),
                    ),
                    child: const Text('Popular',
                        style: TextStyle(
                            color: Colors.white, fontSize: 10)),
                  ),
                ],
              ],
            ),
            const SizedBox(height: 8),
            Row(
              crossAxisAlignment: CrossAxisAlignment.end,
              children: [
                Text(
                  'AED ${price.toStringAsFixed(2)}',
                  style: const TextStyle(
                      fontSize: 22, fontWeight: FontWeight.bold),
                ),
                const SizedBox(width: 4),
                Padding(
                  padding: const EdgeInsets.only(bottom: 3),
                  child: Text(
                    cycle == 'monthly'
                        ? '/month'
                        : cycle == '6months'
                            ? '/6 months'
                            : '/year',
                    style: TextStyle(
                        color: cs.onSurfaceVariant, fontSize: 12),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 12),
            for (final f in features)
              Padding(
                padding: const EdgeInsets.symmetric(vertical: 3),
                child: Row(
                  children: [
                    Icon(Icons.check_rounded, size: 16, color: color),
                    const SizedBox(width: 8),
                    Text(f, style: const TextStyle(fontSize: 13)),
                  ],
                ),
              ),
            const SizedBox(height: 12),
            SizedBox(
              width: double.infinity,
              child: _isCurrent
                  ? OutlinedButton(
                      onPressed: null,
                      child: const Text('Current Plan'),
                    )
                  : _isUpgrade
                      ? FilledButton(
                          onPressed: () =>
                              _showUpgradeSheet(context, tier, price),
                          style: FilledButton.styleFrom(
                              backgroundColor: color),
                          child: Text('Upgrade to $label'),
                        )
                      : OutlinedButton(
                          onPressed: null,
                          child: const Text('Downgrade'),
                        ),
            ),
          ],
        ),
      ),
    );
  }

  void _showUpgradeSheet(
      BuildContext context, String tier, double price) {
    showModalBottomSheet(
      context: context,
      builder: (_) => SafeArea(
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Text(
                'Upgrade to ${tier[0].toUpperCase()}${tier.substring(1)}',
                style: const TextStyle(
                    fontSize: 18, fontWeight: FontWeight.bold),
              ),
              const SizedBox(height: 8),
              Text('AED ${price.toStringAsFixed(2)} / $cycle'),
              const SizedBox(height: 20),
              const Text(
                'Payment via Tap Payments.\nYou will be redirected to complete the payment.',
                textAlign: TextAlign.center,
              ),
              const SizedBox(height: 20),
              FilledButton(
                onPressed: () => Navigator.pop(context),
                child: const Text('Proceed to Payment'),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
