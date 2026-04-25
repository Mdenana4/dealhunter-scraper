import 'membership.dart';

class UserProfile {
  final String uid;
  final String? email;
  final String? displayName;
  final String? photoUrl;
  final String? phone;
  final Membership membership;
  final NotificationPreferences notifications;
  final AppPreferences preferences;
  final UserStats stats;
  final String? referralCode;
  final String? referredBy;
  final DateTime createdAt;
  final DateTime? lastLoginAt;

  const UserProfile({
    required this.uid,
    this.email,
    this.displayName,
    this.photoUrl,
    this.phone,
    this.membership = const Membership(),
    this.notifications = const NotificationPreferences(),
    this.preferences = const AppPreferences(),
    this.stats = const UserStats(),
    this.referralCode,
    this.referredBy,
    required this.createdAt,
    this.lastLoginAt,
  });

  factory UserProfile.fromMap(String uid, Map<String, dynamic> map) => UserProfile(
    uid: uid,
    email: map['email'] as String?,
    displayName: map['display_name'] as String?,
    photoUrl: map['photo_url'] as String?,
    phone: map['phone'] as String?,
    membership: map['membership'] != null
        ? Membership.fromMap(map['membership'] as Map<String, dynamic>)
        : const Membership(),
    notifications: map['notifications'] != null
        ? NotificationPreferences.fromMap(map['notifications'] as Map<String, dynamic>)
        : const NotificationPreferences(),
    preferences: map['preferences'] != null
        ? AppPreferences.fromMap(map['preferences'] as Map<String, dynamic>)
        : const AppPreferences(),
    stats: map['stats'] != null
        ? UserStats.fromMap(map['stats'] as Map<String, dynamic>)
        : const UserStats(),
    referralCode: map['referral_code'] as String?,
    referredBy: map['referred_by'] as String?,
    createdAt: map['created_at'] != null
        ? DateTime.tryParse(map['created_at'].toString()) ?? DateTime.now()
        : DateTime.now(),
    lastLoginAt: map['last_login_at'] != null
        ? DateTime.tryParse(map['last_login_at'].toString())
        : null,
  );

  Map<String, dynamic> toMap() => {
    'email': email,
    'display_name': displayName,
    'photo_url': photoUrl,
    'phone': phone,
    'membership': membership.toMap(),
    'notifications': notifications.toMap(),
    'preferences': preferences.toMap(),
    'referral_code': referralCode,
    'referred_by': referredBy,
    'created_at': createdAt.toIso8601String(),
    'last_login_at': lastLoginAt?.toIso8601String(),
  };

  String get displayFirstName {
    if (displayName == null || displayName!.isEmpty) return 'User';
    return displayName!.split(' ').first;
  }

  UserProfile copyWith({
    Membership? membership,
    NotificationPreferences? notifications,
    AppPreferences? preferences,
    String? displayName,
    String? phone,
  }) => UserProfile(
    uid: uid,
    email: email,
    displayName: displayName ?? this.displayName,
    photoUrl: photoUrl,
    phone: phone ?? this.phone,
    membership: membership ?? this.membership,
    notifications: notifications ?? this.notifications,
    preferences: preferences ?? this.preferences,
    stats: stats,
    referralCode: referralCode,
    referredBy: referredBy,
    createdAt: createdAt,
    lastLoginAt: lastLoginAt,
  );
}

class NotificationPreferences {
  final bool enabled;
  final bool quietHours;
  final int quietStart; // 23 = 11 PM
  final int quietEnd;   // 7  = 7 AM
  final double minDiscountPct;
  final List<String> categories;
  final List<String> brands;
  final List<String> sizes;
  final List<String> marketplaces;
  final bool groupNotifications;

  const NotificationPreferences({
    this.enabled = true,
    this.quietHours = true,
    this.quietStart = 23,
    this.quietEnd = 7,
    this.minDiscountPct = 40.0,
    this.categories = const [],
    this.brands = const [],
    this.sizes = const [],
    this.marketplaces = const [],
    this.groupNotifications = true,
  });

  factory NotificationPreferences.fromMap(Map<String, dynamic> map) =>
      NotificationPreferences(
        enabled: map['enabled'] as bool? ?? true,
        quietHours: map['quiet_hours'] as bool? ?? true,
        quietStart: map['quiet_start'] as int? ?? 23,
        quietEnd: map['quiet_end'] as int? ?? 7,
        minDiscountPct: (map['min_discount_pct'] as num?)?.toDouble() ?? 40.0,
        categories: (map['categories'] as List?)?.cast<String>() ?? [],
        brands: (map['brands'] as List?)?.cast<String>() ?? [],
        sizes: (map['sizes'] as List?)?.cast<String>() ?? [],
        marketplaces: (map['marketplaces'] as List?)?.cast<String>() ?? [],
        groupNotifications: map['group_notifications'] as bool? ?? true,
      );

  Map<String, dynamic> toMap() => {
    'enabled': enabled,
    'quiet_hours': quietHours,
    'quiet_start': quietStart,
    'quiet_end': quietEnd,
    'min_discount_pct': minDiscountPct,
    'categories': categories,
    'brands': brands,
    'sizes': sizes,
    'marketplaces': marketplaces,
    'group_notifications': groupNotifications,
  };
}

class AppPreferences {
  final String language;  // 'en' or 'ar'
  final String theme;     // 'light', 'dark', 'system'
  final String currency;  // 'EGP', 'AED', 'SAR'
  final String country;   // 'eg', 'ae', 'sa'

  const AppPreferences({
    this.language = 'en',
    this.theme = 'system',
    this.currency = 'EGP',
    this.country = 'eg',
  });

  factory AppPreferences.fromMap(Map<String, dynamic> map) => AppPreferences(
    language: map['language'] as String? ?? 'en',
    theme: map['theme'] as String? ?? 'system',
    currency: map['currency'] as String? ?? 'EGP',
    country: map['country'] as String? ?? 'eg',
  );

  Map<String, dynamic> toMap() => {
    'language': language,
    'theme': theme,
    'currency': currency,
    'country': country,
  };
}

class UserStats {
  final int dealsViewed;
  final int dealsSaved;
  final int dealsClicked;      // "Buy" button taps
  final int dealsPurchased;    // "Did you buy?" confirmed
  final int referralsCount;

  const UserStats({
    this.dealsViewed = 0,
    this.dealsSaved = 0,
    this.dealsClicked = 0,
    this.dealsPurchased = 0,
    this.referralsCount = 0,
  });

  factory UserStats.fromMap(Map<String, dynamic> map) => UserStats(
    dealsViewed: map['deals_viewed'] as int? ?? 0,
    dealsSaved: map['deals_saved'] as int? ?? 0,
    dealsClicked: map['deals_clicked'] as int? ?? 0,
    dealsPurchased: map['deals_purchased'] as int? ?? 0,
    referralsCount: map['referrals_count'] as int? ?? 0,
  );
}
