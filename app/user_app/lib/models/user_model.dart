class MembershipInfo {
  final String tier; // free | basic | premium | vip
  final String billingCycle;
  final DateTime? activatedAt;
  final String? gateway;

  const MembershipInfo({
    this.tier = 'free',
    this.billingCycle = 'monthly',
    this.activatedAt,
    this.gateway,
  });

  factory MembershipInfo.fromJson(Map<String, dynamic> json) {
    return MembershipInfo(
      tier: json['tier'] as String? ?? 'free',
      billingCycle: json['billing_cycle'] as String? ?? 'monthly',
      activatedAt: json['activated_at'] != null
          ? DateTime.tryParse(json['activated_at'] as String)
          : null,
      gateway: json['gateway'] as String?,
    );
  }

  bool get isFree => tier == 'free';
  bool get isPaid => !isFree;
  bool get isPremiumOrAbove => tier == 'premium' || tier == 'vip';

  int get priceHistoryDays => switch (tier) {
        'basic' => 60,
        'premium' => 180,
        'vip' => 9999,
        _ => 30,
      };

  int get savedDealsLimit => switch (tier) {
        'basic' => 50,
        'premium' => 999999,
        'vip' => 999999,
        _ => 10,
      };

  bool get canFilterCategory => !isFree;
  bool get canSearch => isPaid;

  String get displayLabel => switch (tier) {
        'basic' => 'Basic',
        'premium' => 'Premium',
        'vip' => 'VIP',
        _ => 'Free',
      };
}

class UserModel {
  final String uid;
  final String email;
  final String displayName;
  final MembershipInfo membership;
  final String? fcmToken;
  final String? referralCode;
  final List<String> savedDeals;
  final String country;
  final String language;

  const UserModel({
    required this.uid,
    required this.email,
    this.displayName = '',
    this.membership = const MembershipInfo(),
    this.fcmToken,
    this.referralCode,
    this.savedDeals = const [],
    this.country = 'AE',
    this.language = 'en',
  });

  factory UserModel.fromFirestore(String uid, Map<String, dynamic> data) {
    final mem = data['membership'];
    return UserModel(
      uid: uid,
      email: data['email'] as String? ?? '',
      displayName: data['display_name'] as String? ?? '',
      membership: mem is Map<String, dynamic>
          ? MembershipInfo.fromJson(mem)
          : const MembershipInfo(),
      fcmToken: data['fcm_token'] as String?,
      referralCode: data['referral_code'] as String?,
      savedDeals: (data['saved_deals'] as List?)
              ?.map((e) => e.toString())
              .toList() ??
          [],
      country: data['country'] as String? ?? 'AE',
      language: data['language'] as String? ?? 'en',
    );
  }

  bool hasSaved(String dealId) => savedDeals.contains(dealId);
}
