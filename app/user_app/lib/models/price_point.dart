class PricePoint {
  final DateTime timestamp;
  final double price;
  final double? originalPrice;
  final double? discountPct;
  final bool inStock;
  final double? changeAmount;
  final double? changePct;

  const PricePoint({
    required this.timestamp,
    required this.price,
    this.originalPrice,
    this.discountPct,
    this.inStock = true,
    this.changeAmount,
    this.changePct,
  });

  factory PricePoint.fromMap(Map<String, dynamic> map) => PricePoint(
    timestamp: map['timestamp'] != null
        ? DateTime.tryParse(map['timestamp'].toString()) ?? DateTime.now()
        : DateTime.now(),
    price: (map['price'] as num?)?.toDouble() ?? 0,
    originalPrice: (map['original_price'] as num?)?.toDouble(),
    discountPct: (map['discount_pct'] as num?)?.toDouble(),
    inStock: map['in_stock'] as bool? ?? true,
    changeAmount: (map['change_amount'] as num?)?.toDouble(),
    changePct: (map['change_pct'] as num?)?.toDouble(),
  );

  bool get isPriceIncrease => (changeAmount ?? 0) > 0;
  bool get isPriceDecrease => (changeAmount ?? 0) < 0;
}

class PriceHistory {
  final String marketplaceCountry;
  final String productId;
  final String productName;
  final String currency;
  final List<PricePoint> points;
  final double? lowestPrice;
  final double? highestPrice;
  final double? averagePrice;
  final double? currentPrice;
  final String? priceTrend;  // 'rising', 'falling', 'stable'

  const PriceHistory({
    required this.marketplaceCountry,
    required this.productId,
    required this.productName,
    required this.currency,
    required this.points,
    this.lowestPrice,
    this.highestPrice,
    this.averagePrice,
    this.currentPrice,
    this.priceTrend,
  });

  factory PriceHistory.fromMap(Map<String, dynamic> map) {
    final rawPoints = (map['history'] as List?) ?? [];
    return PriceHistory(
      marketplaceCountry: map['marketplace_country'] as String? ?? '',
      productId: map['product_id'] as String? ?? '',
      productName: map['name'] as String? ?? '',
      currency: map['currency'] as String? ?? 'EGP',
      points: rawPoints
          .map((p) => PricePoint.fromMap(p as Map<String, dynamic>))
          .toList(),
      lowestPrice: (map['lowest_price'] as num?)?.toDouble(),
      highestPrice: (map['highest_price'] as num?)?.toDouble(),
      averagePrice: (map['average_price'] as num?)?.toDouble(),
      currentPrice: (map['current_price'] as num?)?.toDouble(),
      priceTrend: map['price_trend'] as String?,
    );
  }

  bool get isEmpty => points.isEmpty;
  int get dayCount => points.isEmpty
      ? 0
      : points.last.timestamp.difference(points.first.timestamp).inDays;
}
