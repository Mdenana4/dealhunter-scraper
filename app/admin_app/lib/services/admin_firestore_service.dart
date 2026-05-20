import 'package:cloud_firestore/cloud_firestore.dart';
import 'package:dio/dio.dart';

/// Central service for all admin Firestore operations.
/// Every read/write in the admin app goes through here.
class AdminFirestoreService {
  final FirebaseFirestore _db = FirebaseFirestore.instance;
  final _dio = Dio(BaseOptions(
    baseUrl: 'https://dealhunter-scraper.onrender.com',
    connectTimeout: const Duration(seconds: 10),
  ));

  // ─── ANALYTICS ────────────────────────────────────────────────────────────

  /// Live stream: total users + breakdown by tier
  Stream<Map<String, dynamic>> watchUserStats() {
    return _db.collection('users').snapshots().map((snap) {
      final docs = snap.docs;
      final tierCounts = <String, int>{
        'free': 0, 'basic': 0, 'premium': 0, 'vip': 0,
      };
      for (final doc in docs) {
        final tier = (doc.data()['membership'] as Map?)?['tier'] as String?
            ?? 'free';
        tierCounts[tier] = (tierCounts[tier] ?? 0) + 1;
      }
      return {
        'total': docs.length,
        'by_tier': tierCounts,
      };
    });
  }

  /// Live stream: scraper health latest cycle
  Stream<Map<String, dynamic>> watchScraperHealth() {
    return _db.collection('scraper_health').doc('latest').snapshots().map(
          (doc) => doc.data() ?? {},
        );
  }

  /// Live stream: recent price change events count in last 24h
  Stream<int> watchRecentChanges() {
    final since = DateTime.now().subtract(const Duration(hours: 24));
    return _db
        .collection('price_change_events')
        .where('timestamp', isGreaterThan: since.toIso8601String())
        .snapshots()
        .map((snap) => snap.size);
  }

  /// Recent analytics events (buy clicks, deal views)
  Future<Map<String, int>> getEventCounts({int hours = 24}) async {
    final since = DateTime.now().subtract(Duration(hours: hours));
    final snap = await _db
        .collection('analytics_events')
        .where('timestamp', isGreaterThan: since.toIso8601String())
        .get();

    final counts = <String, int>{};
    for (final doc in snap.docs) {
      final event = doc.data()['event'] as String? ?? 'unknown';
      counts[event] = (counts[event] ?? 0) + 1;
    }
    return counts;
  }

  // ─── USERS ────────────────────────────────────────────────────────────────

  Stream<List<Map<String, dynamic>>> watchUsers() {
    return _db
        .collection('users')
        .orderBy('created_at', descending: true)
        .snapshots()
        .map((snap) => snap.docs
            .map((d) => {'id': d.id, ...d.data()})
            .toList());
  }

  Future<Map<String, dynamic>?> getUser(String uid) async {
    final doc = await _db.collection('users').doc(uid).get();
    if (!doc.exists) return null;
    return {'id': doc.id, ...doc.data()!};
  }

  Future<void> updateUserMembership(String uid, {
    required String tier,
    double? customPrice,
    int? customDailyLimit,
    String? billingCycle,
  }) async {
    final data = <String, dynamic>{
      'membership.tier': tier,
      'last_updated_at': DateTime.now().toIso8601String(),
    };
    if (customPrice != null) data['membership.custom_price'] = customPrice;
    if (customDailyLimit != null) data['membership.custom_daily_limit'] = customDailyLimit;
    if (billingCycle != null) data['membership.billing_cycle'] = billingCycle;

    await _db.collection('users').doc(uid).update(data);
  }

  Future<void> updateUserField(String uid, String field, dynamic value) async {
    await _db.collection('users').doc(uid).update({
      field: value,
      'last_updated_at': DateTime.now().toIso8601String(),
    });
  }

  Future<void> deleteUser(String uid) async {
    await _db.collection('users').doc(uid).delete();
  }

  /// Bulk tier change for all users under a given tier
  Future<int> bulkChangeTier({
    required String fromTier,
    required String toTier,
    double? customPrice,
    int? customDailyLimit,
  }) async {
    final snap = await _db
        .collection('users')
        .where('membership.tier', isEqualTo: fromTier)
        .get();

    final batch = _db.batch();
    for (final doc in snap.docs) {
      final updates = <String, dynamic>{
        'membership.tier': toTier,
        'last_updated_at': DateTime.now().toIso8601String(),
      };
      if (customPrice != null) updates['membership.custom_price'] = customPrice;
      if (customDailyLimit != null) {
        updates['membership.custom_daily_limit'] = customDailyLimit;
      }
      batch.update(doc.reference, updates);
    }
    await batch.commit();
    return snap.docs.length;
  }

  // ─── GROUPS ───────────────────────────────────────────────────────────────

  Stream<List<Map<String, dynamic>>> watchGroups() {
    return _db
        .collection('user_groups')
        .orderBy('created_at', descending: true)
        .snapshots()
        .map((snap) => snap.docs
            .map((d) => {'id': d.id, ...d.data()})
            .toList());
  }

  Future<String> createGroup({
    required String name,
    required String description,
    String? tier,
    double? customPrice,
    int? customDailyLimit,
    List<String> memberUids = const [],
  }) async {
    final ref = await _db.collection('user_groups').add({
      'name': name,
      'description': description,
      'tier_override': tier,
      'custom_price': customPrice,
      'custom_daily_limit': customDailyLimit,
      'member_uids': memberUids,
      'created_at': DateTime.now().toIso8601String(),
      'updated_at': DateTime.now().toIso8601String(),
    });
    return ref.id;
  }

  Future<void> updateGroup(String groupId, Map<String, dynamic> data) async {
    data['updated_at'] = DateTime.now().toIso8601String();
    await _db.collection('user_groups').doc(groupId).update(data);
  }

  Future<void> deleteGroup(String groupId) async {
    await _db.collection('user_groups').doc(groupId).delete();
  }

  Future<void> addUserToGroup(String groupId, String uid) async {
    await _db.collection('user_groups').doc(groupId).update({
      'member_uids': FieldValue.arrayUnion([uid]),
    });
  }

  Future<void> removeUserFromGroup(String groupId, String uid) async {
    await _db.collection('user_groups').doc(groupId).update({
      'member_uids': FieldValue.arrayRemove([uid]),
    });
  }

  /// Apply group overrides to all current members
  Future<int> applyGroupOverridesToMembers(String groupId) async {
    final doc = await _db.collection('user_groups').doc(groupId).get();
    if (!doc.exists) return 0;
    final data = doc.data()!;
    final members = (data['member_uids'] as List?)?.cast<String>() ?? [];
    if (members.isEmpty) return 0;

    final batch = _db.batch();
    for (final uid in members) {
      final updates = <String, dynamic>{
        'last_updated_at': DateTime.now().toIso8601String(),
      };
      if (data['tier_override'] != null) {
        updates['membership.tier'] = data['tier_override'];
      }
      if (data['custom_price'] != null) {
        updates['membership.custom_price'] = data['custom_price'];
      }
      if (data['custom_daily_limit'] != null) {
        updates['membership.custom_daily_limit'] = data['custom_daily_limit'];
      }
      batch.update(_db.collection('users').doc(uid), updates);
    }
    await batch.commit();
    return members.length;
  }

  // ─── SOURCES ──────────────────────────────────────────────────────────────

  Stream<List<Map<String, dynamic>>> watchSources() {
    return _db
        .collection('sources')
        .orderBy('name')
        .snapshots()
        .map((snap) => snap.docs
            .map((d) => {'id': d.id, ...d.data()})
            .toList());
  }

  Future<String> addSource({
    required String name,
    required String marketplaceCountry,
    required String baseUrl,
    required String currency,
    String? logoUrl,
    bool enabled = true,
  }) async {
    final ref = await _db.collection('sources').add({
      'name': name,
      'marketplace_country': marketplaceCountry,
      'base_url': baseUrl,
      'currency': currency,
      'logo_url': logoUrl,
      'enabled': enabled,
      'products_count': 0,
      'last_scraped_at': null,
      'created_at': DateTime.now().toIso8601String(),
    });
    return ref.id;
  }

  Future<void> updateSource(String sourceId, Map<String, dynamic> data) async {
    await _db.collection('sources').doc(sourceId).update(data);
  }

  Future<void> toggleSource(String sourceId, bool enabled) async {
    await _db.collection('sources').doc(sourceId).update({'enabled': enabled});
  }

  Future<void> deleteSource(String sourceId) async {
    await _db.collection('sources').doc(sourceId).delete();
  }

  // ─── NOTIFICATIONS ────────────────────────────────────────────────────────

  /// Send FCM notification via the backend API (which has Admin SDK)
  Future<Map<String, dynamic>> sendNotification({
    required String title,
    required String body,
    String? imageUrl,
    required String targetType,  // 'all', 'tier', 'group', 'user'
    String? targetId,            // tier name, group id, or user uid
    Map<String, String>? data,
  }) async {
    final response = await _dio.post('/api/admin/notify', data: {
      'title': title,
      'body': body,
      'image_url': imageUrl,
      'target_type': targetType,
      'target_id': targetId,
      'data': data ?? {},
    });
    final result = response.data as Map<String, dynamic>;

    // Log to Firestore
    await _db.collection('notification_log').add({
      'title': title,
      'body': body,
      'target_type': targetType,
      'target_id': targetId,
      'sent_at': DateTime.now().toIso8601String(),
      'success_count': result['success_count'] ?? 0,
      'failure_count': result['failure_count'] ?? 0,
    });

    return result;
  }

  Stream<List<Map<String, dynamic>>> watchNotificationLog() {
    return _db
        .collection('notification_log')
        .orderBy('sent_at', descending: true)
        .limit(50)
        .snapshots()
        .map((snap) => snap.docs
            .map((d) => {'id': d.id, ...d.data()})
            .toList());
  }

  // ─── DEALS ────────────────────────────────────────────────────────────────

  /// Paginated deal fetch. Returns (docs, lastDocument) for cursor-based paging.
  Future<(List<Map<String, dynamic>>, DocumentSnapshot?)> getDeals({
    String? source,
    String? category,
    DocumentSnapshot? startAfter,
    int limit = 30,
  }) async {
    // Equality filters must come before orderBy to use composite indexes.
    Query<Map<String, dynamic>> q = _db.collection('deals');
    if (source != null)   q = q.where('site',     isEqualTo: source);
    if (category != null) q = q.where('category', isEqualTo: category);
    q = q.orderBy('timestamp', descending: true);
    if (startAfter != null) q = q.startAfterDocument(startAfter);
    q = q.limit(limit);

    final snap = await q.get();
    final docs = snap.docs
        .map((d) => <String, dynamic>{'id': d.id, ...d.data()})
        .toList();
    final last = snap.docs.isNotEmpty ? snap.docs.last : null;
    return (docs, last);
  }

  Future<void> deleteDeal(String dealId) async {
    await _db.collection('deals').doc(dealId).delete();
  }

  Future<void> flagDealAsFake(String dealId) async {
    await _db.collection('deals').doc(dealId).update({
      'fake_verdict':      'FAKE',
      'manually_flagged':  true,
      'flagged_at':        DateTime.now().toIso8601String(),
    });
  }

  // ─── SCRAPER HISTORY ──────────────────────────────────────────────────────

  /// Returns the last N scraper health cycles, newest first.
  Future<List<Map<String, dynamic>>> getScraperHistory({int limit = 8}) async {
    final snap = await _db
        .collection('scraper_health')
        .orderBy('timestamp', descending: true)
        .limit(limit + 1)   // fetch one extra to skip 'latest' if present
        .get();

    return snap.docs
        .where((d) => d.id != 'latest')
        .take(limit)
        .map((d) => <String, dynamic>{'id': d.id, ...d.data()})
        .toList();
  }
}
