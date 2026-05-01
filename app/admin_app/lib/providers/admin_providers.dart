import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../services/admin_firestore_service.dart';

final adminServiceProvider = Provider<AdminFirestoreService>(
    (_) => AdminFirestoreService());

// ─── Analytics ────────────────────────────────────────────────────────────

final userStatsProvider = StreamProvider<Map<String, dynamic>>((ref) =>
    ref.watch(adminServiceProvider).watchUserStats());

final scraperHealthProvider = StreamProvider<Map<String, dynamic>>((ref) =>
    ref.watch(adminServiceProvider).watchScraperHealth());

final recentChangesCountProvider = StreamProvider<int>((ref) =>
    ref.watch(adminServiceProvider).watchRecentChanges());

final eventCountsProvider = FutureProvider<Map<String, int>>((ref) =>
    ref.watch(adminServiceProvider).getEventCounts());

// ─── Users ────────────────────────────────────────────────────────────────

final usersStreamProvider =
    StreamProvider<List<Map<String, dynamic>>>((ref) =>
        ref.watch(adminServiceProvider).watchUsers());

// ─── Groups ───────────────────────────────────────────────────────────────

final groupsStreamProvider =
    StreamProvider<List<Map<String, dynamic>>>((ref) =>
        ref.watch(adminServiceProvider).watchGroups());

// ─── Sources ──────────────────────────────────────────────────────────────

final sourcesStreamProvider =
    StreamProvider<List<Map<String, dynamic>>>((ref) =>
        ref.watch(adminServiceProvider).watchSources());

// ─── Notification log ─────────────────────────────────────────────────────

final notificationLogProvider =
    StreamProvider<List<Map<String, dynamic>>>((ref) =>
        ref.watch(adminServiceProvider).watchNotificationLog());

// ─── Scraper history ──────────────────────────────────────────────────────

final scraperHistoryProvider =
    FutureProvider<List<Map<String, dynamic>>>((ref) =>
        ref.watch(adminServiceProvider).getScraperHistory());
