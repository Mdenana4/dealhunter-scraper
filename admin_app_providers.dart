// lib/providers/auth_provider.dart
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../models/admin_user.dart';
import '../services/auth_service.dart';
import '../services/permission_service.dart';

final currentAdminEmailProvider = StateProvider<String?>((ref) => null);

final currentAdminProvider = FutureProvider<AdminUser?>((ref) async {
  final email = ref.watch(currentAdminEmailProvider);
  if (email == null) return null;

  final authService = ref.read(authServiceProvider);
  final storedEmail = await authService.getStoredEmail();

  if (storedEmail == null) return null;

  // In a real app, fetch from /api/v1/admin/check-auth endpoint
  // For now, return null - to be updated with actual API call
  return null;
});

final isAuthenticatedProvider = FutureProvider<bool>((ref) async {
  final admin = await ref.watch(currentAdminProvider.future);
  return admin != null;
});

// ============================================================================
// lib/providers/users_provider.dart
import '../models/user.dart';

class UserModel {
  final String id;
  final String email;
  final String? name;
  final String tier; // 'free', 'trial', 'premium', 'vip'
  final int dailyDealLimit;
  final DateTime registeredAt;
  final DateTime? lastLogin;
  final List<String>? referralsMade;
  final String? groupName;
  final int referralRewards;

  UserModel({
    required this.id,
    required this.email,
    this.name,
    required this.tier,
    required this.dailyDealLimit,
    required this.registeredAt,
    this.lastLogin,
    this.referralsMade,
    this.groupName,
    this.referralRewards = 0,
  });

  factory UserModel.fromJson(Map<String, dynamic> json) {
    return UserModel(
      id: json['id'] as String,
      email: json['email'] as String,
      name: json['name'] as String?,
      tier: json['tier'] as String? ?? 'free',
      dailyDealLimit: json['daily_deal_limit'] as int? ?? 50,
      registeredAt: DateTime.parse(json['registered_at'] as String),
      lastLogin: json['last_login'] != null
          ? DateTime.parse(json['last_login'] as String)
          : null,
      referralsMade: List<String>.from(json['referrals_made'] as List? ?? []),
      groupName: json['group_name'] as String?,
      referralRewards: json['referral_rewards'] as int? ?? 0,
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'id': id,
      'email': email,
      'name': name,
      'tier': tier,
      'daily_deal_limit': dailyDealLimit,
      'registered_at': registeredAt.toIso8601String(),
      'last_login': lastLogin?.toIso8601String(),
      'referrals_made': referralsMade,
      'group_name': groupName,
      'referral_rewards': referralRewards,
    };
  }
}

final usersProvider = FutureProvider<List<UserModel>>((ref) async {
  final api = ref.read(apiClientProvider);
  try {
    final response = await api.get('/admin/users');
    final List users = response.data['users'] ?? [];
    return users.map((u) => UserModel.fromJson(u as Map<String, dynamic>)).toList();
  } catch (e) {
    print('❌ Error fetching users: $e');
    rethrow;
  }
});

final usersSearchProvider = FutureProvider.family<List<UserModel>, String>((ref, query) async {
  final api = ref.read(apiClientProvider);
  try {
    final response = await api.get('/admin/users', queryParameters: {'search': query});
    final List users = response.data['users'] ?? [];
    return users.map((u) => UserModel.fromJson(u as Map<String, dynamic>)).toList();
  } catch (e) {
    print('❌ Error searching users: $e');
    return [];
  }
});

final updateUserProvider = FutureProvider.family<void, (String, Map<String, dynamic>)>((ref, args) async {
  final (userId, updates) = args;
  final api = ref.read(apiClientProvider);
  try {
    await api.put('/admin/users/$userId', data: updates);
    ref.refresh(usersProvider);
  } catch (e) {
    print('❌ Error updating user: $e');
    rethrow;
  }
});

final deleteUserProvider = FutureProvider.family<void, String>((ref, userId) async {
  final api = ref.read(apiClientProvider);
  try {
    await api.delete('/admin/users/$userId');
    ref.refresh(usersProvider);
  } catch (e) {
    print('❌ Error deleting user: $e');
    rethrow;
  }
});

// ============================================================================
// lib/providers/deals_provider.dart

class DealModel {
  final String id;
  final String title;
  final String imageUrl;
  final double currentPrice;
  final double originalPrice;
  final int discountPercent;
  final String site;
  final String category;
  final String status; // 'active', 'hidden', 'expired'
  final bool featured;
  final String fakeVerdict; // 'genuine', 'suspicious', 'fake'
  final DateTime addedAt;

  DealModel({
    required this.id,
    required this.title,
    required this.imageUrl,
    required this.currentPrice,
    required this.originalPrice,
    required this.discountPercent,
    required this.site,
    required this.category,
    required this.status,
    required this.featured,
    required this.fakeVerdict,
    required this.addedAt,
  });

  factory DealModel.fromJson(Map<String, dynamic> json) {
    return DealModel(
      id: json['id'] as String,
      title: json['title'] as String,
      imageUrl: json['image_url'] as String,
      currentPrice: (json['current_price'] as num).toDouble(),
      originalPrice: (json['original_price'] as num).toDouble(),
      discountPercent: json['discount_percent'] as int,
      site: json['site'] as String,
      category: json['category'] as String,
      status: json['status'] as String? ?? 'active',
      featured: json['featured'] as bool? ?? false,
      fakeVerdict: json['fake_verdict'] as String? ?? 'genuine',
      addedAt: DateTime.parse(json['added_at'] as String),
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'id': id,
      'title': title,
      'image_url': imageUrl,
      'current_price': currentPrice,
      'original_price': originalPrice,
      'discount_percent': discountPercent,
      'site': site,
      'category': category,
      'status': status,
      'featured': featured,
      'fake_verdict': fakeVerdict,
      'added_at': addedAt.toIso8601String(),
    };
  }

  bool get isActive => status == 'active';
  bool get isFeatured => featured;
  bool get isGeniune => fakeVerdict == 'genuine';
}

final dealsProvider = FutureProvider<List<DealModel>>((ref) async {
  final api = ref.read(apiClientProvider);
  try {
    final response = await api.get('/admin/deals');
    final List deals = response.data['deals'] ?? [];
    return deals.map((d) => DealModel.fromJson(d as Map<String, dynamic>)).toList();
  } catch (e) {
    print('❌ Error fetching deals: $e');
    rethrow;
  }
});

final updateDealProvider = FutureProvider.family<void, (String, Map<String, dynamic>)>((ref, args) async {
  final (dealId, updates) = args;
  final api = ref.read(apiClientProvider);
  try {
    await api.put('/admin/deals/$dealId', data: updates);
    ref.refresh(dealsProvider);
  } catch (e) {
    print('❌ Error updating deal: $e');
    rethrow;
  }
});

final deleteDealProvider = FutureProvider.family<void, String>((ref, dealId) async {
  final api = ref.read(apiClientProvider);
  try {
    await api.delete('/admin/deals/$dealId');
    ref.refresh(dealsProvider);
  } catch (e) {
    print('❌ Error deleting deal: $e');
    rethrow;
  }
});

// ============================================================================
// lib/providers/notifications_provider.dart

class NotificationModel {
  final String id;
  final String title;
  final String message;
  final String targetType; // 'all', 'tier', 'group', 'custom'
  final int sentCount;
  final int openedCount;
  final int failedCount;
  final DateTime sentAt;

  NotificationModel({
    required this.id,
    required this.title,
    required this.message,
    required this.targetType,
    required this.sentCount,
    required this.openedCount,
    required this.failedCount,
    required this.sentAt,
  });

  factory NotificationModel.fromJson(Map<String, dynamic> json) {
    return NotificationModel(
      id: json['id'] as String,
      title: json['title'] as String,
      message: json['message'] as String,
      targetType: json['target_type'] as String,
      sentCount: json['sent_count'] as int? ?? 0,
      openedCount: json['opened_count'] as int? ?? 0,
      failedCount: json['failed_count'] as int? ?? 0,
      sentAt: DateTime.parse(json['sent_at'] as String),
    );
  }
}

final sendNotificationProvider = FutureProvider.family<void, Map<String, dynamic>>((ref, data) async {
  final api = ref.read(apiClientProvider);
  try {
    await api.post('/admin/notifications/send', data: data);
    ref.refresh(notificationsProvider);
  } catch (e) {
    print('❌ Error sending notification: $e');
    rethrow;
  }
});

final notificationsProvider = FutureProvider<List<NotificationModel>>((ref) async {
  final api = ref.read(apiClientProvider);
  try {
    final response = await api.get('/admin/notifications');
    final List notifications = response.data['notifications'] ?? [];
    return notifications.map((n) => NotificationModel.fromJson(n as Map<String, dynamic>)).toList();
  } catch (e) {
    print('❌ Error fetching notifications: $e');
    rethrow;
  }
});

// ============================================================================
// lib/providers/analytics_provider.dart

class AnalyticsData {
  final int totalUsers;
  final int totalDeals;
  final double totalRevenue;
  final int activeSubscriptions;
  final List<int> userGrowthData; // 7 days
  final List<int> revenueData; // 7 days

  AnalyticsData({
    required this.totalUsers,
    required this.totalDeals,
    required this.totalRevenue,
    required this.activeSubscriptions,
    required this.userGrowthData,
    required this.revenueData,
  });

  factory AnalyticsData.fromJson(Map<String, dynamic> json) {
    return AnalyticsData(
      totalUsers: json['total_users'] as int? ?? 0,
      totalDeals: json['total_deals'] as int? ?? 0,
      totalRevenue: (json['total_revenue'] as num? ?? 0).toDouble(),
      activeSubscriptions: json['active_subscriptions'] as int? ?? 0,
      userGrowthData: List<int>.from(json['user_growth_data'] as List? ?? []),
      revenueData: List<int>.from(json['revenue_data'] as List? ?? []),
    );
  }
}

final analyticsProvider = FutureProvider<AnalyticsData>((ref) async {
  final api = ref.read(apiClientProvider);
  try {
    final response = await api.get('/admin/analytics');
    return AnalyticsData.fromJson(response.data);
  } catch (e) {
    print('❌ Error fetching analytics: $e');
    rethrow;
  }
});

// ============================================================================
// lib/providers/scraper_provider.dart

class ScraperStatus {
  final bool isRunning;
  final DateTime? lastRun;
  final DateTime? nextRun;
  final String? errorLog;
  final int dealsAddedToday;

  ScraperStatus({
    required this.isRunning,
    this.lastRun,
    this.nextRun,
    this.errorLog,
    required this.dealsAddedToday,
  });

  factory ScraperStatus.fromJson(Map<String, dynamic> json) {
    return ScraperStatus(
      isRunning: json['is_running'] as bool? ?? false,
      lastRun: json['last_run'] != null ? DateTime.parse(json['last_run'] as String) : null,
      nextRun: json['next_run'] != null ? DateTime.parse(json['next_run'] as String) : null,
      errorLog: json['error_log'] as String?,
      dealsAddedToday: json['deals_added_today'] as int? ?? 0,
    );
  }
}

final scraperStatusProvider = FutureProvider<ScraperStatus>((ref) async {
  final api = ref.read(apiClientProvider);
  try {
    final response = await api.get('/admin/scraper-status');
    return ScraperStatus.fromJson(response.data);
  } catch (e) {
    print('❌ Error fetching scraper status: $e');
    rethrow;
  }
});

final pauseScraperProvider = FutureProvider.family<void, String>((ref, reason) async {
  final api = ref.read(apiClientProvider);
  try {
    await api.post('/admin/scraper/pause', data: {'reason': reason});
    ref.refresh(scraperStatusProvider);
  } catch (e) {
    print('❌ Error pausing scraper: $e');
    rethrow;
  }
});

final resumeScraperProvider = FutureProvider<void>((ref) async {
  final api = ref.read(apiClientProvider);
  try {
    await api.post('/admin/scraper/resume');
    ref.refresh(scraperStatusProvider);
  } catch (e) {
    print('❌ Error resuming scraper: $e');
    rethrow;
  }
});

// ============================================================================
// lib/providers/team_provider.dart

final teamProvider = FutureProvider<List<AdminUser>>((ref) async {
  final api = ref.read(apiClientProvider);
  try {
    final response = await api.get('/admin/team');
    final List admins = response.data['admins'] ?? [];
    return admins.map((a) => AdminUser.fromJson(a as Map<String, dynamic>)).toList();
  } catch (e) {
    print('❌ Error fetching team: $e');
    rethrow;
  }
});

final addTeamMemberProvider = FutureProvider.family<void, AdminUser>((ref, admin) async {
  final api = ref.read(apiClientProvider);
  try {
    await api.post('/admin/team', data: admin.toJson());
    ref.refresh(teamProvider);
  } catch (e) {
    print('❌ Error adding team member: $e');
    rethrow;
  }
});

final updateTeamMemberProvider = FutureProvider.family<void, (String, Map<String, dynamic>)>((ref, args) async {
  final (email, updates) = args;
  final api = ref.read(apiClientProvider);
  try {
    await api.put('/admin/team/$email', data: updates);
    ref.refresh(teamProvider);
  } catch (e) {
    print('❌ Error updating team member: $e');
    rethrow;
  }
});

final removeTeamMemberProvider = FutureProvider.family<void, String>((ref, email) async {
  final api = ref.read(apiClientProvider);
  try {
    await api.delete('/admin/team/$email');
    ref.refresh(teamProvider);
  } catch (e) {
    print('❌ Error removing team member: $e');
    rethrow;
  }
});
