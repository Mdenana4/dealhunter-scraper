import 'package:dio/dio.dart';
import 'package:firebase_auth/firebase_auth.dart';
import '../models/deal_model.dart';

const _baseUrl = 'https://dealhunter-scraper.onrender.com';

class ApiService {
  final Dio _dio;

  ApiService()
      : _dio = Dio(
          BaseOptions(
            baseUrl: _baseUrl,
            connectTimeout: const Duration(seconds: 15),
            receiveTimeout: const Duration(seconds: 30),
          ),
        ) {
    _dio.interceptors.add(
      InterceptorsWrapper(
        onRequest: (options, handler) async {
          final user = FirebaseAuth.instance.currentUser;
          if (user != null) {
            final token = await user.getIdToken();
            options.headers['Authorization'] = 'Bearer $token';
          }
          handler.next(options);
        },
      ),
    );
  }

  // ─── Deals ─────────────────────────────────────────────────────────────────

  Future<List<DealModel>> getDeals({
    String? category,
    String? marketplaceCountry,
    double minDiscount = 0,
    int page = 1,
    int limit = 30,
  }) async {
    final resp = await _dio.get('/api/deals', queryParameters: {
      if (category != null && category.isNotEmpty) 'category': category,
      if (marketplaceCountry != null) 'marketplace_country': marketplaceCountry,
      if (minDiscount > 0) 'min_discount': minDiscount,
      'page': page,
      'limit': limit,
    });
    final data = resp.data as Map<String, dynamic>;
    final list = (data['deals'] as List?) ?? [];
    return list
        .map((e) => DealModel.fromJson(e as Map<String, dynamic>))
        .toList();
  }

  Future<DealModel> getDeal(String id) async {
    final resp = await _dio.get('/api/deals/$id');
    final data = resp.data as Map<String, dynamic>;
    return DealModel.fromJson(data['deal'] as Map<String, dynamic>);
  }

  Future<List<DealModel>> search(
    String query, {
    String? category,
    String? brand,
    String? marketplaceCountry,
    int limit = 30,
  }) async {
    final resp = await _dio.get('/api/search', queryParameters: {
      'q': query,
      if (category != null) 'category': category,
      if (brand != null) 'brand': brand,
      if (marketplaceCountry != null) 'marketplace_country': marketplaceCountry,
      'limit': limit,
    });
    final data = resp.data as Map<String, dynamic>;
    final list = (data['results'] as List?) ?? [];
    return list
        .map((e) => DealModel.fromJson(e as Map<String, dynamic>))
        .toList();
  }

  // ─── Verify ────────────────────────────────────────────────────────────────

  Future<Map<String, dynamic>> verify(
    String marketplaceCountry,
    String productId,
  ) async {
    final resp = await _dio.get('/api/verify', queryParameters: {
      'marketplace_country': marketplaceCountry,
      'product_id': productId,
    });
    return resp.data as Map<String, dynamic>;
  }

  // ─── Price history ─────────────────────────────────────────────────────────

  Future<List<Map<String, dynamic>>> getPriceHistory(
    String marketplaceCountry,
    String productId, {
    int days = 90,
  }) async {
    final resp = await _dio.get('/api/v1/tracker/history', queryParameters: {
      'marketplace_country': marketplaceCountry,
      'product_id': productId,
      'days': days,
    });
    final data = resp.data as Map<String, dynamic>;
    return ((data['history'] as List?) ?? [])
        .map((e) => e as Map<String, dynamic>)
        .toList();
  }

  // ─── Alerts ────────────────────────────────────────────────────────────────

  Future<String> createAlert({
    required String userId,
    required String marketplaceCountry,
    required String productId,
    double? targetPrice,
    double? alertThresholdPct,
  }) async {
    final resp = await _dio.post('/api/v1/tracker/alert', data: {
      'user_id': userId,
      'marketplace_country': marketplaceCountry,
      'product_id': productId,
      if (targetPrice != null) 'target_price': targetPrice,
      if (alertThresholdPct != null) 'alert_threshold_pct': alertThresholdPct,
    });
    final data = resp.data as Map<String, dynamic>;
    return data['alert_id'] as String? ?? '';
  }

  Future<List<Map<String, dynamic>>> getAlerts(String userId) async {
    final resp = await _dio.get('/api/v1/tracker/alert',
        queryParameters: {'user_id': userId});
    final data = resp.data as Map<String, dynamic>;
    return ((data['alerts'] as List?) ?? [])
        .map((e) => e as Map<String, dynamic>)
        .toList();
  }

  Future<void> deleteAlert(String alertId, String userId) async {
    await _dio.delete('/api/v1/tracker/alert/$alertId',
        data: {'user_id': userId});
  }

  // ─── Analytics ─────────────────────────────────────────────────────────────

  Future<void> logEvent(String event, [Map<String, dynamic>? extra]) async {
    try {
      await _dio.post('/api/analytics/event', data: {
        'event': event,
        'data': extra ?? {},
      });
    } catch (_) {
      // fire-and-forget: never throw
    }
  }

  // ─── Referral ──────────────────────────────────────────────────────────────

  Future<Map<String, dynamic>> applyReferral(
    String userId,
    String code,
  ) async {
    final resp = await _dio.post('/api/referral/apply', data: {
      'user_id': userId,
      'referral_code': code,
    });
    return resp.data as Map<String, dynamic>;
  }
}
