// lib/providers/notifications_provider.dart

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:dio/dio.dart';
import '../models/notification.dart';

// API client provider (reuse from team_provider)
final dioProvider = Provider<Dio>((ref) {
  return Dio(
    BaseOptions(
      baseUrl: 'https://dealhunter-scraper.onrender.com/api/v1',
      connectTimeout: const Duration(seconds: 10),
      receiveTimeout: const Duration(seconds: 10),
    ),
  );
});

/// Fetch notification history
final notificationsProvider =
    FutureProvider<List<NotificationModel>>((ref) async {
  final dio = ref.watch(dioProvider);
  try {
    final response = await dio.get('/admin/notifications');
    final List<dynamic> data = response.data['data'] ?? response.data ?? [];
    return data
        .map((item) => NotificationModel.fromJson(
            item as Map<String, dynamic>, item['id'] as String? ?? ''))
        .toList();
  } catch (e) {
    throw Exception('Failed to load notifications: $e');
  }
});

/// Send notification to users
final sendNotificationProvider = FutureProvider.family<void,
    Map<String, dynamic>>((ref, data) async {
  final dio = ref.watch(dioProvider);
  try {
    await dio.post(
      '/admin/notifications/send',
      data: {
        'title': data['title'],
        'message': data['message'],
        'target_type': data['target_type'],
        'target_tier': data['target_tier'],
        'target_group': data['target_group'],
      },
    );
    // Refresh notifications list after sending
    ref.refresh(notificationsProvider);
  } catch (e) {
    throw Exception('Failed to send notification: $e');
  }
});

/// Get notification analytics
final notificationAnalyticsProvider = FutureProvider.family<
    Map<String, dynamic>,
    String>((ref, notificationId) async {
  final dio = ref.watch(dioProvider);
  try {
    final response =
        await dio.get('/admin/notifications/$notificationId/analytics');
    return response.data as Map<String, dynamic>;
  } catch (e) {
    throw Exception('Failed to load notification analytics: $e');
  }
});

/// Get delivery status for a notification
final notificationDeliveryProvider =
    FutureProvider.family<Map<String, dynamic>, String>(
        (ref, notificationId) async {
  final dio = ref.watch(dioProvider);
  try {
    final response =
        await dio.get('/admin/notifications/$notificationId/delivery');
    return response.data as Map<String, dynamic>;
  } catch (e) {
    throw Exception('Failed to load delivery status: $e');
  }
});
