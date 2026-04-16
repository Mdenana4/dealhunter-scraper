// lib/providers/users_provider.dart

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:dio/dio.dart';
import '../models/user.dart';

// API client provider
final dioProvider = Provider<Dio>((ref) {
  return Dio(
    BaseOptions(
      baseUrl: 'https://dealhunter-scraper.onrender.com/api/v1',
      connectTimeout: const Duration(seconds: 10),
      receiveTimeout: const Duration(seconds: 10),
    ),
  );
});

/// Fetch all users
final usersProvider = FutureProvider<List<UserModel>>((ref) async {
  final dio = ref.watch(dioProvider);
  try {
    final response = await dio.get('/admin/users');
    final List<dynamic> data = response.data['data'] ?? response.data ?? [];
    return data
        .map((item) => UserModel.fromJson(
            item as Map<String, dynamic>, item['id'] as String? ?? ''))
        .toList();
  } catch (e) {
    throw Exception('Failed to load users: $e');
  }
});

/// Get single user by ID
final userDetailProvider = FutureProvider.family<UserModel, String>(
    (ref, userId) async {
  final dio = ref.watch(dioProvider);
  try {
    final response = await dio.get('/admin/users/$userId');
    return UserModel.fromJson(response.data as Map<String, dynamic>, userId);
  } catch (e) {
    throw Exception('Failed to load user: $e');
  }
});

/// Update user
final updateUserProvider = FutureProvider.family<void,
    (String, Map<String, dynamic>)>((ref, params) async {
  final dio = ref.watch(dioProvider);
  final (userId, updates) = params;
  try {
    await dio.put(
      '/admin/users/$userId',
      data: updates,
    );
    // Refresh users list after updating
    ref.refresh(usersProvider);
  } catch (e) {
    throw Exception('Failed to update user: $e');
  }
});

/// Delete user
final deleteUserProvider =
    FutureProvider.family<void, String>((ref, userId) async {
  final dio = ref.watch(dioProvider);
  try {
    await dio.delete('/admin/users/$userId');
    // Refresh users list after deleting
    ref.refresh(usersProvider);
  } catch (e) {
    throw Exception('Failed to delete user: $e');
  }
});

/// Upgrade/downgrade user tier
final changeUserTierProvider = FutureProvider.family<void,
    (String, String, String)>((ref, params) async {
  final dio = ref.watch(dioProvider);
  final (userId, newTier, reason) = params;
  try {
    await dio.post(
      '/admin/users/$userId/tier',
      data: {
        'new_tier': newTier,
        'reason': reason,
      },
    );
    // Refresh users list after tier change
    ref.refresh(usersProvider);
  } catch (e) {
    throw Exception('Failed to change user tier: $e');
  }
});

/// Grant referral reward to user
final grantReferralRewardProvider = FutureProvider.family<void,
    (String, int, String)>((ref, params) async {
  final dio = ref.watch(dioProvider);
  final (userId, amount, reason) = params;
  try {
    await dio.post(
      '/admin/users/$userId/reward',
      data: {
        'reward_amount': amount,
        'reason': reason,
      },
    );
    // Refresh users list
    ref.refresh(usersProvider);
  } catch (e) {
    throw Exception('Failed to grant reward: $e');
  }
});

/// Get user referral statistics
final userReferralsProvider = FutureProvider.family<Map<String, dynamic>,
    String>((ref, userId) async {
  final dio = ref.watch(dioProvider);
  try {
    final response = await dio.get('/admin/users/$userId/referrals');
    return response.data as Map<String, dynamic>;
  } catch (e) {
    throw Exception('Failed to load referrals: $e');
  }
});

/// Search users
final searchUsersProvider = FutureProvider.family<List<UserModel>, String>(
    (ref, query) async {
  if (query.isEmpty) {
    return ref.watch(usersProvider);
  }

  final dio = ref.watch(dioProvider);
  try {
    final response =
        await dio.get('/admin/users/search', queryParameters: {'q': query});
    final List<dynamic> data = response.data['data'] ?? [];
    return data
        .map((item) => UserModel.fromJson(
            item as Map<String, dynamic>, item['id'] as String? ?? ''))
        .toList();
  } catch (e) {
    // Fall back to client-side filtering
    final allUsers = await ref.watch(usersProvider.future);
    final lowerQuery = query.toLowerCase();
    return allUsers
        .where((user) =>
            user.email.toLowerCase().contains(lowerQuery) ||
            (user.name?.toLowerCase().contains(lowerQuery) ?? false))
        .toList();
  }
});
