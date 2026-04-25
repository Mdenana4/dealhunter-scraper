class Deal {
  final String id;
  final String productId;
  final String marketplaceCountry;
  final String storeName;
  final String name;
  final String? brand;
  final String? category;
  final String url;
  final String? imageUrl;
  final double currentPrice;
  final double? originalPrice;
  final double discountPct;
  final String currency;
  final bool inStock;
  final DateTime foundAt;
  final bool isSaved;
  final VerificationSummary? verification;

  const Deal({
    required this.id,
    required this.productId,
    required this.marketplaceCountry,
    required this.storeName,
    required this.name,
    this.brand,
    this.category,
    required this.url,
    this.imageUrl,
    required this.currentPrice,
    this.originalPrice,
    required this.discountPct,
    required this.currency,
    this.inStock = true,
    required this.foundAt,
    this.isSaved = false,
    this.verification,
  });

  factory Deal.fromMap(Map<String, dynamic> map) => Deal(
    id: map['id'] as String? ?? map['deal_id'] as String? ?? '',
    productId: map['product_id'] as String? ?? '',
    marketplaceCountry: map['marketplace_country'] as String? ?? '',
    storeName: map['store_name'] as String? ?? map['site'] as String? ?? '',
    name: map['name'] as String? ?? map['deal_title'] as String? ?? '',
    brand: map['brand'] as String?,
    category: map['category'] as String?,
    url: map['url'] as String? ?? map['product_url'] as String? ?? '',
    imageUrl: map['image_url'] as String?,
    currentPrice: (map['current_price'] as num?)?.toDouble() ??
                  (map['deal_price'] as num?)?.toDouble() ?? 0,
    originalPrice: (map['original_price'] as num?)?.toDouble() ??
                   (map['original'] as num?)?.toDouble(),
    discountPct: (map['discount_pct'] as num?)?.toDouble() ??
                 (map['discount_percent'] as num?)?.toDouble() ?? 0,
    currency: map['currency'] as String? ?? 'EGP',
    inStock: map['in_stock'] as bool? ?? true,
    foundAt: map['found_at'] != null
        ? DateTime.tryParse(map['found_at'].toString()) ?? DateTime.now()
        : DateTime.now(),
    isSaved: map['is_saved'] as bool? ?? false,
    verification: map['verification'] != null
        ? VerificationSummary.fromMap(map['verification'] as Map<String, dynamic>)
        : null,
  );

  Map<String, dynamic> toMap() => {
    'id': id,
    'product_id': productId,
    'marketplace_country': marketplaceCountry,
    'store_name': storeName,
    'name': name,
    'brand': brand,
    'category': category,
    'url': url,
    'image_url': imageUrl,
    'current_price': currentPrice,
    'original_price': originalPrice,
    'discount_pct': discountPct,
    'currency': currency,
    'in_stock': inStock,
    'found_at': foundAt.toIso8601String(),
    'is_saved': isSaved,
  };

  String get formattedPrice => '${currency} ${currentPrice.toStringAsFixed(0)}';
  String get formattedOriginalPrice =>
      originalPrice != null ? '${currency} ${originalPrice!.toStringAsFixed(0)}' : '';
  String get discountLabel => '-${discountPct.toStringAsFixed(0)}%';
  String get savingAmount => originalPrice != null
      ? '${currency} ${(originalPrice! - currentPrice).toStringAsFixed(0)}'
      : '';

  Deal copyWith({bool? isSaved, VerificationSummary? verification}) => Deal(
    id: id,
    productId: productId,
    marketplaceCountry: marketplaceCountry,
    storeName: storeName,
    name: name,
    brand: brand,
    category: category,
    url: url,
    imageUrl: imageUrl,
    currentPrice: currentPrice,
    originalPrice: originalPrice,
    discountPct: discountPct,
    currency: currency,
    inStock: inStock,
    foundAt: foundAt,
    isSaved: isSaved ?? this.isSaved,
    verification: verification ?? this.verification,
  );
}

class VerificationSummary {
  final String verdict;       // 'genuine', 'fake', 'uncertain'
  final int confidence;       // 0-100
  final String explanation;
  final List<String> redFlags;
  final String recommendation; // 'buy_now', 'not_recommended', 'check_history'

  const VerificationSummary({
    required this.verdict,
    required this.confidence,
    required this.explanation,
    this.redFlags = const [],
    required this.recommendation,
  });

  factory VerificationSummary.fromMap(Map<String, dynamic> map) => VerificationSummary(
    verdict: map['verdict'] as String? ?? 'uncertain',
    confidence: (map['confidence'] as num?)?.toInt() ?? 0,
    explanation: map['explanation'] as String? ?? '',
    redFlags: (map['red_flags'] as List?)?.cast<String>() ?? [],
    recommendation: map['recommendation'] as String? ?? 'check_history',
  );

  bool get isGenuine   => verdict == 'genuine';
  bool get isFake      => verdict == 'fake';
  bool get isUncertain => verdict == 'uncertain';
}
