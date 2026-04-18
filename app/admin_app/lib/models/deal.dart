// lib/models/deal.dart

class DealModel {
  final String id;
  final String title;
  final String source; // 'amazon', 'jumia', 'noon'
  final double currentPrice;
  final double? originalPrice;
  final int? discountPercent;
  final String? imageUrl;
  final String? productUrl;
  final String status; // 'active', 'hidden', 'expired'
  final String verdict; // 'genuine', 'suspicious', 'fake'
  final bool featured;
  final bool hidden;
  final int views;
  final double? rating;
  final int? reviews;
  final DateTime addedAt;
  final DateTime? updatedAt;

  DealModel({
    required this.id,
    required this.title,
    required this.source,
    required this.currentPrice,
    this.originalPrice,
    this.discountPercent,
    this.imageUrl,
    this.productUrl,
    required this.status,
    required this.verdict,
    required this.featured,
    required this.hidden,
    required this.views,
    this.rating,
    this.reviews,
    required this.addedAt,
    this.updatedAt,
  });

  factory DealModel.fromJson(Map<String, dynamic> json, [String? docId]) {
    return DealModel(
      id: docId ?? json['id'] as String? ?? 'unknown',
      title: json['title'] as String? ?? '',
      source: json['source'] as String? ?? 'unknown',
      currentPrice: (json['current_price'] as num?)?.toDouble() ?? 0.0,
      originalPrice: (json['original_price'] as num?)?.toDouble(),
      discountPercent: json['discount_percent'] as int?,
      imageUrl: json['image_url'] as String?,
      productUrl: json['product_url'] as String?,
      status: json['status'] as String? ?? 'active',
      verdict: json['verdict'] as String? ?? 'genuine',
      featured: json['featured'] as bool? ?? false,
      hidden: json['hidden'] as bool? ?? false,
      views: json['views'] as int? ?? 0,
      rating: (json['rating'] as num?)?.toDouble(),
      reviews: json['reviews'] as int?,
      addedAt: json['added_at'] is DateTime
          ? json['added_at'] as DateTime
          : DateTime.parse(json['added_at'] as String? ?? DateTime.now().toIso8601String()),
      updatedAt: json['updated_at'] != null
          ? json['updated_at'] is DateTime
              ? json['updated_at'] as DateTime
              : DateTime.parse(json['updated_at'] as String)
          : null,
    );
  }

  String get site => source;
  bool get isFeatured => featured;
  String get fakeVerdict => verdict;

  // Convert to JSON for Firestore
  Map<String, dynamic> toJson() {
    return {
      'title': title,
      'source': source,
      'current_price': currentPrice,
      'original_price': originalPrice,
      'discount_percent': discountPercent,
      'image_url': imageUrl,
      'product_url': productUrl,
      'status': status,
      'verdict': verdict,
      'featured': featured,
      'hidden': hidden,
      'views': views,
      'rating': rating,
      'reviews': reviews,
      'added_at': addedAt.toIso8601String(),
      'updated_at': updatedAt?.toIso8601String(),
    };
  }

  DealModel copyWith({
    String? id,
    String? title,
    String? source,
    double? currentPrice,
    double? originalPrice,
    int? discountPercent,
    String? imageUrl,
    String? productUrl,
    String? status,
    String? verdict,
    bool? featured,
    bool? hidden,
    int? views,
    double? rating,
    int? reviews,
    DateTime? addedAt,
    DateTime? updatedAt,
  }) {
    return DealModel(
      id: id ?? this.id,
      title: title ?? this.title,
      source: source ?? this.source,
      currentPrice: currentPrice ?? this.currentPrice,
      originalPrice: originalPrice ?? this.originalPrice,
      discountPercent: discountPercent ?? this.discountPercent,
      imageUrl: imageUrl ?? this.imageUrl,
      productUrl: productUrl ?? this.productUrl,
      status: status ?? this.status,
      verdict: verdict ?? this.verdict,
      featured: featured ?? this.featured,
      hidden: hidden ?? this.hidden,
      views: views ?? this.views,
      rating: rating ?? this.rating,
      reviews: reviews ?? this.reviews,
      addedAt: addedAt ?? this.addedAt,
      updatedAt: updatedAt ?? this.updatedAt,
    );
  }
}
