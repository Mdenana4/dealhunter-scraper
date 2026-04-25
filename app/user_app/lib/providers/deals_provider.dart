import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../services/api_service.dart';
import '../models/deal.dart';

final apiServiceProvider = Provider<ApiService>((ref) => ApiService());

// Active category filter
final selectedCategoryProvider = StateProvider<String?>((ref) => null);
// Active marketplace filter
final selectedMarketplaceProvider = StateProvider<String?>((ref) => null);

class DealsNotifier extends StateNotifier<AsyncValue<List<Deal>>> {
  DealsNotifier(this._api, this._savedIds) : super(const AsyncValue.loading()) {
    load();
  }

  final ApiService _api;
  Set<String> _savedIds;

  String? _category;
  String? _marketplace;
  bool _isLoadingMore = false;
  int _page = 1;
  bool _hasMore = true;
  final List<Deal> _deals = [];

  void updateSavedIds(Set<String> ids) {
    _savedIds = ids;
    if (state is AsyncData) {
      final current = (state as AsyncData<List<Deal>>).value;
      state = AsyncValue.data(
        current.map((d) => d.copyWith(isSaved: ids.contains(d.id))).toList(),
      );
    }
  }

  Future<void> load({String? category, String? marketplace}) async {
    _category = category;
    _marketplace = marketplace;
    _page = 1;
    _hasMore = true;
    _deals.clear();
    state = const AsyncValue.loading();
    await _fetchPage();
  }

  Future<void> refresh() => load(category: _category, marketplace: _marketplace);

  Future<void> loadMore() async {
    if (_isLoadingMore || !_hasMore) return;
    _isLoadingMore = true;
    _page++;
    await _fetchPage();
    _isLoadingMore = false;
  }

  Future<void> _fetchPage() async {
    try {
      final fresh = await _api.getDeals(
        category: _category,
        marketplaceCountry: _marketplace,
        limit: 30,
        page: _page,
      );
      if (fresh.length < 30) _hasMore = false;
      final withSaved = fresh
          .map((d) => d.copyWith(isSaved: _savedIds.contains(d.id)))
          .toList();
      _deals.addAll(withSaved);
      state = AsyncValue.data(List.from(_deals));
    } catch (e, st) {
      if (_page == 1) {
        state = AsyncValue.error(e, st);
      }
    }
  }
}

final dealsNotifierProvider =
    StateNotifierProvider.autoDispose<DealsNotifier, AsyncValue<List<Deal>>>(
  (ref) {
    final api = ref.watch(apiServiceProvider);
    final savedIds = ref.watch(savedDealIdsProviderAlias);
    final notifier = DealsNotifier(api, savedIds);
    ref.listen(savedDealIdsProviderAlias, (_, next) {
      notifier.updateSavedIds(next);
    });
    return notifier;
  },
);

// Alias to avoid circular import (defined in auth_provider but used here)
final savedDealIdsProviderAlias = Provider<Set<String>>((ref) => {});

// Price history provider
final priceHistoryProvider = FutureProvider.autoDispose.family<
    dynamic, ({String mc, String productId, int days})>((ref, args) async {
  final api = ref.watch(apiServiceProvider);
  return api.getPriceHistory(
    marketplaceCountry: args.mc,
    productId: args.productId,
    days: args.days,
  );
});

// Verification provider
final verificationProvider = FutureProvider.autoDispose
    .family<VerificationSummary?, ({String mc, String productId})>(
        (ref, args) async {
  final api = ref.watch(apiServiceProvider);
  return api.verifyDeal(
      marketplaceCountry: args.mc, productId: args.productId);
});
