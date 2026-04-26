import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import '../../models/deal_model.dart';
import '../../models/user_model.dart';
import '../../providers/app_providers.dart';
import '../../widgets/deal_widgets.dart';

class SearchScreen extends ConsumerStatefulWidget {
  const SearchScreen({super.key});

  @override
  ConsumerState<SearchScreen> createState() => _SearchScreenState();
}

class _SearchScreenState extends ConsumerState<SearchScreen> {
  final _ctrl = TextEditingController();
  String? _category;

  @override
  void dispose() {
    _ctrl.dispose();
    super.dispose();
  }

  void _search([String? query]) {
    ref.read(searchProvider.notifier).search(
          query ?? _ctrl.text,
          category: _category,
        );
  }

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    final user = ref.watch(currentUserProvider).valueOrNull;
    final membership = user?.membership ?? const MembershipInfo();

    if (!membership.canSearch) {
      return Scaffold(
        appBar: AppBar(title: const Text('Search')),
        body: Center(
          child: Padding(
            padding: const EdgeInsets.all(32),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                Icon(Icons.lock_outline, size: 64, color: cs.primary),
                const SizedBox(height: 16),
                Text(
                  'Search is a Premium feature',
                  style: Theme.of(context).textTheme.titleMedium,
                  textAlign: TextAlign.center,
                ),
                const SizedBox(height: 8),
                Text(
                  'Upgrade to Basic or higher to search across all stores.',
                  textAlign: TextAlign.center,
                  style: TextStyle(color: cs.onSurfaceVariant),
                ),
                const SizedBox(height: 24),
                FilledButton(
                  onPressed: () {},
                  child: const Text('Upgrade Now'),
                ),
              ],
            ),
          ),
        ),
      );
    }

    final state = ref.watch(searchProvider);
    return Scaffold(
      appBar: AppBar(
        title: TextField(
          controller: _ctrl,
          autofocus: false,
          textInputAction: TextInputAction.search,
          decoration: InputDecoration(
            hintText: 'Search deals…',
            border: InputBorder.none,
            suffixIcon: _ctrl.text.isNotEmpty
                ? IconButton(
                    icon: const Icon(Icons.clear),
                    onPressed: () {
                      _ctrl.clear();
                      ref.read(searchProvider.notifier).clear();
                    },
                  )
                : null,
          ),
          onChanged: (v) {
            setState(() {});
            if (v.length >= 2) _search(v);
          },
          onSubmitted: _search,
        ),
      ),
      body: Column(
        children: [
          // Category filter
          SizedBox(
            height: 48,
            child: ListView(
              scrollDirection: Axis.horizontal,
              padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
              children: [
                FilterChip(
                  label: const Text('All'),
                  selected: _category == null,
                  onSelected: (_) {
                    setState(() => _category = null);
                    _search();
                  },
                  showCheckmark: false,
                ),
                const SizedBox(width: 8),
                for (final cat in [
                  'Electronics',
                  'Fashion',
                  'Home',
                  'Beauty',
                  'Sports'
                ]) ...[
                  FilterChip(
                    label: Text(cat),
                    selected: _category == cat.toLowerCase(),
                    onSelected: (_) {
                      setState(() => _category = cat.toLowerCase());
                      _search();
                    },
                    showCheckmark: false,
                  ),
                  const SizedBox(width: 8),
                ],
              ],
            ),
          ),
          // Results
          Expanded(
            child: state.when(
              loading: () =>
                  const Center(child: CircularProgressIndicator()),
              error: (e, _) => Center(child: Text('Error: $e')),
              data: (results) {
                if (_ctrl.text.isEmpty) {
                  return Center(
                    child: Column(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        Icon(Icons.search,
                            size: 64, color: cs.onSurfaceVariant),
                        const SizedBox(height: 12),
                        Text('Type to search',
                            style: TextStyle(
                                color: cs.onSurfaceVariant)),
                      ],
                    ),
                  );
                }
                if (results.isEmpty) {
                  return Center(
                    child: Column(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        Icon(Icons.search_off_rounded,
                            size: 64, color: cs.onSurfaceVariant),
                        const SizedBox(height: 12),
                        Text(
                          'No results for "${_ctrl.text}"',
                          style:
                              TextStyle(color: cs.onSurfaceVariant),
                        ),
                      ],
                    ),
                  );
                }
                return ListView.builder(
                  itemCount: results.length,
                  itemBuilder: (_, i) => _DealRow(deal: results[i]),
                );
              },
            ),
          ),
        ],
      ),
    );
  }
}

class _DealRow extends StatelessWidget {
  const _DealRow({required this.deal});

  final DealModel deal;

  @override
  Widget build(BuildContext context) {
    return ListTile(
      onTap: () => context.go('/home/deal/${deal.id}', extra: deal),
      leading: ClipRRect(
        borderRadius: BorderRadius.circular(6),
        child: SizedBox(
          width: 56,
          height: 56,
          child: deal.imageUrl.isNotEmpty
              ? Image.network(deal.imageUrl, fit: BoxFit.cover,
                  errorBuilder: (_, __, ___) =>
                      const Icon(Icons.image_not_supported_outlined))
              : const Icon(Icons.image_outlined),
        ),
      ),
      title: Text(deal.title, maxLines: 1, overflow: TextOverflow.ellipsis),
      subtitle: Text(
        '${deal.formattedPrice}  •  -${deal.discountPercent}%',
        style: TextStyle(color: Theme.of(context).colorScheme.primary),
      ),
      trailing: VerdictDot(verdict: deal.verdict),
    );
  }
}
