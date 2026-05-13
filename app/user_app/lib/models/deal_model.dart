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

  factory DealModel.fromJson(Map<String, dynamic> json) {
    final docId = json['id'] as String? ?? '';
    // product_id is the raw ASIN/SKU; fall back to doc ID if missing
    final rawProductId = json['product_id'] as String? ??
        json['productId'] as String? ??
        docId;
    return DealModel(
      id: docId,
      productId: rawProductId,
      title: json['title'] as String? ?? '',
      store: json['store'] as String? ?? json['source'] as String? ?? '',
      source: json['source'] as String? ?? '',
      currentPrice: (json['current_price'] ?? json['currentPrice'] as num?)
              ?.toDouble() ??
          0.0,
      originalPrice: (json['original_price'] ?? json['originalPrice'] as num?)
              ?.toDouble() ??
          0.0,
      discountPercent:
          (json['discount_percent'] ?? json['discountPercent'] as num?)
                  ?.toInt() ??
              0,
      currency: json['currency'] as String? ?? 'EGP',
      imageUrl: json['image_url'] as String? ??
          json['imageUrl'] as String? ??
          '',
      productUrl: json['product_url'] as String? ??
          json['productUrl'] as String? ??
          '',
      category: json['category'] as String? ?? 'general',
      rating: (json['rating'] as num?)?.toDouble() ?? 0.0,
      verdict: json['verdict'] as String? ?? 'UNVERIFIED',
      fakeScore: (json['fake_score'] ?? json['fakeScore'] as num?)
              ?.toDouble() ??
          0.0,
      recommendation: json['recommendation'] as String? ?? 'normal',
      confidence: (json['confidence'] as num?)?.toDouble() ?? 0.0,
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
