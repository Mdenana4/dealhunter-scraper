import 'package:intl/intl.dart';

class DealModel {
  final String id;         // Firestore document ID (e.g. amazon_eg_B09XYZ)
  final String productId;  // raw ASIN / SKU (e.g. B09XYZ) — used for price history
  final String title;
  final String store;
  final String source;     // marketplace_country (e.g. amazon_eg)
  final double currentPrice;
  final double originalPrice;
  final int discountPercent;
  final String currency;
  final String imageUrl;
  final String productUrl;
  final String category;
  final double rating;
  final String verdict;        // GENUINE | FAKE | SUSPICIOUS
  final double fakeScore;
  final String recommendation; // buy_now | good_deal | research_first | wait | avoid
  final double confidence;
  final List<String> fraudReasons;

  const DealModel({
    required this.id,
    required this.productId,
    required this.title,
    required this.store,
    required this.source,
    required this.currentPrice,
    required this.originalPrice,
    required this.discountPercent,
    required this.currency,
    required this.imageUrl,
    required this.productUrl,
    required this.category,
    required this.rating,
    required this.verdict,
    required this.fakeScore,
    required this.recommendation,
    required this.confidence,
    required this.fraudReasons,
  });

  static double _d(dynamic v) {
    if (v == null) return 0.0;
    if (v is double) return v;
    if (v is int) return v.toDouble();
    if (v is String) return double.tryParse(v) ?? 0.0;
    return 0.0;
  }

  static int _i(dynamic v) {
    if (v == null) return 0;
    if (v is int) return v;
    if (v is double) return v.toInt();
    if (v is String) return int.tryParse(v) ?? (double.tryParse(v)?.toInt() ?? 0);
    return 0;
  }

  factory DealModel.fromJson(Map<String, dynamic> json) {
    final docId = json['id'] as String? ?? '';
    final rawProductId = json['product_id'] as String? ??
        json['productId'] as String? ??
        docId;
    return DealModel(
      id: docId,
      productId: rawProductId,
      title: json['title'] as String? ?? '',
      store: json['store'] as String? ?? json['source'] as String? ?? '',
      source: json['source'] as String? ?? '',
      currentPrice: _d(json['current_price'] ?? json['currentPrice']),
      originalPrice: _d(json['original_price'] ?? json['originalPrice']),
      discountPercent: _i(json['discount_percent'] ?? json['discountPercent']),
      currency: json['currency'] as String? ?? 'EGP',
      imageUrl: json['image_url'] as String? ??
          json['imageUrl'] as String? ??
          '',
      productUrl: json['product_url'] as String? ??
          json['productUrl'] as String? ??
          '',
      category: json['category'] as String? ?? 'general',
      rating: _d(json['rating']),
      verdict: json['verdict'] as String? ?? 'UNVERIFIED',
      fakeScore: _d(json['fake_score'] ?? json['fakeScore']),
      recommendation: json['recommendation'] as String? ?? 'normal',
      confidence: _d(json['confidence']),
      fraudReasons: (json['fraud_reasons'] ?? json['fraudReasons'] as List?)
              ?.map((e) => e.toString())
              .toList() ??
          [],
    );
  }

  double get savings =>
      originalPrice > currentPrice ? originalPrice - currentPrice : 0.0;
  bool get isGenuine => verdict == 'GENUINE';
  bool get isFake => verdict == 'FAKE';
  bool get isSuspicious => verdict == 'SUSPICIOUS';
  bool get isUnverified => verdict == 'UNVERIFIED';

  String get formattedPrice {
    final fmt = NumberFormat('#,##0', 'en');
    return '$currency ${fmt.format(currentPrice)}';
  }

  String get formattedOriginal {
    final fmt = NumberFormat('#,##0', 'en');
    return '$currency ${fmt.format(originalPrice)}';
  }

  String get formattedSavings {
    final fmt = NumberFormat('#,##0', 'en');
    return '$currency ${fmt.format(savings)}';
  }
}
