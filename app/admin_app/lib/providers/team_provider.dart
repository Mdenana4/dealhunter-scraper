// lib/providers/team_provider.dart

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:dio/dio.dart';
import '../models/admin_user.dart';
import '../services/api_client.dart';

// API client provider (assuming it exists)
final dioProvider = Provider<Dio>((ref) {
  return Dio(
    BaseOptions(
      baseUrl: 'https://dealhunter-scraper.onrender.com/api/v1',
      connectTimeout: const Duration(seconds: 10),
      receiveTimeout: const Duration(seconds: 10),
    ),
  );
});

/// Fetch all team members
final teamProvider = FutureProvider<List<AdminUser>>((ref) async {
  final dio = ref.watch(dioProvider);
  try {
    final response = await dio.get('/admin/team');
    final List<dynamic> data = response.data['data'] ?? response.data ?? [];
    return data
        .map((item) => AdminUser.fromJson(item as Map<String, dynamic>))
        .toList();
  } catch (e) {
    throw Exception('Failed to load team: $e');
  }
});

/// Add new team member
final addTeamMemberProvider =
    FutureProvider.family<void, AdminUser>((ref, admin) async {
  final dio = ref.watch(dioProvider);
  try {
    await dio.post(
      '/admin/team',
      data: {
        'email': admin.email,
        'name': admin.name,
        'role': admin.role,
        'permissions': admin.permissions,
        'status': admin.status,
      },
    );
    // Refresh team list after adding
    ref.refresh(teamProvider);
  } catch (e) {
    throw Exception('Failed to add team member: $e');
  }
});

/// Update team member
final updateTeamMemberProvider = FutureProvider.family<void,
    (String, Map<String, dynamic>)>((ref, params) async {
  final dio = ref.watch(dioProvider);
  final (email, updates) = params;
  try {
    await dio.put(
      '/admin/team/$email',
      data: updates,
    );
    // Refresh team list after updating
    ref.refresh(teamProvider);
  } catch (e) {
    throw Exception('Failed to update team member: $e');
  }
});

/// Remove team member
final removeTeamMemberProvider =
    FutureProvider.family<void, String>((ref, email) async {
  final dio = ref.watch(dioProvider);
  try {
    await dio.delete('/admin/team/$email');
    // Refresh team list after removing
    ref.refresh(teamProvider);
  } catch (e) {
    throw Exception('Failed to remove team member: $e');
  }
});

/// Get admin permissions
final adminPermissionsProvider =
    FutureProvider<List<String>>((ref) async {
  final dio = ref.watch(dioProvider);
  try {
    final response = await dio.get('/admin/permissions');
    final List<dynamic> data = response.data['permissions'] ?? [];
    return data.cast<String>();
  } catch (e) {
    throw Exception('Failed to load permissions: $e');
  }
});

/// Check specific permission for current admin
final checkPermissionProvider =
    FutureProvider.family<bool, String>((ref, resource) async {
  final dio = ref.watch(dioProvider);
  try {
    final response = await dio.get('/admin/check-permission/$resource');
    return response.data['allowed'] as bool? ?? false;
  } catch (e) {
    return false;
  }
});
