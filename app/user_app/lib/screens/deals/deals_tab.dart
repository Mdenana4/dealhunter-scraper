import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import '../../models/deal.dart';
import '../../models/membership.dart';
import '../../providers/auth_provider.dart';
import '../../providers/deals_provider.dart';
import '../../providers/saved_provider.dart';
import '../../config/theme.dart';
import '../../config/constants.dart';
import '../../widgets/deal_card.dart';
import 'deal_detail_screen.dart';

class DealsTab extends ConsumerStatefulWidget {
  const DealsTab({super.key});

  @override
  ConsumerState<DealsTab> createState() => _DealsTabState();
}

class _DealsTabState extends ConsumerState<DealsTab> {
  final _scrollController = ScrollController();

  @override
  void initState() {
    super.initState();
    _scrollController.addListener(_onScroll);
  }

  @override
  void dispose() {
    _scrollController.dispose();
    super.dispose();
  }

  void _onScroll() {
    if (_scrollController.position.pixels >=
        _scrollController.position.maxScrollExtent - 200) {
      ref.read(dealsNotifierProvider.notifier).loadMore();
    }
  }

  void _openDeal(Deal deal) {
    Navigator.of(context).push(MaterialPageRoute(
      builder: (_) => DealDetailScreen(deal: deal),
    ));
  }

  Future<void> _toggleSave(Deal deal) async {
    final user = ref.read(firebaseUserProvider).value;
    if (user == null) {
      context.push('/login');
      return;
    }
    final actions = ref.read(savedActionsProvider);
    if (actions == null) return;
    if (deal.isSaved) {
      await actions.unsave(deal.id);
    } else {
      await actions.save(deal.id);
    }
  }

  @override
  Widget build(BuildContext context) {
    final dealsAsync = ref.watch(dealsNotifierProvider);
    final userProfile = ref.watch(userProfileProvider).value;
    final tier = userProfile?.membership.tier ?? MembershipTier.free;
    final canFilter = tier.canFilterCategory;

    final selectedCategory = ref.watch(selectedCategoryProvider);
    final selectedMarketplace = ref.watch(selectedMarketplaceProvider);

    return RefreshIndicator(
      onRefresh: () => ref.read(dealsNotifierProvider.notifier).refresh(),
      child: CustomScrollView(
        controller: _scrollController,
        slivers: [
          // Header
          SliverAppBar(
            floating: true,
            snap: true,
            backgroundColor: AppTheme.primary,
            title: const Text('🔥 Hot Deals'),
            bottom: PreferredSize(
              preferredSize: const Size.fromHeight(56),
              child: _FilterBar(
                canFilter: canFilter,
                selectedCategory: selectedCategory,
                selectedMarketplace: selectedMarketplace,
                onCategoryChanged: (c) {
                  ref.read(selectedCategoryProvider.notifier).state = c;
                  ref
                      .read(dealsNotifierProvider.notifier)
                      .load(category: c, marketplace: selectedMarketplace);
                },
                onMarketplaceChanged: (m) {
                  ref.read(selectedMarketplaceProvider.notifier).state = m;
                  ref
                      .read(dealsNotifierProvider.notifier)
                      .load(category: selectedCategory, marketplace: m);
                },
              ),
            ),
          ),

          // Live indicator
          SliverToBoxAdapter(
            child: Padding(
              padding: const EdgeInsets.fromLTRB(16, 12, 16, 4),
              child: Row(
                children: [
                  const _PulseDot(),
                  const SizedBox(width: 6),
                  Text(
                    'Live deals — updating every ${tier.scanFrequency.toLowerCase()}',
                    style: TextStyle(
                        fontSize: 12, color: Colors.grey.shade600),
                  ),
                ],
              ),
            ),
          ),

          // Deal cards
          dealsAsync.when(
            loading: () => const SliverFillRemaining(
              child: Center(child: CircularProgressIndicator()),
            ),
            error: (e, _) => SliverFillRemaining(
              child: Center(
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    const Icon(Icons.wifi_off, size: 64, color: Colors.grey),
                    const SizedBox(height: 16),
                    const Text('Could not load deals.',
                        style: TextStyle(fontSize: 16)),
                    const SizedBox(height: 12),
                    ElevatedButton.icon(
                      onPressed: () =>
                          ref.read(dealsNotifierProvider.notifier).refresh(),
                      icon: const Icon(Icons.refresh),
                      label: const Text('Retry'),
                    ),
                  ],
                ),
              ),
            ),
            data: (deals) {
              if (deals.isEmpty) {
                return const SliverFillRemaining(
                  child: Center(
                    child: Column(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        Icon(Icons.local_offer_outlined,
                            size: 64, color: Colors.grey),
                        SizedBox(height: 12),
                        Text('No deals right now.',
                            style: TextStyle(fontSize: 16)),
                        SizedBox(height: 6),
                        Text('Pull down to refresh.',
                            style: TextStyle(color: Colors.grey)),
                      ],
                    ),
                  ),
                );
              }

              return SliverList(
                delegate: SliverChildBuilderDelegate(
                  (context, index) {
                    if (index >= deals.length) {
                      return const Padding(
                        padding: EdgeInsets.all(16),
                        child: Center(child: CircularProgressIndicator()),
                      );
                    }
                    final deal = deals[index];
                    return DealCard(
                      deal: deal,
                      onTap: () => _openDeal(deal),
                      onSaveToggle: () => _toggleSave(deal),
                      onShare: () {},
                    );
                  },
                  childCount: deals.length + 1,
                ),
              );
            },
          ),
        ],
      ),
    );
  }
}

class _FilterBar extends StatelessWidget {
  final bool canFilter;
  final String? selectedCategory;
  final String? selectedMarketplace;
  final void Function(String?) onCategoryChanged;
  final void Function(String?) onMarketplaceChanged;

  const _FilterBar({
    required this.canFilter,
    required this.selectedCategory,
    required this.selectedMarketplace,
    required this.onCategoryChanged,
    required this.onMarketplaceChanged,
  });

  static const _categories = [
    'Electronics', 'Fashion', 'Home', 'Sports', 'Beauty',
    'Books', 'Toys', 'Grocery'
  ];

  @override
  Widget build(BuildContext context) {
    return Container(
      height: 48,
      color: AppTheme.primary,
      child: canFilter
          ? ListView(
              scrollDirection: Axis.horizontal,
              padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
              children: [
                // All
                _FilterChip(
                  label: 'All',
                  selected: selectedCategory == null && selectedMarketplace == null,
                  onTap: () {
                    onCategoryChanged(null);
                    onMarketplaceChanged(null);
                  },
                ),
                const SizedBox(width: 6),
                // Marketplace filters
                ...AppConstants.marketplaceNames.entries.map((e) => Padding(
                  padding: const EdgeInsets.only(right: 6),
                  child: _FilterChip(
                    label: e.value.split(' ').first,
                    selected: selectedMarketplace == e.key,
                    onTap: () => onMarketplaceChanged(
                        selectedMarketplace == e.key ? null : e.key),
                  ),
                )),
                // Category filters
                ...(_categories.map((c) => Padding(
                  padding: const EdgeInsets.only(right: 6),
                  child: _FilterChip(
                    label: c,
                    selected: selectedCategory == c,
                    onTap: () =>
                        onCategoryChanged(selectedCategory == c ? null : c),
                  ),
                ))),
              ],
            )
          : Center(
              child: Text(
                'Upgrade to Basic to filter deals',
                style: TextStyle(color: Colors.white.withOpacity(0.8),
                    fontSize: 13),
              ),
            ),
    );
  }
}

class _FilterChip extends StatelessWidget {
  final String label;
  final bool selected;
  final VoidCallback onTap;
  const _FilterChip(
      {required this.label, required this.selected, required this.onTap});

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onTap,
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 4),
        decoration: BoxDecoration(
          color: selected ? Colors.white : Colors.white.withOpacity(0.2),
          borderRadius: BorderRadius.circular(20),
        ),
        child: Text(
          label,
          style: TextStyle(
            color: selected ? AppTheme.primary : Colors.white,
            fontSize: 12,
            fontWeight: selected ? FontWeight.w700 : FontWeight.normal,
          ),
        ),
      ),
    );
  }
}

class _PulseDot extends StatefulWidget {
  const _PulseDot();

  @override
  State<_PulseDot> createState() => _PulseDotState();
}

class _PulseDotState extends State<_PulseDot>
    with SingleTickerProviderStateMixin {
  late final AnimationController _ctrl;

  @override
  void initState() {
    super.initState();
    _ctrl = AnimationController(
        vsync: this, duration: const Duration(seconds: 1))
      ..repeat(reverse: true);
  }

  @override
  void dispose() {
    _ctrl.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return AnimatedBuilder(
      animation: _ctrl,
      builder: (_, __) => Container(
        width: 8,
        height: 8,
        decoration: BoxDecoration(
          color: AppTheme.genuine.withOpacity(0.5 + _ctrl.value * 0.5),
          shape: BoxShape.circle,
        ),
      ),
    );
  }
}
