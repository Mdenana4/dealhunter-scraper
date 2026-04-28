import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../l10n/app_strings.dart';
import '../../models/user_model.dart';
import '../../providers/app_providers.dart';

// Prices per currency, per billing cycle
const _pricesEGP = {
  'basic':   {'monthly': 49.0,  '6months': 264.6,  'yearly': 441.0},
  'premium': {'monthly': 99.0,  '6months': 534.6,  'yearly': 891.0},
  'vip':     {'monthly': 199.0, '6months': 1074.6, 'yearly': 1791.0},
};

const _pricesAED = {
  'basic':   {'monthly': 14.99, '6months': 80.94,  'yearly': 134.91},
  'premium': {'monthly': 29.99, '6months': 161.94, 'yearly': 269.91},
  'vip':     {'monthly': 59.99, '6months': 323.94, 'yearly': 539.91},
};

const _pricesSAR = {
  'basic':   {'monthly': 54.99, '6months': 296.95, 'yearly': 494.91},
  'premium': {'monthly': 109.99,'6months': 593.95, 'yearly': 989.91},
  'vip':     {'monthly': 219.99,'6months': 1187.95,'yearly': 1979.91},
};

const _pricesKWD = {
  'basic':   {'monthly': 4.49,  '6months': 24.25,  'yearly': 40.41},
  'premium': {'monthly': 8.99,  '6months': 48.55,  'yearly': 80.91},
  'vip':     {'monthly': 17.99, '6months': 97.15,  'yearly': 161.91},
};

const _pricesBHD = {
  'basic':   {'monthly': 5.49,  '6months': 29.65,  'yearly': 49.41},
  'premium': {'monthly': 10.99, '6months': 59.35,  'yearly': 98.91},
  'vip':     {'monthly': 21.99, '6months': 118.75, 'yearly': 197.91},
};

const _pricesQAR = {
  'basic':   {'monthly': 54.99, '6months': 296.95, 'yearly': 494.91},
  'premium': {'monthly': 109.99,'6months': 593.95, 'yearly': 989.91},
  'vip':     {'monthly': 219.99,'6months': 1187.95,'yearly': 1979.91},
};

const _pricesOMR = {
  'basic':   {'monthly': 5.99,  '6months': 32.35,  'yearly': 53.91},
  'premium': {'monthly': 11.99, '6months': 64.75,  'yearly': 107.91},
  'vip':     {'monthly': 23.99, '6months': 129.55, 'yearly': 215.91},
};

String _currencyFor(String? country) {
  switch ((country ?? '').toUpperCase()) {
    case 'EG': return 'EGP';
    case 'SA': return 'SAR';
    case 'KW': return 'KWD';
    case 'BH': return 'BHD';
    case 'QA': return 'QAR';
    case 'OM': return 'OMR';
    default:   return 'AED';
  }
}

Map<String, Map<String, double>> _pricesFor(String? country) {
  switch ((country ?? '').toUpperCase()) {
    case 'EG': return _pricesEGP;
    case 'SA': return _pricesSAR;
    case 'KW': return _pricesKWD;
    case 'BH': return _pricesBHD;
    case 'QA': return _pricesQAR;
    case 'OM': return _pricesOMR;
    default:   return _pricesAED;
  }
}

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
    final currency = _currencyFor(user?.country);
    final prices   = _pricesFor(user?.country);
    final cs = Theme.of(context).colorScheme;

    return Scaffold(
      appBar: AppBar(title: Text(context.s('membership_title'))),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          // Current plan
          _CurrentPlanCard(membership: membership),
          const SizedBox(height: 20),

          // Billing cycle picker
          Center(
            child: SegmentedButton<String>(
              segments: [
                ButtonSegment(value: 'monthly',  label: Text(context.s('monthly'))),
                ButtonSegment(value: '6months',  label: Text(context.s('six_months'))),
                ButtonSegment(value: 'yearly',   label: Text(context.s('yearly'))),
              ],
              selected: {_cycle},
              onSelectionChanged: (s) => setState(() => _cycle = s.first),
            ),
          ),
          if (_cycle == '6months')
            Padding(
              padding: const EdgeInsets.only(top: 6),
              child: Text(
                context.s('save_10'),
                textAlign: TextAlign.center,
                style: TextStyle(color: Colors.green.shade700, fontSize: 12),
              ),
            ),
          if (_cycle == 'yearly')
            Padding(
              padding: const EdgeInsets.only(top: 6),
              child: Text(
                context.s('save_25'),
                textAlign: TextAlign.center,
                style: TextStyle(color: Colors.green.shade700, fontSize: 12),
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
              currency: currency,
              prices: prices,
            ),
            const SizedBox(height: 12),
          ],

          // Free plan summary
          const SizedBox(height: 8),
          Card(
            color: cs.surfaceContainerLowest,
            child: Padding(
              padding: const EdgeInsets.all(16),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(context.s('free_plan_includes'),
                      style: const TextStyle(fontWeight: FontWeight.w500)),
                  const SizedBox(height: 8),
                  for (final fKey in [
                    'free_feat_1',
                    'free_feat_2',
                    'free_feat_3',
                    'free_feat_4',
                  ])
                    Padding(
                      padding: const EdgeInsets.symmetric(vertical: 2),
                      child: Row(
                        children: [
                          Icon(Icons.check_circle_outline,
                              size: 16, color: cs.onSurfaceVariant),
                          const SizedBox(width: 8),
                          Text(context.s(fKey),
                              style: TextStyle(
                                  color: cs.onSurfaceVariant, fontSize: 13)),
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
      'vip'     => Colors.amber,
      'premium' => cs.primary,
      'basic'   => Colors.teal,
      _         => cs.onSurfaceVariant,
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
                Text(context.s('current_plan'),
                    style: TextStyle(color: cs.onSurfaceVariant, fontSize: 12)),
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
                '${context.s('active_since')}\n'
                '${membership.activatedAt!.day}/${membership.activatedAt!.month}/${membership.activatedAt!.year}',
                textAlign: TextAlign.right,
                style: TextStyle(fontSize: 11, color: cs.onSurfaceVariant),
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
    required this.currency,
    required this.prices,
  });

  final String tier;
  final String cycle;
  final String currentTier;
  final String userId;
  final String currency;
  final Map<String, Map<String, double>> prices;

  bool get _isCurrent => tier == currentTier;
  bool get _isUpgrade => _tierRank(tier) > _tierRank(currentTier);

  static int _tierRank(String t) =>
      const {'free': 0, 'basic': 1, 'premium': 2, 'vip': 3}[t] ?? 0;

  @override
  Widget build(BuildContext context) {
    final cs    = Theme.of(context).colorScheme;
    final color = switch (tier) {
      'vip'     => Colors.amber,
      'premium' => cs.primary,
      _         => Colors.teal,
    };
    final price    = (prices[tier]?[cycle] ?? 0.0) as double;
    final label    = tier[0].toUpperCase() + tier.substring(1);
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
                    child: Text(context.s('popular'),
                        style: const TextStyle(color: Colors.white, fontSize: 10)),
                  ),
                ],
              ],
            ),
            const SizedBox(height: 8),
            Row(
              crossAxisAlignment: CrossAxisAlignment.end,
              children: [
                Text(
                  '$currency ${price.toStringAsFixed(2)}',
                  style: const TextStyle(
                      fontSize: 22, fontWeight: FontWeight.bold),
                ),
                const SizedBox(width: 4),
                Padding(
                  padding: const EdgeInsets.only(bottom: 3),
                  child: Text(
                    cycle == 'monthly'
                        ? '/${context.s('monthly').toLowerCase()}'
                        : cycle == '6months'
                            ? '/${context.s('six_months').toLowerCase()}'
                            : '/${context.s('yearly').toLowerCase()}',
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
                      child: Text(context.s('current_plan_btn')),
                    )
                  : _isUpgrade
                      ? FilledButton(
                          onPressed: () =>
                              _showUpgradeSheet(context, tier, price),
                          style: FilledButton.styleFrom(
                              backgroundColor: color),
                          child: Text('${context.s('upgrade_to')} $label'),
                        )
                      : OutlinedButton(
                          onPressed: null,
                          child: Text(context.s('downgrade')),
                        ),
            ),
          ],
        ),
      ),
    );
  }

  void _showUpgradeSheet(BuildContext context, String tier, double price) {
    showModalBottomSheet(
      context: context,
      builder: (_) => SafeArea(
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Text(
                '${context.s('upgrade_to')} ${tier[0].toUpperCase()}${tier.substring(1)}',
                style: const TextStyle(
                    fontSize: 18, fontWeight: FontWeight.bold),
              ),
              const SizedBox(height: 8),
              Text('$currency ${price.toStringAsFixed(2)} / $cycle'),
              const SizedBox(height: 20),
              Text(
                context.s('payment_coming'),
                textAlign: TextAlign.center,
              ),
              const SizedBox(height: 20),
              FilledButton(
                onPressed: () => Navigator.pop(context),
                child: Text(context.s('ok')),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
