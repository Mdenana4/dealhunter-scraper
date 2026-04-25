import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../services/auth_service.dart';
import '../services/api_service.dart';
import '../models/deal.dart';
import 'auth_provider.dart';
import 'deals_provider.dart';

// Saved deals full list (we store IDs in Firestore, fetch details from API)
final savedDealsProvider = FutureProvider.autoDispose<List<Deal>>((ref) async {
  final user = ref.watch(firebaseUserProvider).value;
  if (user == null) return [];

  final authService = ref.watch(authServiceProvider);
  final api = ref.watch(apiServiceProvider);

  final ids = await authService.getSavedDealIds(user.uid);
  if (ids.isEmpty) return [];

  // Fetch each deal from backend (in parallel, up to 10 at a time)
  final results = <Deal>[];
  for (final id in ids) {
    final deal = await api.getDealDetail(id);
    if (deal != null) results.add(deal.copyWith(isSaved: true));
  }
  return results;
});

class SavedDealActions {
  SavedDealActions(this._auth, this._uid);

  final AuthService _auth;
  final String _uid;

  Future<void> save(String dealId) => _auth.saveDeal(_uid, dealId);
  Future<void> unsave(String dealId) => _auth.unsaveDeal(_uid, dealId);
}

final savedActionsProvider = Provider.autoDispose<SavedDealActions?>((ref) {
  final user = ref.watch(firebaseUserProvider).value;
  if (user == null) return null;
  return SavedDealActions(ref.watch(authServiceProvider), user.uid);
});
