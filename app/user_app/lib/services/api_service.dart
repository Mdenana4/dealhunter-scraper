import 'package:dio/dio.dart';
import 'package:firebase_auth/firebase_auth.dart';
import '../config/constants.dart';
import '../models/deal.dart';
import '../models/price_point.dart';

class ApiService {
  late final Dio _dio;

  ApiService() {
    _dio = Dio(BaseOptions(
      baseUrl: AppConstants.apiBaseUrl,
      connectTimeout: const Duration(seconds: 10),
      receiveTimeout: const Duration(seconds: 15),
      headers: {'Content-Type': 'application/json'},
    ));

    _dio.interceptors.add(InterceptorsWrapper(
      onRequest: (options, handler) async {
        final user = FirebaseAuth.instance.currentUser;
        if (user != null) {
          final token = await user.getIdToken();
          options.headers['Authorization'] = 'Bearer $token';
        }
        handler.next(options);
      },
      onError: (error, handler) {
        handler.next(error);
      },
    ));
  }

  // ─── Deals ───────────────────────────────────────────────────────────────

  Future<List<Deal>> getDeals({
    String? category,
    String? marketplaceCountry,
    double minDiscount = 40.0,
    int limit = 50,
    int page = 1,
  }) async {
    try {
      final response = await _dio.get('/api/deals', queryParameters: {
        if (category != null) 'category': category,
        if (marketplaceCountry != null) 'marketplace_country': marketplaceCountry,
        'min_discount': minDiscount,
        'limit': limit,
        'page': page,
      });
      final data = response.data;
      final list = (data is Map ? data['deals'] : data) as List? ?? [];
      return list.map((d) => Deal.fromMap(d as Map<String, dynamic>)).toList();
    } catch (_) {
      return [];
    }
  }

  Future<Deal?> getDealDetail(String dealId) async {
    try {
      final response = await _dio.get('/api/deals/$dealId');
      return Deal.fromMap(response.data as Map<String, dynamic>);
    } catch (_) {
      return null;
    }
  }

  // ─── Price History ────────────────────────────────────────────────────────

  Future<PriceHistory?> getPriceHistory({
    required String marketplaceCountry,
    required String productId,
    int days = 90,
  }) async {
    try {
      final response = await _dio.get('/api/v1/tracker/history', queryParameters: {
        'marketplace_country': marketplaceCountry,
        'product_id': productId,
        'days': days,
      });
      return PriceHistory.fromMap(response.data as Map<String, dynamic>);
    } catch (_) {
      return null;
    }
  }

  Future<Map<String, dynamic>?> getProductSummary({
    required String marketplaceCountry,
    required String productId,
    int days = 90,
  }) async {
    try {
      final response = await _dio.get('/api/v1/tracker/product', queryParameters: {
        'marketplace_country': marketplaceCountry,
        'product_id': productId,
        'days': days,
      });
      return response.data as Map<String, dynamic>;
    } catch (_) {
      return null;
    }
  }

  // ─── Search ───────────────────────────────────────────────────────────────

  Future<List<Deal>> searchDeals({
    required String query,
    String? category,
    String? brand,
    String? size,
    String? marketplaceCountry,
    int limit = 30,
  }) async {
    try {
      final response = await _dio.get('/api/search', queryParameters: {
        'q': query,
        if (category != null) 'category': category,
        if (brand != null) 'brand': brand,
        if (size != null) 'size': size,
        if (marketplaceCountry != null) 'marketplace_country': marketplaceCountry,
        'limit': limit,
      });
      final data = response.data;
      final list = (data is Map ? data['results'] : data) as List? ?? [];
      return list.map((d) => Deal.fromMap(d as Map<String, dynamic>)).toList();
    } catch (_) {
      return [];
    }
  }

  // ─── Verification ─────────────────────────────────────────────────────────

  Future<VerificationSummary?> verifyDeal({
    required String marketplaceCountry,
    required String productId,
  }) async {
    try {
      final response = await _dio.get('/api/verify', queryParameters: {
        'marketplace_country': marketplaceCountry,
        'product_id': productId,
      });
      return VerificationSummary.fromMap(response.data as Map<String, dynamic>);
    } catch (_) {
      return null;
    }
  }

  // ─── Price Alerts ─────────────────────────────────────────────────────────

  Future<bool> createPriceAlert({
    required String userId,
    required String marketplaceCountry,
    required String productId,
    double? targetPrice,
    double? thresholdPct,
  }) async {
    try {
      await _dio.post('/api/v1/tracker/alert', data: {
        'user_id': userId,
        'marketplace_country': marketplaceCountry,
        'product_id': productId,
        if (targetPrice != null) 'target_price': targetPrice,
        if (thresholdPct != null) 'alert_threshold_pct': thresholdPct,
        'notification_channels': ['push'],
      });
      return true;
    } catch (_) {
      return false;
    }
  }

  // ─── Analytics (fire-and-forget) ──────────────────────────────────────────

  void logEvent(String event, Map<String, dynamic> data) {
    _dio.post('/api/analytics/event', data: {
      'event': event,
      'data': data,
      'timestamp': DateTime.now().toIso8601String(),
    }).catchError((_) {});
  }

  // ─── Payment ──────────────────────────────────────────────────────────────

  Future<Map<String, dynamic>?> createPaymentSession({
    required String userId,
    required String tier,
    required String billingCycle,
  }) async {
    try {
      final response = await _dio.post('/api/payment/create', data: {
        'user_id': userId,
        'tier': tier,
        'billing_cycle': billingCycle,
      });
      return response.data as Map<String, dynamic>;
    } catch (_) {
      return null;
    }
  }

  // ─── Admin (referral) ─────────────────────────────────────────────────────

  Future<bool> applyReferralCode(String userId, String code) async {
    try {
      await _dio.post('/api/referral/apply', data: {
        'user_id': userId,
        'referral_code': code,
      });
      return true;
    } catch (_) {
      return false;
    }
  }
}
