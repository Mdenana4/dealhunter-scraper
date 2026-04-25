import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:cached_network_image/cached_network_image.dart';
import 'package:share_plus/share_plus.dart';
import 'package:webview_flutter/webview_flutter.dart';
import '../../models/deal.dart';
import '../../models/price_point.dart';
import '../../models/user_profile.dart';
import '../../models/membership.dart';
import '../../providers/auth_provider.dart';
import '../../providers/deals_provider.dart';
import '../../providers/saved_provider.dart';
import '../../services/api_service.dart';
import '../../config/theme.dart';
import '../../config/constants.dart';
import '../../widgets/verification_badge.dart';
import '../../widgets/price_history_chart.dart';

class DealDetailScreen extends ConsumerStatefulWidget {
  final Deal deal;
  const DealDetailScreen({super.key, required this.deal});

  @override
  ConsumerState<DealDetailScreen> createState() => _DealDetailScreenState();
}

class _DealDetailScreenState extends ConsumerState<DealDetailScreen> {
  bool _showBrowserConfirm = false;
  bool _didBuyPrompt = false;
  late Deal _deal;

  @override
  void initState() {
    super.initState();
    _deal = widget.deal;
    _trackView();
  }

  void _trackView() {
    final user = ref.read(firebaseUserProvider).value;
    if (user != null) {
      ref.read(apiServiceProvider).logEvent('deal_viewed', {
        'deal_id': _deal.id,
        'user_id': user.uid,
        'marketplace_country': _deal.marketplaceCountry,
      });
    }
  }

  Future<void> _toggleSave() async {
    final user = ref.read(firebaseUserProvider).value;
    if (user == null) return;
    final actions = ref.read(savedActionsProvider);
    if (actions == null) return;

    if (_deal.isSaved) {
      await actions.unsave(_deal.id);
    } else {
      await actions.save(_deal.id);
    }
    setState(() => _deal = _deal.copyWith(isSaved: !_deal.isSaved));
  }

  void _openStore() {
    setState(() => _showBrowserConfirm = true);
  }

  void _confirmOpenStore() {
    setState(() => _showBrowserConfirm = false);
    final user = ref.read(firebaseUserProvider).value;
    ref.read(apiServiceProvider).logEvent('buy_clicked', {
      'deal_id': _deal.id,
      'user_id': user?.uid,
      'store': _deal.marketplaceCountry,
    });
    Navigator.of(context).push(MaterialPageRoute(
      builder: (_) => _InAppBrowser(
        url: _deal.url,
        storeName: AppConstants.marketplaceNames[_deal.marketplaceCountry]
            ?? _deal.storeName,
        onReturn: () {
          if (!mounted) return;
          Future.delayed(const Duration(milliseconds: 800), () {
            setState(() => _didBuyPrompt = true);
          });
        },
      ),
    ));
  }

  void _confirmPurchased() {
    setState(() => _didBuyPrompt = false);
    final user = ref.read(firebaseUserProvider).value;
    ref.read(apiServiceProvider).logEvent('purchase_confirmed', {
      'deal_id': _deal.id,
      'user_id': user?.uid,
    });
    ScaffoldMessenger.of(context).showSnackBar(const SnackBar(
      content: Text('Great! Added to your purchases. 🎉'),
      backgroundColor: AppTheme.genuine,
    ));
  }

  void _share() {
    Share.share(
      '🔥 ${_deal.discountLabel} OFF - ${_deal.name}\n'
      'Now ${_deal.formattedPrice} (was ${_deal.formattedOriginalPrice})\n'
      'on ${AppConstants.marketplaceNames[_deal.marketplaceCountry] ?? _deal.storeName}\n\n'
      '${_deal.url}\n\n'
      'Found by DealHunter 🎯',
    );
  }

  @override
  Widget build(BuildContext context) {
    final userProfile = ref.watch(userProfileProvider).value;
    final tier = userProfile?.membership.tier ?? MembershipTier.free;
    final historyDays = tier.historyDays;

    // Fetch verification automatically
    final verificationAsync = ref.watch(verificationProvider(
        (mc: _deal.marketplaceCountry, productId: _deal.productId)));

    // Fetch price history automatically
    final historyAsync = ref.watch(priceHistoryProvider(
        (mc: _deal.marketplaceCountry, productId: _deal.productId, days: historyDays)));

    return Scaffold(
      body: CustomScrollView(
        slivers: [
          // App bar with product image
          SliverAppBar(
            expandedHeight: 260,
            pinned: true,
            backgroundColor: AppTheme.primary,
            flexibleSpace: FlexibleSpaceBar(
              background: _deal.imageUrl != null
                  ? CachedNetworkImage(
                      imageUrl: _deal.imageUrl!,
                      fit: BoxFit.cover,
                      color: Colors.black26,
                      colorBlendMode: BlendMode.darken,
                    )
                  : Container(color: Colors.grey.shade200),
            ),
            actions: [
              IconButton(
                icon: Icon(
                    _deal.isSaved
                        ? Icons.bookmark_rounded
                        : Icons.bookmark_border_rounded,
                    color: Colors.white),
                onPressed: _toggleSave,
              ),
              IconButton(
                icon: const Icon(Icons.share, color: Colors.white),
                onPressed: _share,
              ),
            ],
          ),

          SliverToBoxAdapter(
            child: Padding(
              padding: const EdgeInsets.all(16),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  // Discount + store
                  Row(
                    children: [
                      Container(
                        padding: const EdgeInsets.symmetric(
                            horizontal: 12, vertical: 5),
                        decoration: BoxDecoration(
                            color: AppTheme.fake,
                            borderRadius: BorderRadius.circular(20)),
                        child: Text(_deal.discountLabel,
                            style: const TextStyle(
                                color: Colors.white,
                                fontWeight: FontWeight.w700)),
                      ),
                      const SizedBox(width: 10),
                      Text(
                        AppConstants.marketplaceNames[_deal.marketplaceCountry]
                            ?? _deal.storeName,
                        style: TextStyle(
                            color: AppTheme.primary,
                            fontWeight: FontWeight.w600),
                      ),
                      if (_deal.category != null) ...[
                        const Text(' · '),
                        Flexible(
                            child: Text(_deal.category!,
                                style: const TextStyle(color: Colors.grey),
                                overflow: TextOverflow.ellipsis)),
                      ],
                    ],
                  ),

                  const SizedBox(height: 12),

                  // Product name
                  Text(_deal.name,
                      style: Theme.of(context).textTheme.headlineSmall),

                  const SizedBox(height: 16),

                  // Price row
                  Row(
                    crossAxisAlignment: CrossAxisAlignment.end,
                    children: [
                      Text(_deal.formattedPrice,
                          style: Theme.of(context)
                              .textTheme
                              .displayMedium
                              ?.copyWith(
                                  color: AppTheme.genuine,
                                  fontWeight: FontWeight.w700)),
                      const SizedBox(width: 12),
                      if (_deal.originalPrice != null)
                        Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(_deal.formattedOriginalPrice,
                                style: const TextStyle(
                                    decoration: TextDecoration.lineThrough,
                                    color: Colors.grey,
                                    fontSize: 16)),
                            if (_deal.savingAmount.isNotEmpty)
                              Text('Save ${_deal.savingAmount}',
                                  style: const TextStyle(
                                      color: AppTheme.genuine,
                                      fontWeight: FontWeight.w600)),
                          ],
                        ),
                    ],
                  ),

                  // Stock status
                  const SizedBox(height: 10),
                  Row(
                    children: [
                      Icon(
                        _deal.inStock
                            ? Icons.check_circle
                            : Icons.cancel,
                        size: 16,
                        color: _deal.inStock
                            ? AppTheme.genuine
                            : AppTheme.fake,
                      ),
                      const SizedBox(width: 6),
                      Text(
                        _deal.inStock ? 'In Stock' : 'Out of Stock',
                        style: TextStyle(
                          color: _deal.inStock
                              ? AppTheme.genuine
                              : AppTheme.fake,
                          fontWeight: FontWeight.w600,
                        ),
                      ),
                    ],
                  ),

                  const SizedBox(height: 24),

                  // ─── VERIFICATION SECTION ────────────────────────────────
                  Text('Deal Verification',
                      style: Theme.of(context).textTheme.titleLarge),
                  const SizedBox(height: 10),

                  verificationAsync.when(
                    loading: () => const VerificationLoading(),
                    error: (_, __) => const _VerificationUnavailable(),
                    data: (v) => v != null
                        ? VerificationBadge(verification: v, expanded: true)
                        : const _VerificationUnavailable(),
                  ),

                  const SizedBox(height: 28),

                  // ─── PRICE HISTORY SECTION ────────────────────────────────
                  Row(
                    mainAxisAlignment: MainAxisAlignment.spaceBetween,
                    children: [
                      Text('Price History',
                          style: Theme.of(context).textTheme.titleLarge),
                      Text('Last $historyDays days',
                          style: TextStyle(
                              fontSize: 12, color: Colors.grey.shade500)),
                    ],
                  ),
                  const SizedBox(height: 12),

                  historyAsync.when(
                    loading: () => const SizedBox(
                        height: 200,
                        child: Center(child: CircularProgressIndicator())),
                    error: (_, __) => const SizedBox(
                        height: 80,
                        child: Center(
                            child: Text(
                                'Price history not available',
                                style: TextStyle(color: Colors.grey)))),
                    data: (history) => history != null && !history.isEmpty
                        ? PriceHistoryChart(
                            history: history,
                            lowestEver: history.lowestPrice,
                          )
                        : const SizedBox(
                            height: 80,
                            child: Center(
                                child: Text(
                                    'Not enough data yet — check back in a few days.',
                                    style: TextStyle(color: Colors.grey)))),
                  ),

                  // Tier upgrade hint if limited history
                  if (tier == MembershipTier.free || tier == MembershipTier.basic)
                    Padding(
                      padding: const EdgeInsets.only(top: 12),
                      child: _HistoryUpgradeHint(tier: tier),
                    ),

                  const SizedBox(height: 32),

                  // "Did you buy?" prompt
                  if (_didBuyPrompt) _DidYouBuyBanner(
                    onYes: _confirmPurchased,
                    onNo: () => setState(() => _didBuyPrompt = false),
                  ),

                  // Store confirm dialog
                  if (_showBrowserConfirm) _StoreConfirmBanner(
                    storeName: AppConstants.marketplaceNames[_deal.marketplaceCountry]
                        ?? _deal.storeName,
                    onConfirm: _confirmOpenStore,
                    onCancel: () => setState(() => _showBrowserConfirm = false),
                  ),

                  const SizedBox(height: 80), // space for bottom button
                ],
              ),
            ),
          ),
        ],
      ),

      // Fixed Buy button
      bottomNavigationBar: SafeArea(
        child: Padding(
          padding: const EdgeInsets.fromLTRB(16, 8, 16, 16),
          child: ElevatedButton.icon(
            onPressed: _deal.inStock ? _openStore : null,
            icon: const Icon(Icons.shopping_cart_rounded),
            label: Text(_deal.inStock
                ? 'Buy on ${AppConstants.marketplaceNames[_deal.marketplaceCountry]?.split(' ').first ?? "Store"}'
                : 'Out of Stock'),
            style: ElevatedButton.styleFrom(
              backgroundColor:
                  _deal.inStock ? AppTheme.primary : Colors.grey,
            ),
          ),
        ),
      ),
    );
  }
}

// ─── Supporting widgets ──────────────────────────────────────────────────────

class _VerificationUnavailable extends StatelessWidget {
  const _VerificationUnavailable();

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: Colors.grey.shade100,
        borderRadius: BorderRadius.circular(12),
      ),
      child: Row(
        children: [
          const Icon(Icons.info_outline, color: Colors.grey),
          const SizedBox(width: 10),
          Expanded(
            child: Text(
              'Verification not available yet. More price data needed.',
              style: TextStyle(color: Colors.grey.shade600, fontSize: 13),
            ),
          ),
        ],
      ),
    );
  }
}

class _HistoryUpgradeHint extends StatelessWidget {
  final MembershipTier tier;
  const _HistoryUpgradeHint({required this.tier});

  @override
  Widget build(BuildContext context) {
    final nextTier = tier == MembershipTier.free
        ? MembershipTier.basic
        : MembershipTier.premium;
    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: AppTheme.primary.withOpacity(0.06),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: AppTheme.primary.withOpacity(0.2)),
      ),
      child: Row(
        children: [
          const Icon(Icons.upgrade, color: AppTheme.primary, size: 18),
          const SizedBox(width: 8),
          Expanded(
            child: Text(
              'Upgrade to ${nextTier.displayName} for ${nextTier.historyDays} days of price history.',
              style: const TextStyle(fontSize: 12, color: AppTheme.primary),
            ),
          ),
        ],
      ),
    );
  }
}

class _StoreConfirmBanner extends StatelessWidget {
  final String storeName;
  final VoidCallback onConfirm;
  final VoidCallback onCancel;
  const _StoreConfirmBanner(
      {required this.storeName,
      required this.onConfirm,
      required this.onCancel});

  @override
  Widget build(BuildContext context) {
    return Card(
      color: Colors.blue.shade50,
      margin: const EdgeInsets.only(bottom: 16),
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Text('Open in $storeName?',
                style: Theme.of(context).textTheme.titleMedium),
            const SizedBox(height: 4),
            const Text(
                'You\'ll complete your purchase on the official store.',
                style: TextStyle(fontSize: 13, color: Colors.grey)),
            const SizedBox(height: 12),
            Row(
              children: [
                Expanded(
                  child: OutlinedButton(
                      onPressed: onCancel,
                      child: const Text('Cancel')),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: ElevatedButton(
                      onPressed: onConfirm,
                      child: const Text('Continue')),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }
}

class _DidYouBuyBanner extends StatelessWidget {
  final VoidCallback onYes;
  final VoidCallback onNo;
  const _DidYouBuyBanner({required this.onYes, required this.onNo});

  @override
  Widget build(BuildContext context) {
    return Card(
      color: AppTheme.genuine.withOpacity(0.08),
      margin: const EdgeInsets.only(bottom: 16),
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Text('Did you buy it? 🛍️',
                style: Theme.of(context).textTheme.titleMedium),
            const SizedBox(height: 4),
            const Text('Help us track your savings!',
                style: TextStyle(fontSize: 13, color: Colors.grey)),
            const SizedBox(height: 12),
            Row(
              children: [
                Expanded(
                  child: OutlinedButton(
                      onPressed: onNo,
                      child: const Text('Not yet')),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: ElevatedButton.icon(
                      onPressed: onYes,
                      icon: const Icon(Icons.check),
                      label: const Text('Yes, I bought it!'),
                      style: ElevatedButton.styleFrom(
                          backgroundColor: AppTheme.genuine)),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }
}

// In-app browser using WebView
class _InAppBrowser extends StatelessWidget {
  final String url;
  final String storeName;
  final VoidCallback onReturn;

  const _InAppBrowser(
      {required this.url,
      required this.storeName,
      required this.onReturn});

  @override
  Widget build(BuildContext context) {
    final controller = WebViewController()
      ..setJavaScriptMode(JavaScriptMode.unrestricted)
      ..loadRequest(Uri.parse(url));

    return WillPopScope(
      onWillPop: () async {
        onReturn();
        return true;
      },
      child: Scaffold(
        appBar: AppBar(
          title: Text(storeName),
          actions: [
            IconButton(
              icon: const Icon(Icons.open_in_new),
              onPressed: () {},
            ),
          ],
        ),
        body: WebViewWidget(controller: controller),
      ),
    );
  }
}
