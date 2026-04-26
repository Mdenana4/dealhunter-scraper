class DealModel {
  final String id;
  final String title;
  final String store;
  final String source;
  final double currentPrice;
  final double originalPrice;
  final int discountPercent;
  final String currency;
  final String imageUrl;
  final String productUrl;
  final String category;
  final double rating;
  final String verdict;   // GENUINE | FAKE | SUSPICIOUS
  final double fakeScore;
  final double confidence;
  final List<String> fraudReasons;

  const DealModel({
    required this.id,
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
    required this.confidence,
    required this.fraudReasons,
  });

  factory DealModel.fromJson(Map<String, dynamic> json) {
    return DealModel(
      id: json['id'] as String? ?? '',
      title: json['title'] as String? ?? '',
      store: json['store'] as String? ?? json['source'] as String? ?? '',
      source: json['source'] as String? ?? '',
      currentPrice: (json['current_price'] as num?)?.toDouble() ?? 0.0,
      originalPrice: (json['original_price'] as num?)?.toDouble() ?? 0.0,
      discountPercent: (json['discount_percent'] as num?)?.toInt() ?? 0,
      currency: json['currency'] as String? ?? 'EGP',
      imageUrl: json['image_url'] as String? ?? '',
      productUrl: json['product_url'] as String? ?? '',
      category: json['category'] as String? ?? '',
      rating: (json['rating'] as num?)?.toDouble() ?? 0.0,
      verdict: json['verdict'] as String? ?? 'SUSPICIOUS',
      fakeScore: (json['fake_score'] as num?)?.toDouble() ?? 50.0,
      confidence: (json['confidence'] as num?)?.toDouble() ?? 50.0,
      fraudReasons: (json['fraud_reasons'] as List?)
              ?.map((e) => e.toString())
              .toList() ??
          [],
    );
  }

  double get savings =>
      originalPrice > currentPrice ? originalPrice - currentPrice : 0;
  bool get isGenuine => verdict == 'GENUINE';
  bool get isFake => verdict == 'FAKE';
  String get formattedPrice =>
      '$currency ${currentPrice.toStringAsFixed(0)}';
  String get formattedOriginal =>
      '$currency ${originalPrice.toStringAsFixed(0)}';
}
