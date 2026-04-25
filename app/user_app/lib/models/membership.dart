import '../config/constants.dart';

enum MembershipTier { free, basic, premium, vip }

extension MembershipTierX on MembershipTier {
  String get id => name;

  String get displayName {
    switch (this) {
      case MembershipTier.free:    return 'Free';
      case MembershipTier.basic:   return 'Basic';
      case MembershipTier.premium: return 'Premium';
      case MembershipTier.vip:     return 'VIP';
    }
  }

  double get monthlyPrice => AppConstants.tierMonthlyPrice[id] ?? 0;
  int get dailyNotifications => AppConstants.tierDailyNotifications[id] ?? 10;
  int get historyDays => AppConstants.tierHistoryDays[id] ?? 30;
  int get maxSavedDeals => AppConstants.tierSavedDeals[id] ?? 10;

  bool get canFilterCategory => this != MembershipTier.free;
  bool get canSearchProduct  => this == MembershipTier.premium || this == MembershipTier.vip;
  bool get canFilterSize     => this == MembershipTier.premium || this == MembershipTier.vip;
  bool get hasAiRecommendations => this == MembershipTier.vip;

  String get scanFrequency {
    switch (this) {
      case MembershipTier.free:    return 'Every 30 minutes';
      case MembershipTier.basic:   return 'Every 10 minutes';
      case MembershipTier.premium: return 'Every 10 seconds';
      case MembershipTier.vip:     return 'Every 10 seconds';
    }
  }

  List<String> get features {
    switch (this) {
      case MembershipTier.free:
        return [
          'Up to ${dailyNotifications} deals/day',
          'Price history: ${historyDays} days',
          'Save up to ${maxSavedDeals} deals',
          'All categories (no filter)',
          'Basic deal alerts',
        ];
      case MembershipTier.basic:
        return [
          'Up to ${dailyNotifications} deals/day',
          'Price history: ${historyDays} days',
          'Save up to ${maxSavedDeals} deals',
          'Category filter',
          'Deal alerts with filters',
        ];
      case MembershipTier.premium:
        return [
          'Up to ${dailyNotifications} deals/day',
          'Price history: ${historyDays} days',
          'Unlimited saved deals',
          'Category + Size + Brand filter',
          'Product search across all stores',
          'Priority notifications',
        ];
      case MembershipTier.vip:
        return [
          'Unlimited deals/day',
          'Lifetime price history',
          'Unlimited saved deals',
          'All filters unlocked',
          'AI deal recommendations',
          'Instant notifications',
          'Priority support',
        ];
    }
  }

  static MembershipTier fromString(String? tier) {
    switch (tier?.toLowerCase()) {
      case 'basic':   return MembershipTier.basic;
      case 'premium': return MembershipTier.premium;
      case 'vip':     return MembershipTier.vip;
      default:        return MembershipTier.free;
    }
  }
}

class Membership {
  final MembershipTier tier;
  final DateTime? expiresAt;
  final String? billingCycle;   // 'monthly', '6months', 'yearly'
  final bool isActive;
  final double? customPrice;    // Admin override price

  const Membership({
    this.tier = MembershipTier.free,
    this.expiresAt,
    this.billingCycle,
    this.isActive = true,
    this.customPrice,
  });

  factory Membership.fromMap(Map<String, dynamic> map) => Membership(
    tier: MembershipTierX.fromString(map['tier'] as String?),
    expiresAt: map['expires_at'] != null
        ? DateTime.tryParse(map['expires_at'].toString())
        : null,
    billingCycle: map['billing_cycle'] as String?,
    isActive: map['is_active'] as bool? ?? true,
    customPrice: (map['custom_price'] as num?)?.toDouble(),
  );

  Map<String, dynamic> toMap() => {
    'tier':           tier.id,
    'expires_at':     expiresAt?.toIso8601String(),
    'billing_cycle':  billingCycle,
    'is_active':      isActive,
    'custom_price':   customPrice,
  };

  bool get isExpired =>
      expiresAt != null && expiresAt!.isBefore(DateTime.now());

  double get effectivePrice =>
      customPrice ?? tier.monthlyPrice;

  Membership copyWith({
    MembershipTier? tier,
    DateTime? expiresAt,
    String? billingCycle,
    bool? isActive,
    double? customPrice,
  }) => Membership(
    tier: tier ?? this.tier,
    expiresAt: expiresAt ?? this.expiresAt,
    billingCycle: billingCycle ?? this.billingCycle,
    isActive: isActive ?? this.isActive,
    customPrice: customPrice ?? this.customPrice,
  );
}
