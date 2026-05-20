import 'package:cloud_firestore/cloud_firestore.dart';
import 'package:dio/dio.dart';
import 'package:firebase_auth/firebase_auth.dart';
import '../models/deal_model.dart';

// Deals are read directly from Firestore (where the scraper writes).
// The Cloud Run server is only used for search, verify, price history, alerts.
const _baseUrl = 'https://dealhunter-server-q2rbodm3ta-uc.a.run.app';

class ApiService {
  final Dio _dio;
  final FirebaseFirestore _db = FirebaseFirestore.instance;

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
        onError: (err, handler) async {
          if (err.response?.statusCode == 401) {
            try {
              final user = FirebaseAuth.instance.currentUser;
              if (user != null) {
                final token = await user.getIdToken(true);
                final opts = err.requestOptions;
                opts.headers['Authorization'] = 'Bearer $token';
                final resp = await _dio.fetch(opts);
                return handler.resolve(resp);
              }
            } catch (_) {}
          }
          handler.next(err);
        },
      ),
    );
  }

  // ─── Deals (Firestore) ─────────────────────────────────────────────────────
  // Reads directly from the 'deals' Firestore collection (populated by scraper).
  // 'source' maps to the 'site' field (e.g. 'amazon_eg', 'noon', 'jumia').

  Future<List<DealModel>> getDeals({
    String? category,
    String? country,
    String? source = 'amazon_eg',
    String? marketplaceCountry,
    double minDiscount = 0,
    int page = 1,
    int limit = 30,
  }) async {
    Query<Map<String, dynamic>> q = _db.collection('deals');

    final site = marketplaceCountry ?? source;
    final hasFilter = (site != null && site.isNotEmpty) ||
        (category != null && category.isNotEmpty);

    if (site != null && site.isNotEmpty) {
      q = q.where('site', isEqualTo: site);
    }
    if (category != null && category.isNotEmpty) {
      q = q.where('category', isEqualTo: category);
    }

    if (!hasFilter) {
      // No equality filter — single-field index on discount_percent is enough.
      q = q.orderBy('discount_percent', descending: true).limit(limit);
    } else {
      // With equality filters, orderBy('discount_percent') would need a
      // composite index. Load all matching docs (≤500) and sort client-side.
      q = q.limit(500);
    }

    final snap = await q.get();
    var docs = snap.docs.map((doc) {
      final data = Map<String, dynamic>.from(doc.data());
      data['id'] = doc.id;
      data['source'] = data['source'] ?? data['site'] ?? '';
      data['store'] = data['store'] ?? data['site_display'] ?? data['site'] ?? '';
      return data;
    }).toList();

    if (hasFilter) {
      // Filter by minDiscount client-side.
      if (minDiscount > 0) {
        docs = docs.where((d) {
          final dp = d['discount_percent'];
          final v = dp is num ? dp.toDouble() : double.tryParse(dp?.toString() ?? '') ?? 0.0;
          return v >= minDiscount;
        }).toList();
      }
      // Sort by discount_percent descending client-side.
      docs.sort((a, b) {
        final da = (a['discount_percent'] as num?)?.toDouble() ?? 0.0;
        final db = (b['discount_percent'] as num?)?.toDouble() ?? 0.0;
        return db.compareTo(da);
      });
      // Apply page-based offset.
      final offset = (page - 1) * limit;
      if (offset >= docs.length) return [];
      docs = docs.sublist(offset, (offset + limit).clamp(0, docs.length));
    }

    return docs.map((data) => DealModel.fromJson(data)).toList();
  }

  Future<DealModel> getDeal(String id) async {
    final doc = await _db.collection('deals').doc(id).get();
    if (!doc.exists) throw Exception('Deal not found: $id');
    final data = Map<String, dynamic>.from(doc.data()!);
    data['id'] = doc.id;
    data['source'] = data['source'] ?? data['site'] ?? '';
    data['store'] = data['store'] ?? data['site_display'] ?? data['site'] ?? '';
    return DealModel.fromJson(data);
  }

  // ─── Search (Cloud Run) ────────────────────────────────────────────────────

  Future<List<DealModel>> search(
    String query, {
    String? category,
    String? brand,
    String? marketplaceCountry,
    int limit = 30,
  }) async {
    try {
      final resp = await _dio.get('/api/search', queryParameters: {
        'q': query,
        if (category != null) 'category': category,
        if (brand != null) 'brand': brand,
        if (marketplaceCountry != null) 'marketplace_country': marketplaceCountry,
        'limit': limit,
      });
      final data = resp.data as Map<String, dynamic>;
      final list = (data['results'] as List?) ?? [];
      return list.map((e) => DealModel.fromJson(e as Map<String, dynamic>)).toList();
    } catch (_) {
      // Fall back to Firestore title search if server unavailable
      final snap = await _db
          .collection('deals')
          .orderBy('discount_percent', descending: true)
          .limit(limit)
          .get();
      final q = query.toLowerCase();
      return snap.docs
          .where((d) => (d.data()['title'] as String? ?? '').toLowerCase().contains(q))
          .map((doc) {
            final data = Map<String, dynamic>.from(doc.data());
            data['id'] = doc.id;
            data['source'] = data['source'] ?? data['site'] ?? '';
            data['store'] = data['store'] ?? data['site_display'] ?? data['site'] ?? '';
            return DealModel.fromJson(data);
          })
          .toList();
    }
  }

  // ─── Verify ────────────────────────────────────────────────────────────────

  Future<Map<String, dynamic>> verify(
    String marketplaceCountry,
    String productId, {
    String? productUrl,
    double? originalPrice,
    double? currentPrice,
    int? discountPercent,
  }) async {
    final resp = await _dio.get('/api/verify', queryParameters: {
      'marketplace_country': marketplaceCountry,
      'product_id': productId,
      if (productUrl != null && productUrl.isNotEmpty) 'product_url': productUrl,
      if (originalPrice != null) 'original_price': originalPrice,
      if (currentPrice != null) 'current_price': currentPrice,
      if (discountPercent != null) 'discount_percent': discountPercent,
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
