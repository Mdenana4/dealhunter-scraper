import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../services/api_service.dart';
import '../models/deal.dart';
import 'deals_provider.dart';

final searchQueryProvider = StateProvider<String>((ref) => '');
final searchCategoryProvider = StateProvider<String?>((ref) => null);
final searchBrandProvider = StateProvider<String?>((ref) => null);
final searchSizeProvider = StateProvider<String?>((ref) => null);
final searchMarketplaceProvider = StateProvider<String?>((ref) => null);

final searchResultsProvider =
    FutureProvider.autoDispose<List<Deal>>((ref) async {
  final query = ref.watch(searchQueryProvider);
  if (query.trim().length < 2) return [];

  final api = ref.watch(apiServiceProvider);
  return api.searchDeals(
    query: query.trim(),
    category: ref.watch(searchCategoryProvider),
    brand: ref.watch(searchBrandProvider),
    size: ref.watch(searchSizeProvider),
    marketplaceCountry: ref.watch(searchMarketplaceProvider),
  );
});

// Recently searched terms (persisted locally)
class SearchHistoryNotifier extends StateNotifier<List<String>> {
  SearchHistoryNotifier() : super([]);

  void add(String term) {
    if (term.trim().isEmpty) return;
    final list = [term, ...state.where((s) => s != term)];
    state = list.take(10).toList();
  }

  void remove(String term) {
    state = state.where((s) => s != term).toList();
  }

  void clear() => state = [];
}

final searchHistoryProvider =
    StateNotifierProvider<SearchHistoryNotifier, List<String>>(
  (ref) => SearchHistoryNotifier(),
);
