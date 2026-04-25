import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../models/membership.dart';
import '../../providers/auth_provider.dart';
import '../../providers/deals_provider.dart';
import '../../services/api_service.dart';
import '../../config/theme.dart';
import 'package:webview_flutter/webview_flutter.dart';

class MembershipTab extends ConsumerWidget {
  const MembershipTab({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final userProfile = ref.watch(userProfileProvider).value;
    final currentTier = userProfile?.membership.tier ?? MembershipTier.free;

    return Scaffold(
      appBar: AppBar(
        title: const Text('💎 Membership'),
        backgroundColor: AppTheme.primary,
      ),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // Current plan card
            _CurrentPlanCard(membership: userProfile?.membership),

            const SizedBox(height: 24),

            Text('Choose Your Plan',
                style: Theme.of(context).textTheme.headlineSmall),
            const SizedBox(height: 4),
            Text('Cancel anytime. No hidden fees.',
                style: Theme.of(context)
                    .textTheme
                    .bodyMedium
                    ?.copyWith(color: Colors.grey)),

            const SizedBox(height: 16),

            // Tier cards
            ...MembershipTier.values.map((tier) => Padding(
                  padding: const EdgeInsets.only(bottom: 12),
                  child: _TierCard(
                    tier: tier,
                    isCurrentTier: tier == currentTier,
                    onSubscribe: () => _startPayment(context, ref, tier),
                  ),
                )),

            const SizedBox(height: 24),

            // Feature comparison table
            _FeatureTable(currentTier: currentTier),

            const SizedBox(height: 24),

            // Billing info (if subscribed)
            if (userProfile?.membership.tier != MembershipTier.free)
              _BillingInfo(membership: userProfile!.membership),
          ],
        ),
      ),
    );
  }

  Future<void> _startPayment(
      BuildContext context, WidgetRef ref, MembershipTier tier) async {
    if (tier == MembershipTier.free) return;

    // Show billing cycle picker
    final cycle = await showDialog<String>(
      context: context,
      builder: (_) => _BillingCycleDialog(tier: tier),
    );
    if (cycle == null) return;

    final user = ref.read(firebaseUserProvider).value;
    if (user == null) {
      Navigator.pushNamed(context, '/login');
      return;
    }

    // Create payment session
    final api = ref.read(apiServiceProvider);
    final session = await api.createPaymentSession(
        userId: user.uid, tier: tier.id, billingCycle: cycle);

    if (session == null || session['payment_url'] == null) {
      ScaffoldMessenger.of(context).showSnackBar(const SnackBar(
        content: Text('Could not start payment. Please try again.'),
        backgroundColor: AppTheme.fake,
      ));
      return;
    }

    // Open Paymob payment page in-app
    if (!context.mounted) return;
    Navigator.push(
      context,
      MaterialPageRoute(
        builder: (_) => _PaymentScreen(
          paymentUrl: session['payment_url'] as String,
          tier: tier,
          cycle: cycle,
        ),
      ),
    );
  }
}

class _CurrentPlanCard extends StatelessWidget {
  final Membership? membership;
  const _CurrentPlanCard({this.membership});

  @override
  Widget build(BuildContext context) {
    final tier = membership?.tier ?? MembershipTier.free;
    final color = AppTheme.tierColor(tier.id);

    return Container(
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        gradient: LinearGradient(
          colors: [color, color.withOpacity(0.7)],
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
        ),
        borderRadius: BorderRadius.circular(20),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              const Icon(Icons.workspace_premium, color: Colors.white, size: 28),
              const SizedBox(width: 10),
              Text('Your Plan',
                  style: const TextStyle(color: Colors.white70, fontSize: 14)),
              const Spacer(),
              if (membership?.expiresAt != null)
                Text(
                  'Renews ${_formatDate(membership!.expiresAt!)}',
                  style:
                      const TextStyle(color: Colors.white70, fontSize: 12),
                ),
            ],
          ),
          const SizedBox(height: 8),
          Text(
            tier.displayName,
            style: const TextStyle(
                color: Colors.white,
                fontSize: 28,
                fontWeight: FontWeight.w700),
          ),
          const SizedBox(height: 4),
          Text(
            tier == MembershipTier.free
                ? 'Free forever'
                : 'EGP ${membership?.effectivePrice.toStringAsFixed(0) ?? tier.monthlyPrice.toStringAsFixed(0)} / month',
            style: const TextStyle(color: Colors.white70, fontSize: 14),
          ),
          const SizedBox(height: 12),
          Row(
            children: [
              _PlanStat(label: 'Deals/day',
                  value: tier == MembershipTier.vip
                      ? '∞'
                      : '${tier.dailyNotifications}'),
              const SizedBox(width: 20),
              _PlanStat(label: 'History',
                  value: tier == MembershipTier.vip
                      ? 'Lifetime'
                      : '${tier.historyDays}d'),
              const SizedBox(width: 20),
              _PlanStat(label: 'Scan',
                  value: tier == MembershipTier.free
                      ? '30m'
                      : tier == MembershipTier.basic
                          ? '10m'
                          : '10s'),
            ],
          ),
        ],
      ),
    );
  }

  String _formatDate(DateTime dt) => '${dt.day}/${dt.month}/${dt.year}';
}

class _PlanStat extends StatelessWidget {
  final String label;
  final String value;
  const _PlanStat({required this.label, required this.value});

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        Text(value,
            style: const TextStyle(
                color: Colors.white,
                fontSize: 18,
                fontWeight: FontWeight.w700)),
        Text(label,
            style: const TextStyle(color: Colors.white70, fontSize: 11)),
      ],
    );
  }
}

class _TierCard extends StatelessWidget {
  final MembershipTier tier;
  final bool isCurrentTier;
  final VoidCallback onSubscribe;

  const _TierCard({
    required this.tier,
    required this.isCurrentTier,
    required this.onSubscribe,
  });

  @override
  Widget build(BuildContext context) {
    final color = AppTheme.tierColor(tier.id);
    final isPopular = tier == MembershipTier.premium;

    return Stack(
      clipBehavior: Clip.none,
      children: [
        Container(
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(16),
            border: Border.all(
              color: isCurrentTier ? color : Colors.grey.shade200,
              width: isCurrentTier ? 2 : 1,
            ),
            color: isCurrentTier
                ? color.withOpacity(0.04)
                : Theme.of(context).cardColor,
          ),
          child: Padding(
            padding: const EdgeInsets.all(16),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    Icon(Icons.workspace_premium, color: color, size: 24),
                    const SizedBox(width: 8),
                    Text(tier.displayName,
                        style: TextStyle(
                            fontSize: 18,
                            fontWeight: FontWeight.w700,
                            color: color)),
                    const Spacer(),
                    if (tier != MembershipTier.free)
                      Column(
                        crossAxisAlignment: CrossAxisAlignment.end,
                        children: [
                          Text(
                            'EGP ${tier.monthlyPrice.toStringAsFixed(0)}',
                            style: TextStyle(
                                fontSize: 20,
                                fontWeight: FontWeight.w700,
                                color: color),
                          ),
                          const Text('/month',
                              style: TextStyle(
                                  fontSize: 11, color: Colors.grey)),
                        ],
                      )
                    else
                      Text('FREE',
                          style: TextStyle(
                              fontSize: 20,
                              fontWeight: FontWeight.w700,
                              color: color)),
                  ],
                ),

                const SizedBox(height: 12),
                const Divider(),
                const SizedBox(height: 8),

                ...tier.features.map((f) => Padding(
                      padding: const EdgeInsets.only(bottom: 6),
                      child: Row(
                        children: [
                          Icon(Icons.check_circle_rounded,
                              size: 16, color: color),
                          const SizedBox(width: 8),
                          Expanded(child: Text(f, style: const TextStyle(fontSize: 13))),
                        ],
                      ),
                    )),

                const SizedBox(height: 12),

                SizedBox(
                  width: double.infinity,
                  child: isCurrentTier
                      ? OutlinedButton(
                          onPressed: null,
                          child: const Text('Current Plan'),
                        )
                      : tier == MembershipTier.free
                          ? const SizedBox()
                          : ElevatedButton(
                              onPressed: onSubscribe,
                              style: ElevatedButton.styleFrom(
                                  backgroundColor: color),
                              child: Text('Upgrade to ${tier.displayName}'),
                            ),
                ),
              ],
            ),
          ),
        ),

        // Popular badge
        if (isPopular)
          Positioned(
            top: -10,
            right: 16,
            child: Container(
              padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
              decoration: BoxDecoration(
                color: color,
                borderRadius: BorderRadius.circular(20),
              ),
              child: const Text('⭐ Most Popular',
                  style: TextStyle(
                      color: Colors.white,
                      fontSize: 11,
                      fontWeight: FontWeight.w700)),
            ),
          ),
      ],
    );
  }
}

class _FeatureTable extends StatelessWidget {
  final MembershipTier currentTier;
  const _FeatureTable({required this.currentTier});

  @override
  Widget build(BuildContext context) {
    final features = [
      ('Scan frequency', ['30 min', '10 min', '10 sec', '10 sec']),
      ('Deals per day', ['10', '50', '200', '∞']),
      ('Price history', ['30d', '60d', '180d', 'Lifetime']),
      ('Saved deals', ['10', '50', '∞', '∞']),
      ('Category filter', ['✗', '✓', '✓', '✓']),
      ('Product search', ['✗', '✗', '✓', '✓']),
      ('Size & brand filter', ['✗', '✗', '✓', '✓']),
      ('AI recommendations', ['✗', '✗', '✗', '✓']),
    ];

    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text('Feature Comparison',
                style: Theme.of(context).textTheme.titleLarge),
            const SizedBox(height: 12),
            Table(
              columnWidths: const {
                0: FlexColumnWidth(2),
                1: FlexColumnWidth(1),
                2: FlexColumnWidth(1),
                3: FlexColumnWidth(1),
                4: FlexColumnWidth(1),
              },
              children: [
                // Header
                TableRow(
                  decoration: BoxDecoration(
                      color: Colors.grey.shade100,
                      borderRadius: BorderRadius.circular(8)),
                  children: ['Feature', 'Free', 'Basic', 'Premium', 'VIP']
                      .map((h) => Padding(
                            padding: const EdgeInsets.all(8),
                            child: Text(h,
                                style: const TextStyle(
                                    fontSize: 11,
                                    fontWeight: FontWeight.w700),
                                textAlign: h == 'Feature'
                                    ? TextAlign.left
                                    : TextAlign.center),
                          ))
                      .toList(),
                ),
                // Rows
                ...features.map((f) {
                  final (label, values) = f;
                  return TableRow(
                    children: [
                      Padding(
                        padding: const EdgeInsets.all(8),
                        child: Text(label,
                            style: const TextStyle(fontSize: 12)),
                      ),
                      ...values.asMap().entries.map((e) {
                        final tierForIdx =
                            MembershipTier.values[e.key];
                        final isCurrent = tierForIdx == currentTier;
                        return Padding(
                          padding: const EdgeInsets.all(8),
                          child: Text(
                            e.value,
                            textAlign: TextAlign.center,
                            style: TextStyle(
                              fontSize: 12,
                              fontWeight: isCurrent
                                  ? FontWeight.w700
                                  : FontWeight.normal,
                              color: e.value == '✓'
                                  ? AppTheme.genuine
                                  : e.value == '✗'
                                      ? Colors.grey
                                      : isCurrent
                                          ? AppTheme.primary
                                          : null,
                            ),
                          ),
                        );
                      }),
                    ],
                  );
                }),
              ],
            ),
          ],
        ),
      ),
    );
  }
}

class _BillingInfo extends StatelessWidget {
  final Membership membership;
  const _BillingInfo({required this.membership});

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text('Billing', style: Theme.of(context).textTheme.titleMedium),
            const SizedBox(height: 12),
            if (membership.billingCycle != null)
              _BillingRow('Plan', '${membership.tier.displayName} (${membership.billingCycle})'),
            if (membership.expiresAt != null)
              _BillingRow('Next renewal',
                  '${membership.expiresAt!.day}/${membership.expiresAt!.month}/${membership.expiresAt!.year}'),
            _BillingRow('Amount',
                'EGP ${membership.effectivePrice.toStringAsFixed(0)}/month'),
            const SizedBox(height: 12),
            OutlinedButton(
              onPressed: () {},
              style: OutlinedButton.styleFrom(
                  foregroundColor: AppTheme.fake,
                  side: const BorderSide(color: AppTheme.fake)),
              child: const Text('Cancel Subscription'),
            ),
          ],
        ),
      ),
    );
  }
}

class _BillingRow extends StatelessWidget {
  final String label;
  final String value;
  const _BillingRow(this.label, this.value);

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 8),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Text(label, style: const TextStyle(color: Colors.grey)),
          Text(value, style: const TextStyle(fontWeight: FontWeight.w600)),
        ],
      ),
    );
  }
}

class _BillingCycleDialog extends StatefulWidget {
  final MembershipTier tier;
  const _BillingCycleDialog({required this.tier});

  @override
  State<_BillingCycleDialog> createState() => _BillingCycleDialogState();
}

class _BillingCycleDialogState extends State<_BillingCycleDialog> {
  String _selected = 'monthly';

  @override
  Widget build(BuildContext context) {
    final monthly = widget.tier.monthlyPrice;
    final options = [
      ('monthly', '1 Month', monthly, ''),
      ('6months', '6 Months', monthly * 6 * 0.9, 'Save 10%'),
      ('yearly', '1 Year', monthly * 12 * 0.75, 'Save 25%'),
    ];

    return AlertDialog(
      title: Text('Subscribe to ${widget.tier.displayName}'),
      content: Column(
        mainAxisSize: MainAxisSize.min,
        children: options.map((o) {
          final (id, label, price, badge) = o;
          return RadioListTile<String>(
            value: id,
            groupValue: _selected,
            onChanged: (v) => setState(() => _selected = v!),
            title: Row(
              children: [
                Text(label),
                if (badge.isNotEmpty) ...[
                  const SizedBox(width: 8),
                  Container(
                    padding: const EdgeInsets.symmetric(
                        horizontal: 6, vertical: 2),
                    decoration: BoxDecoration(
                      color: AppTheme.genuine,
                      borderRadius: BorderRadius.circular(4),
                    ),
                    child: Text(badge,
                        style: const TextStyle(
                            color: Colors.white, fontSize: 10)),
                  ),
                ],
              ],
            ),
            subtitle: Text(
                'EGP ${price.toStringAsFixed(0)} total'),
            activeColor: AppTheme.primary,
          );
        }).toList(),
      ),
      actions: [
        TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('Cancel')),
        ElevatedButton(
            onPressed: () => Navigator.pop(context, _selected),
            child: const Text('Continue to Payment')),
      ],
    );
  }
}

class _PaymentScreen extends StatelessWidget {
  final String paymentUrl;
  final MembershipTier tier;
  final String cycle;

  const _PaymentScreen({
    required this.paymentUrl,
    required this.tier,
    required this.cycle,
  });

  @override
  Widget build(BuildContext context) {
    final controller = WebViewController()
      ..setJavaScriptMode(JavaScriptMode.unrestricted)
      ..setNavigationDelegate(NavigationDelegate(
        onNavigationRequest: (req) {
          // Paymob redirects to a success/fail URL after payment
          if (req.url.contains('success=true') ||
              req.url.contains('payment_status=paid')) {
            Navigator.pop(context, true);
            ScaffoldMessenger.of(context).showSnackBar(SnackBar(
              content: Text(
                  '🎉 You\'re now on ${tier.displayName}!'),
              backgroundColor: AppTheme.genuine,
            ));
            return NavigationDecision.prevent;
          }
          if (req.url.contains('success=false') ||
              req.url.contains('payment_status=failed')) {
            Navigator.pop(context, false);
            ScaffoldMessenger.of(context).showSnackBar(const SnackBar(
              content: Text('Payment failed. Please try again.'),
              backgroundColor: AppTheme.fake,
            ));
            return NavigationDecision.prevent;
          }
          return NavigationDecision.navigate;
        },
      ))
      ..loadRequest(Uri.parse(paymentUrl));

    return Scaffold(
      appBar: AppBar(
        title: const Text('Secure Payment'),
        backgroundColor: AppTheme.primary,
      ),
      body: WebViewWidget(controller: controller),
    );
  }
}
