// lib/models/user.dart

class UserModel {
  final String id;
  final String email;
  final String? name;
  final String tier; // 'free', 'trial', 'premium', 'vip'
  final int dailyDealLimit;
  final DateTime registeredAt;
  final DateTime? lastLogin;
  final bool isActive;
  final String? groupName;
  final String? stripeCustomerId;

  UserModel({
    required this.id,
    required this.email,
    this.name,
    required this.tier,
    required this.dailyDealLimit,
    required this.registeredAt,
    this.lastLogin,
    required this.isActive,
    this.groupName,
    this.stripeCustomerId,
  });

  factory UserModel.fromJson(Map<String, dynamic> json, [String? docId]) {
    return UserModel(
      id: docId ?? json['id'] as String? ?? 'unknown',
      email: json['email'] as String? ?? '',
      name: json['name'] as String?,
      tier: json['tier'] as String? ?? 'free',
      dailyDealLimit: json['daily_deal_limit'] as int? ?? 50,
      registeredAt: json['registered_at'] is DateTime
          ? json['registered_at'] as DateTime
          : DateTime.parse(json['registered_at'] as String? ?? DateTime.now().toIso8601String()),
      lastLogin: json['last_login'] != null
          ? json['last_login'] is DateTime
              ? json['last_login'] as DateTime
              : DateTime.parse(json['last_login'] as String)
          : null,
      isActive: json['is_active'] as bool? ?? true,
      groupName: json['group_name'] as String?,
      stripeCustomerId: json['stripe_customer_id'] as String?,
    );
  }

  // Convert to JSON for Firestore
  Map<String, dynamic> toJson() {
    return {
      'email': email,
      'name': name,
      'tier': tier,
      'daily_deal_limit': dailyDealLimit,
      'registered_at': registeredAt.toIso8601String(),
      'last_login': lastLogin?.toIso8601String(),
      'is_active': isActive,
      'group_name': groupName,
      'stripe_customer_id': stripeCustomerId,
    };
  }

  UserModel copyWith({
    String? id,
    String? email,
    String? name,
    String? tier,
    int? dailyDealLimit,
    DateTime? registeredAt,
    DateTime? lastLogin,
    bool? isActive,
    String? groupName,
    String? stripeCustomerId,
  }) {
    return UserModel(
      id: id ?? this.id,
      email: email ?? this.email,
      name: name ?? this.name,
      tier: tier ?? this.tier,
      dailyDealLimit: dailyDealLimit ?? this.dailyDealLimit,
      registeredAt: registeredAt ?? this.registeredAt,
      lastLogin: lastLogin ?? this.lastLogin,
      isActive: isActive ?? this.isActive,
      groupName: groupName ?? this.groupName,
      stripeCustomerId: stripeCustomerId ?? this.stripeCustomerId,
    );
  }
}
