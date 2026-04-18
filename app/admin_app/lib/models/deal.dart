class DealModel {
  final String id;
  final String title;
  final String description;
  final double price;
  final double? originalPrice;
  final String? source;
  final String? imageUrl;
  final String? fakeVerdict;
  final bool? isFeatured;
  final bool? isActive;
  final DateTime? createdAt;
  final DateTime? updatedAt;

  DealModel({
    required this.id,
    required this.title,
    required this.description,
    required this.price,
    this.originalPrice,
    this.source,
    this.imageUrl,
    this.fakeVerdict,
    this.isFeatured,
    this.isActive,
    this.createdAt,
    this.updatedAt,
  });

  factory DealModel.fromJson(Map<String, dynamic> json) {
    return DealModel(
      id: json['id'] as String,
      title: json['title'] as String? ?? '',
      description: json['description'] as String? ?? '',
      price: (json['price'] as num?)?.toDouble() ?? 0.0,
      originalPrice: (json['originalPrice'] as num?)?.toDouble(),
      source: json['source'] as String?,
      imageUrl: json['imageUrl'] as String?,
      fakeVerdict: json['fakeVerdict'] as String?,
      isFeatured: json['isFeatured'] as bool?,
      isActive: json['isActive'] as bool?,
      createdAt: json['createdAt'] != null
          ? DateTime.parse(json['createdAt'] as String)
          : null,
      updatedAt: json['updatedAt'] != null
          ? DateTime.parse(json['updatedAt'] as String)
          : null,
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'id': id,
      'title': title,
      'description': description,
      'price': price,
      'originalPrice': originalPrice,
      'source': source,
      'imageUrl': imageUrl,
      'fakeVerdict': fakeVerdict,
      'isFeatured': isFeatured,
      'isActive': isActive,
      'createdAt': createdAt?.toIso8601String(),
      'updatedAt': updatedAt?.toIso8601String(),
    };
  }
}
