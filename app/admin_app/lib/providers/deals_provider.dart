// lib/providers/deals_provider.dart

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:dio/dio.dart';
import '../models/deal.dart';

// API client provider
final dioProvider = Provider<Dio>((ref) {
  return Dio(
    BaseOptions(
      baseUrl: 'https://dealhunter-scraper.onrender.com/api/v1',
      connectTimeout: const Duration(seconds: 10),
      receiveTimeout: const Duration(seconds: 10),
    ),
  );
});

/// Fetch all deals
final dealsProvider = FutureProvider<List<DealModel>>((ref) async {
  final dio = ref.watch(dioProvider);
  try {
    final response = await dio.get('/admin/deals');
    final List<dynamic> data = response.data['data'] ?? response.data ?? [];
    return data
        .map((item) => DealModel.fromJson(
            item as Map<String, dynamic>, item['id'] as String? ?? ''))
        .toList();
  } catch (e) {
    throw Exception('Failed to load deals: $e');
  }
});

/// Get single deal by ID
final dealDetailProvider = FutureProvider.family<DealModel, String>(
    (ref, dealId) async {
  final dio = ref.watch(dioProvider);
  try {
    final response = await dio.get('/admin/deals/$dealId');
    return DealModel.fromJson(response.data as Map<String, dynamic>, dealId);
  } catch (e) {
    throw Exception('Failed to load deal: $e');
  }
});

/// Update deal
final updateDealProvider = FutureProvider.family<void,
    (String, Map<String, dynamic>)>((ref, params) async {
  final dio = ref.watch(dioProvider);
  final (dealId, updates) = params;
  try {
    await dio.put(
      '/admin/deals/$dealId',
      data: updates,
    );
    // Refresh deals list after updating
    ref.refresh(dealsProvider);
  } catch (e) {
    throw Exception('Failed to update deal: $e');
  }
});

/// Delete deal
final deleteDealProvider =
    FutureProvider.family<void, String>((ref, dealId) async {
  final dio = ref.watch(dioProvider);
  try {
    await dio.delete('/admin/deals/$dealId');
    // Refresh deals list after deleting
    ref.refresh(dealsProvider);
  } catch (e) {
    throw Exception('Failed to delete deal: $e');
  }
});

/// Toggle deal visibility (hide/show)
final toggleDealVisibilityProvider = FutureProvider.family<void,
    (String, bool)>((ref, params) async {
  final dio = ref.watch(dioProvider);
  final (dealId, hide) = params;
  try {
    await dio.patch(
      '/admin/deals/$dealId/visibility',
      data: {'hidden': hide},
    );
    ref.refresh(dealsProvider);
  } catch (e) {
    throw Exception('Failed to toggle visibility: $e');
  }
});

/// Toggle deal featured status
final toggleDealFeaturedProvider = FutureProvider.family<void,
    (String, bool)>((ref, params) async {
  final dio = ref.watch(dioProvider);
  final (dealId, featured) = params;
  try {
    await dio.patch(
      '/admin/deals/$dealId/featured',
      data: {'featured': featured},
    );
    ref.refresh(dealsProvider);
  } catch (e) {
    throw Exception('Failed to toggle featured: $e');
  }
});

/// Set deal fraud verdict
final setDealVerdictProvider = FutureProvider.family<void,
    (String, String)>((ref, params) async {
  final dio = ref.watch(dioProvider);
  final (dealId, verdict) = params;
  try {
    await dio.patch(
      '/admin/deals/$dealId/verdict',
      data: {'verdict': verdict}, // 'genuine', 'suspicious', 'fake'
    );
    ref.refresh(dealsProvider);
  } catch (e) {
    throw Exception('Failed to set verdict: $e');
  }
});

/// Get deal analytics
final dealAnalyticsProvider = FutureProvider.family<Map<String, dynamic>,
    String>((ref, dealId) async {
  final dio = ref.watch(dioProvider);
  try {
    final response = await dio.get('/admin/deals/$dealId/analytics');
    return response.data as Map<String, dynamic>;
  } catch (e) {
    throw Exception('Failed to load analytics: $e');
  }
});

/// Search deals
final searchDealsProvider = FutureProvider.family<List<DealModel>, String>(
    (ref, query) async {
  if (query.isEmpty) {
    return await ref.watch(dealsProvider.future);
  }

  final dio = ref.watch(dioProvider);
  try {
    final response =
        await dio.get('/admin/deals/search', queryParameters: {'q': query});
    final List<dynamic> data = response.data['data'] ?? [];
    return data
        .map((item) => DealModel.fromJson(
            item as Map<String, dynamic>, item['id'] as String? ?? ''))
        .toList();
  } catch (e) {
    // Fall back to client-side filtering
    final allDeals = await ref.watch(dealsProvider.future);
    final lowerQuery = query.toLowerCase();
    return allDeals
        .where((deal) =>
            deal.title.toLowerCase().contains(lowerQuery) ||
            deal.source.toLowerCase().contains(lowerQuery))
        .toList();
  }
});

/// Filter deals by source
final dealsBySourceProvider =
    FutureProvider.family<List<DealModel>, String>((ref, source) async {
  final allDeals = await ref.watch(dealsProvider.future);
  if (source == 'all') return allDeals;
  return allDeals.where((deal) => deal.source == source).toList();
});

/// Filter deals by status
final dealsByStatusProvider =
    FutureProvider.family<List<DealModel>, String>((ref, status) async {
  final allDeals = await ref.watch(dealsProvider.future);
  if (status == 'all') return allDeals;
  return allDeals.where((deal) => deal.status == status).toList();
});
