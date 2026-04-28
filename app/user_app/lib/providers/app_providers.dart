import 'package:cloud_firestore/cloud_firestore.dart';
import 'package:firebase_auth/firebase_auth.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../models/deal_model.dart';
import '../models/user_model.dart';
import '../services/api_service.dart';

// ─── Navigation ────────────────────────────────────────────────────────────

final homeTabIndexProvider = StateProvider<int>((ref) => 0);

// ─── Locale ────────────────────────────────────────────────────────────────

final localeProvider = StateProvider<Locale>((ref) => const Locale('en'));

// ─── Services ──────────────────────────────────────────────────────────────

final apiServiceProvider = Provider<ApiService>((ref) => ApiService());

// ─── Auth ──────────────────────────────────────────────────────────────────

final authStateProvider = StreamProvider<User?>(
  (ref) => FirebaseAuth.instance.authStateChanges(),
);

final currentUserProvider = StreamProvider<UserModel?>((ref) {
  final authState = ref.watch(authStateProvider);
  return authState.when(
    data: (user) {
      if (user == null) return Stream.value(null);
      return FirebaseFirestore.instance
          .collection('users')
          .doc(user.uid)
          .snapshots()
          .map((snap) => snap.exists
              ? UserModel.fromFirestore(snap.id, snap.data()!)
              : null);
    },
    loading: () => Stream.value(null),
    error: (_, __) => Stream.value(null),
  );
});

// ─── Deals feed ────────────────────────────────────────────────────────────

class DealsNotifier extends StateNotifier<AsyncValue<List<DealModel>>> {
  DealsNotifier(this._api) : super(const AsyncValue.loading()) {
    load();
  }

  final ApiService _api;
  int _page = 1;
  bool _hasMore = true;
  String? _category;
  bool _loading = false;

  Future<void> load({bool reset = false}) async {
    if (_loading) return;
    if (!_hasMore && !reset) return;
    _loading = true;

    if (reset) {
      _page = 1;
      _hasMore = true;
      state = const AsyncValue.loading();
    }

    try {
      final deals = await _api.getDeals(
        category: _category,
        page: _page,
        limit: 30,
      );
      final prev =
          reset ? <DealModel>[] : (state.valueOrNull ?? <DealModel>[]);
      if (deals.length < 30) _hasMore = false;
      _page++;
      state = AsyncValue.data([...prev, ...deals]);
    } catch (e, st) {
      state = AsyncValue.error(e, st);
    } finally {
      _loading = false;
    }
  }

  Future<void> refresh() => load(reset: true);

  Future<void> setCategory(String? category) async {
    _category = category;
    await load(reset: true);
  }

  bool get hasMore => _hasMore;
}

final dealsProvider =
    StateNotifierProvider<DealsNotifier, AsyncValue<List<DealModel>>>(
  (ref) => DealsNotifier(ref.watch(apiServiceProvider)),
);

// ─── Single deal ───────────────────────────────────────────────────────────

final dealDetailProvider =
    FutureProvider.family<DealModel, String>((ref, id) async {
  return ref.watch(apiServiceProvider).getDeal(id);
});

// ─── Search ────────────────────────────────────────────────────────────────

class SearchNotifier extends StateNotifier<AsyncValue<List<DealModel>>> {
  SearchNotifier(this._api) : super(const AsyncValue.data([]));

  final ApiService _api;

  Future<void> search(String query, {String? category}) async {
    if (query.trim().length < 2) {
      state = const AsyncValue.data([]);
      return;
    }
    state = const AsyncValue.loading();
    try {
      final results =
          await _api.search(query.trim(), category: category);
      state = AsyncValue.data(results);
    } catch (e, st) {
      state = AsyncValue.error(e, st);
    }
  }

  void clear() => state = const AsyncValue.data([]);
}

final searchProvider =
    StateNotifierProvider<SearchNotifier, AsyncValue<List<DealModel>>>(
  (ref) => SearchNotifier(ref.watch(apiServiceProvider)),
);

// ─── Saved deals ───────────────────────────────────────────────────────────

final savedDealIdsProvider = StreamProvider<List<String>>((ref) {
  final authState = ref.watch(authStateProvider);
  final uid = authState.valueOrNull?.uid;
  if (uid == null) return Stream.value([]);
  return FirebaseFirestore.instance
      .collection('users')
      .doc(uid)
      .snapshots()
      .map((snap) =>
          (snap.data()?['saved_deals'] as List?)
              ?.map((e) => e.toString())
              .toList() ??
          []);
});

// ─── Verify ────────────────────────────────────────────────────────────────

typedef VerifyKey = ({String marketplaceCountry, String productId});

final verifyProvider =
    FutureProvider.family<Map<String, dynamic>, VerifyKey>((ref, key) async {
  return ref.watch(apiServiceProvider).verify(
        key.marketplaceCountry,
        key.productId,
      );
});

// ─── Price history ─────────────────────────────────────────────────────────

typedef HistoryKey = ({String marketplaceCountry, String productId, int days});

final priceHistoryProvider =
    FutureProvider.family<List<Map<String, dynamic>>, HistoryKey>(
        (ref, key) async {
  return ref.watch(apiServiceProvider).getPriceHistory(
        key.marketplaceCountry,
        key.productId,
        days: key.days,
      );
});

// ─── Price alerts ──────────────────────────────────────────────────────────

final userAlertsProvider =
    FutureProvider.autoDispose<List<Map<String, dynamic>>>((ref) async {
  final uid = ref.watch(authStateProvider).valueOrNull?.uid;
  if (uid == null) return [];
  return ref.watch(apiServiceProvider).getAlerts(uid);
});
