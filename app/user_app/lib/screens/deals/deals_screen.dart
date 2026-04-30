import 'package:cached_network_image/cached_network_image.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:shimmer/shimmer.dart';
import '../../l10n/app_strings.dart';
import '../../models/deal_model.dart';
import '../../providers/app_providers.dart';
import '../../widgets/deal_widgets.dart';

// Category keys map to S keys for translation
const _categoryKeys = [
  ('All', 'cat_all'),
  ('Electronics', 'cat_electronics'),
  ('Fashion', 'cat_fashion'),
  ('Home', 'cat_home'),
  ('Beauty', 'cat_beauty'),
  ('Sports', 'cat_sports'),
  ('Toys', 'cat_toys'),
  ('Books', 'cat_books'),
  ('Food', 'cat_food'),
];

class DealsScreen extends ConsumerStatefulWidget {
  const DealsScreen({super.key});

  @override
  ConsumerState<DealsScreen> createState() => _DealsScreenState();
}

// Country options: (code sent to API, string key for translation)
const _countries = [
  (null,  'country_all'),
  ('eg',  'country_eg'),
  ('ae',  'country_ae'),
  ('sa',  'country_sa'),
];

// Source options: (code sent to API, string key)
const _sources = [
  (null,      'source_all'),
  ('amazon',  'source_amazon'),
  ('noon',    'source_noon'),
  ('jumia',   'source_jumia'),
];

class _DealsScreenState extends ConsumerState<DealsScreen> {
  final _scrollCtrl = ScrollController();
  String _category = 'All';
  String? _country;
  String? _source;

  @override
  void initState() {
    super.initState();
    _scrollCtrl.addListener(_onScroll);
  }

  @override
  void dispose() {
    _scrollCtrl.removeListener(_onScroll);
    _scrollCtrl.dispose();
    super.dispose();
  }

  void _onScroll() {
    if (_scrollCtrl.position.pixels >
        _scrollCtrl.position.maxScrollExtent - 300) {
      ref.read(dealsProvider.notifier).load();
    }
  }

  Future<void> _refresh() => ref.read(dealsProvider.notifier).refresh();

  void _setCategory(String cat) {
    setState(() => _category = cat);
    ref.read(dealsProvider.notifier).setCategory(cat == 'All' ? null : cat.toLowerCase());
  }

  void _setCountry(String? code) {
    setState(() => _country = code);
    ref.read(dealsProvider.notifier).setCountry(code);
  }

  void _setSource(String? code) {
    setState(() => _source = code);
    ref.read(dealsProvider.notifier).setSource(code);
  }

  @override
  Widget build(BuildContext context) {
    final state = ref.watch(dealsProvider);
    return Scaffold(
      appBar: AppBar(
        title: const Text('DealHunter 🔥'),
        centerTitle: false,
        actions: [
          IconButton(
            icon: const Icon(Icons.notifications_outlined),
            onPressed: () =>
                ref.read(homeTabIndexProvider.notifier).state = 2,
          ),
        ],
        bottom: PreferredSize(
          preferredSize: const Size.fromHeight(150),
          child: Column(
            children: [
              _CountryBar(selected: _country, onSelect: _setCountry),
              _SourceBar(selected: _source, onSelect: _setSource),
              _CategoryBar(selected: _category, onSelect: _setCategory),
            ],
          ),
        ),
      ),
      body: state.when(
        loading: () => _ShimmerList(),
        error: (e, _) => _ErrorView(message: e.toString(), onRetry: _refresh),
        data: (deals) {
          if (deals.isEmpty) {
            return Center(
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  const Icon(Icons.search_off_rounded, size: 64),
                  const SizedBox(height: 12),
                  Text(context.s('no_deals')),
                  TextButton(
                      onPressed: _refresh, child: Text(context.s('refresh'))),
                ],
              ),
            );
          }
          final hasMore =
              ref.read(dealsProvider.notifier).hasMore;
          return RefreshIndicator(
            onRefresh: _refresh,
            child: ListView.builder(
              controller: _scrollCtrl,
              padding: const EdgeInsets.only(bottom: 16),
              itemCount: deals.length + (hasMore ? 1 : 0),
              itemBuilder: (ctx, i) {
                if (i == deals.length) {
                  return const Center(
                    child: Padding(
                      padding: EdgeInsets.all(16),
                      child: CircularProgressIndicator(),
                    ),
                  );
                }
                return _DealCard(deal: deals[i]);
              },
            ),
          );
        },
      ),
    );
  }
}

// ─── Country bar ───────────────────────────────────────────────────────────

class _CountryBar extends StatelessWidget {
  const _CountryBar({required this.selected, required this.onSelect});

  final String? selected;
  final ValueChanged<String?> onSelect;

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      height: 48,
      child: ListView.separated(
        scrollDirection: Axis.horizontal,
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
        itemCount: _countries.length,
        separatorBuilder: (_, __) => const SizedBox(width: 8),
        itemBuilder: (_, i) {
          final (code, strKey) = _countries[i];
          final active = code == selected;
          return FilterChip(
            label: Text(context.s(strKey)),
            selected: active,
            onSelected: (_) => onSelect(code),
            showCheckmark: false,
            avatar: null,
          );
        },
      ),
    );
  }
}

// ─── Source bar ────────────────────────────────────────────────────────────

class _SourceBar extends StatelessWidget {
  const _SourceBar({required this.selected, required this.onSelect});

  final String? selected;
  final ValueChanged<String?> onSelect;

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      height: 48,
      child: ListView.separated(
        scrollDirection: Axis.horizontal,
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
        itemCount: _sources.length,
        separatorBuilder: (_, __) => const SizedBox(width: 8),
        itemBuilder: (_, i) {
          final (code, strKey) = _sources[i];
          final active = code == selected;
          return FilterChip(
            label: Text(context.s(strKey)),
            selected: active,
            onSelected: (_) => onSelect(code),
            showCheckmark: false,
          );
        },
      ),
    );
  }
}

// ─── Category bar ──────────────────────────────────────────────────────────

class _CategoryBar extends StatelessWidget {
  const _CategoryBar({required this.selected, required this.onSelect});

  final String selected;
  final ValueChanged<String> onSelect;

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      height: 48,
      child: ListView.separated(
        scrollDirection: Axis.horizontal,
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
        itemCount: _categoryKeys.length,
        separatorBuilder: (_, __) => const SizedBox(width: 8),
        itemBuilder: (_, i) {
          final (key, strKey) = _categoryKeys[i];
          final active = key == selected;
          return FilterChip(
            label: Text(context.s(strKey)),
            selected: active,
            onSelected: (_) => onSelect(key),
            showCheckmark: false,
          );
        },
      ),
    );
  }
}

// ─── Deal card ─────────────────────────────────────────────────────────────

class _DealCard extends StatelessWidget {
  const _DealCard({required this.deal});

  final DealModel deal;

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    return Card(
      margin: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
      clipBehavior: Clip.antiAlias,
      child: InkWell(
        onTap: () => context.go('/home/deal/${deal.id}', extra: deal),
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // Thumbnail
            SizedBox(
              width: 110,
              height: 110,
              child: deal.imageUrl.isNotEmpty
                  ? CachedNetworkImage(
                      imageUrl: deal.imageUrl,
                      fit: BoxFit.cover,
                      errorWidget: (_, __, ___) =>
                          const Icon(Icons.image_not_supported_outlined,
                              size: 40),
                    )
                  : Container(
                      color: cs.surfaceContainerHighest,
                      child: const Icon(Icons.image_outlined, size: 40),
                    ),
            ),
            // Content
            Expanded(
              child: Padding(
                padding: const EdgeInsets.all(10),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      deal.title,
                      maxLines: 2,
                      overflow: TextOverflow.ellipsis,
                      style: const TextStyle(
                          fontSize: 14, fontWeight: FontWeight.w500),
                    ),
                    const SizedBox(height: 6),
                    Row(
                      children: [
                        Text(
                          deal.formattedPrice,
                          style: TextStyle(
                            fontSize: 16,
                            fontWeight: FontWeight.bold,
                            color: cs.primary,
                          ),
                        ),
                        const SizedBox(width: 8),
                        if (deal.originalPrice > deal.currentPrice)
                          Text(
                            deal.formattedOriginal,
                            style: TextStyle(
                              fontSize: 12,
                              decoration: TextDecoration.lineThrough,
                              color: cs.onSurfaceVariant,
                            ),
                          ),
                      ],
                    ),
                    const SizedBox(height: 6),
                    Row(
                      children: [
                        DiscountBadge(percent: deal.discountPercent),
                        const SizedBox(width: 8),
                        VerdictDot(verdict: deal.verdict),
                      ],
                    ),
                    const SizedBox(height: 4),
                    Text(
                      deal.store,
                      style: TextStyle(
                          fontSize: 11, color: cs.onSurfaceVariant),
                    ),
                  ],
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

// ─── Shimmer loading ───────────────────────────────────────────────────────

class _ShimmerList extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return Shimmer.fromColors(
      baseColor: Colors.grey.shade300,
      highlightColor: Colors.grey.shade100,
      child: ListView.builder(
        padding: const EdgeInsets.symmetric(vertical: 8),
        itemCount: 8,
        itemBuilder: (_, __) => Card(
          margin: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
          child: SizedBox(
            height: 110,
            child: Row(
              children: [
                Container(width: 110, color: Colors.white),
                const SizedBox(width: 10),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                      Container(height: 14, width: double.infinity,
                          color: Colors.white),
                      const SizedBox(height: 8),
                      Container(height: 14, width: 120, color: Colors.white),
                      const SizedBox(height: 8),
                      Container(height: 10, width: 80, color: Colors.white),
                    ],
                  ),
                ),
                const SizedBox(width: 10),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

// ─── Error view ────────────────────────────────────────────────────────────

class _ErrorView extends StatelessWidget {
  const _ErrorView({required this.message, required this.onRetry});

  final String message;
  final VoidCallback onRetry;

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const Icon(Icons.wifi_off_rounded, size: 56),
            const SizedBox(height: 12),
            Text(message, textAlign: TextAlign.center),
            const SizedBox(height: 16),
            FilledButton(onPressed: onRetry, child: Text(context.s('retry'))),
          ],
        ),
      ),
    );
  }
}
