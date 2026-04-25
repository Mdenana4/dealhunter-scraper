import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../models/membership.dart';
import '../../providers/auth_provider.dart';
import '../../providers/search_provider.dart';
import '../../providers/saved_provider.dart';
import '../../config/theme.dart';
import '../../config/constants.dart';
import '../../widgets/deal_card.dart';
import '../deals/deal_detail_screen.dart';

class SearchTab extends ConsumerStatefulWidget {
  const SearchTab({super.key});

  @override
  ConsumerState<SearchTab> createState() => _SearchTabState();
}

class _SearchTabState extends ConsumerState<SearchTab> {
  final _ctrl = TextEditingController();
  final _focusNode = FocusNode();
  bool _searching = false;

  @override
  void dispose() {
    _ctrl.dispose();
    _focusNode.dispose();
    super.dispose();
  }

  void _submit(String value) {
    final trimmed = value.trim();
    if (trimmed.isEmpty) return;
    ref.read(searchQueryProvider.notifier).state = trimmed;
    ref.read(searchHistoryProvider.notifier).add(trimmed);
    _focusNode.unfocus();
    setState(() => _searching = true);
  }

  void _clear() {
    _ctrl.clear();
    ref.read(searchQueryProvider.notifier).state = '';
    setState(() => _searching = false);
  }

  @override
  Widget build(BuildContext context) {
    final userProfile = ref.watch(userProfileProvider).value;
    final tier = userProfile?.membership.tier ?? MembershipTier.free;

    // Free tier cannot search
    if (!tier.canSearchProduct) {
      return _UpgradePrompt(tier: tier);
    }

    final resultsAsync = ref.watch(searchResultsProvider);
    final history = ref.watch(searchHistoryProvider);

    return Scaffold(
      appBar: AppBar(
        title: TextField(
          controller: _ctrl,
          focusNode: _focusNode,
          onSubmitted: _submit,
          textInputAction: TextInputAction.search,
          style: const TextStyle(color: Colors.white),
          cursorColor: Colors.white,
          decoration: InputDecoration(
            hintText: 'Search products, brands...',
            hintStyle: const TextStyle(color: Colors.white60),
            border: InputBorder.none,
            filled: false,
            prefixIcon: const Icon(Icons.search, color: Colors.white),
            suffixIcon: _ctrl.text.isNotEmpty
                ? IconButton(
                    icon: const Icon(Icons.clear, color: Colors.white),
                    onPressed: _clear,
                  )
                : null,
          ),
          onChanged: (v) => setState(() {}),
        ),
        backgroundColor: AppTheme.primary,
      ),
      body: Column(
        children: [
          // Advanced filters (Premium+)
          if (tier.canFilterSize) _AdvancedFilters(),

          // Results or history
          Expanded(
            child: _searching
                ? resultsAsync.when(
                    loading: () => const Center(
                        child: CircularProgressIndicator()),
                    error: (_, __) => const Center(
                        child: Text('Search failed. Try again.')),
                    data: (deals) {
                      if (deals.isEmpty) {
                        return const Center(
                          child: Column(
                            mainAxisSize: MainAxisSize.min,
                            children: [
                              Icon(Icons.search_off,
                                  size: 64, color: Colors.grey),
                              SizedBox(height: 12),
                              Text('No results found.',
                                  style: TextStyle(fontSize: 16)),
                              SizedBox(height: 6),
                              Text('Try different keywords.',
                                  style: TextStyle(color: Colors.grey)),
                            ],
                          ),
                        );
                      }
                      return ListView.builder(
                        itemCount: deals.length,
                        itemBuilder: (ctx, i) {
                          final deal = deals[i];
                          return DealCard(
                            deal: deal,
                            onTap: () => Navigator.push(
                              context,
                              MaterialPageRoute(
                                  builder: (_) =>
                                      DealDetailScreen(deal: deal)),
                            ),
                            onSaveToggle: () async {
                              final user =
                                  ref.read(firebaseUserProvider).value;
                              if (user == null) return;
                              final actions =
                                  ref.read(savedActionsProvider);
                              if (actions == null) return;
                              deal.isSaved
                                  ? await actions.unsave(deal.id)
                                  : await actions.save(deal.id);
                            },
                          );
                        },
                      );
                    },
                  )
                : _SearchHistory(
                    history: history,
                    onTap: (term) {
                      _ctrl.text = term;
                      _submit(term);
                    },
                    onRemove: (term) =>
                        ref.read(searchHistoryProvider.notifier).remove(term),
                    onClearAll: () =>
                        ref.read(searchHistoryProvider.notifier).clear(),
                  ),
          ),
        ],
      ),
    );
  }
}

class _AdvancedFilters extends ConsumerWidget {
  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final category = ref.watch(searchCategoryProvider);
    final marketplace = ref.watch(searchMarketplaceProvider);

    return Container(
      height: 48,
      color: Colors.grey.shade100,
      child: ListView(
        scrollDirection: Axis.horizontal,
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
        children: [
          if (marketplace != null)
            Padding(
              padding: const EdgeInsets.only(right: 6),
              child: Chip(
                label: Text(AppConstants.marketplaceNames[marketplace] ?? marketplace),
                onDeleted: () =>
                    ref.read(searchMarketplaceProvider.notifier).state = null,
                deleteIcon: const Icon(Icons.close, size: 14),
              ),
            ),
          if (category != null)
            Padding(
              padding: const EdgeInsets.only(right: 6),
              child: Chip(
                label: Text(category),
                onDeleted: () =>
                    ref.read(searchCategoryProvider.notifier).state = null,
                deleteIcon: const Icon(Icons.close, size: 14),
              ),
            ),
          ActionChip(
            avatar: const Icon(Icons.tune, size: 14),
            label: const Text('Filters'),
            onPressed: () => _showFilterSheet(context, ref),
          ),
        ],
      ),
    );
  }

  void _showFilterSheet(BuildContext context, WidgetRef ref) {
    showModalBottomSheet(
      context: context,
      shape: const RoundedRectangleBorder(
          borderRadius: BorderRadius.vertical(top: Radius.circular(20))),
      builder: (ctx) => _FilterSheet(),
    );
  }
}

class _FilterSheet extends ConsumerWidget {
  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final selectedMC = ref.watch(searchMarketplaceProvider);
    final selectedCat = ref.watch(searchCategoryProvider);

    return Padding(
      padding: const EdgeInsets.all(24),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text('Filter Results',
              style: Theme.of(context).textTheme.titleLarge),
          const SizedBox(height: 20),
          Text('Marketplace', style: Theme.of(context).textTheme.titleMedium),
          const SizedBox(height: 8),
          Wrap(
            spacing: 8, runSpacing: 8,
            children: AppConstants.marketplaceNames.entries.map((e) =>
              ChoiceChip(
                label: Text(e.value),
                selected: selectedMC == e.key,
                onSelected: (_) => ref.read(searchMarketplaceProvider.notifier).state =
                    selectedMC == e.key ? null : e.key,
              ),
            ).toList(),
          ),
          const SizedBox(height: 16),
          Text('Category', style: Theme.of(context).textTheme.titleMedium),
          const SizedBox(height: 8),
          Wrap(
            spacing: 8, runSpacing: 8,
            children: ['Electronics', 'Fashion', 'Home', 'Sports',
                       'Beauty', 'Books', 'Toys', 'Grocery'].map((c) =>
              ChoiceChip(
                label: Text(c),
                selected: selectedCat == c,
                onSelected: (_) => ref.read(searchCategoryProvider.notifier).state =
                    selectedCat == c ? null : c,
              ),
            ).toList(),
          ),
          const SizedBox(height: 20),
          ElevatedButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('Apply'),
          ),
        ],
      ),
    );
  }
}

class _SearchHistory extends StatelessWidget {
  final List<String> history;
  final void Function(String) onTap;
  final void Function(String) onRemove;
  final VoidCallback onClearAll;

  const _SearchHistory({
    required this.history,
    required this.onTap,
    required this.onRemove,
    required this.onClearAll,
  });

  @override
  Widget build(BuildContext context) {
    if (history.isEmpty) {
      return Center(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const Icon(Icons.search, size: 64, color: Colors.grey),
            const SizedBox(height: 12),
            Text('Search any product across all stores.',
                style: Theme.of(context).textTheme.bodyLarge
                    ?.copyWith(color: Colors.grey)),
          ],
        ),
      );
    }

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Padding(
          padding: const EdgeInsets.fromLTRB(16, 16, 16, 8),
          child: Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Text('Recent searches',
                  style: Theme.of(context).textTheme.titleMedium),
              TextButton(
                  onPressed: onClearAll,
                  child: const Text('Clear all')),
            ],
          ),
        ),
        Expanded(
          child: ListView.builder(
            itemCount: history.length,
            itemBuilder: (_, i) {
              final term = history[i];
              return ListTile(
                leading: const Icon(Icons.history, size: 20,
                    color: Colors.grey),
                title: Text(term),
                trailing: IconButton(
                  icon: const Icon(Icons.close, size: 16),
                  onPressed: () => onRemove(term),
                ),
                onTap: () => onTap(term),
              );
            },
          ),
        ),
      ],
    );
  }
}

class _UpgradePrompt extends StatelessWidget {
  final MembershipTier tier;
  const _UpgradePrompt({required this.tier});

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(32),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const Icon(Icons.search, size: 72, color: Colors.grey),
            const SizedBox(height: 20),
            Text('Search is a Premium feature',
                style: Theme.of(context).textTheme.headlineSmall,
                textAlign: TextAlign.center),
            const SizedBox(height: 12),
            Text(
              'Upgrade to Premium to search any product, brand, or category across all stores.',
              style: Theme.of(context)
                  .textTheme
                  .bodyMedium
                  ?.copyWith(color: Colors.grey),
              textAlign: TextAlign.center,
            ),
            const SizedBox(height: 24),
            ElevatedButton.icon(
              onPressed: () {},
              icon: const Icon(Icons.upgrade),
              label: const Text('Upgrade to Premium'),
            ),
          ],
        ),
      ),
    );
  }
}
