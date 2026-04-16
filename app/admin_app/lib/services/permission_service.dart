// lib/services/permission_service.dart

import 'package:flutter_riverpod/flutter_riverpod.dart';

/// Permission service for role-based access control
class PermissionService {
  /// Check if current admin can access a specific page
  bool canAccessPage(String pageName, Map<String, dynamic> currentAdmin) {
    // If admin map is empty or null, deny access
    if (currentAdmin.isEmpty) return false;

    final role = currentAdmin['role'] as String? ?? 'viewer';
    final permissions = (currentAdmin['permissions'] as List?)?.cast<String>() ?? [];

    // Owner has full access
    if (role == 'owner') return true;

    // Viewer has read-only access to all pages
    if (role == 'viewer') return true;

    // Editor needs specific permission
    if (role == 'editor') {
      const pagePermissions = {
        'users': 'users',
        'deals': 'deals',
        'sources': 'sources',
        'notifications': 'notifications',
        'checker': 'checker',
        'competitors': 'competitors',
        'scraper_control': 'scraper_control',
        'team': 'team', // Editors cannot manage team
        'dashboard': null, // Dashboard accessible to all
      };

      final requiredPerm = pagePermissions[pageName];
      if (requiredPerm == null) return true; // No permission required
      if (requiredPerm == 'team') return false; // Editors cannot manage team

      return permissions.contains(requiredPerm);
    }

    return false;
  }

  /// Check if admin can manage team (Owner only)
  bool canManageTeam(Map<String, dynamic> currentAdmin) {
    if (currentAdmin.isEmpty) return false;
    final role = currentAdmin['role'] as String? ?? 'viewer';
    return role == 'owner';
  }

  /// Check if admin can manage users
  bool canManageUsers(Map<String, dynamic> currentAdmin) {
    if (currentAdmin.isEmpty) return false;

    final role = currentAdmin['role'] as String? ?? 'viewer';
    if (role == 'owner') return true;
    if (role == 'viewer') return false;

    final permissions = (currentAdmin['permissions'] as List?)?.cast<String>() ?? [];
    return permissions.contains('users');
  }

  /// Check if admin can manage deals
  bool canManageDeals(Map<String, dynamic> currentAdmin) {
    if (currentAdmin.isEmpty) return false;

    final role = currentAdmin['role'] as String? ?? 'viewer';
    if (role == 'owner') return true;
    if (role == 'viewer') return false;

    final permissions = (currentAdmin['permissions'] as List?)?.cast<String>() ?? [];
    return permissions.contains('deals');
  }

  /// Check if admin can send notifications
  bool canSendNotifications(Map<String, dynamic> currentAdmin) {
    if (currentAdmin.isEmpty) return false;

    final role = currentAdmin['role'] as String? ?? 'viewer';
    if (role == 'owner') return true;
    if (role == 'viewer') return false;

    final permissions = (currentAdmin['permissions'] as List?)?.cast<String>() ?? [];
    return permissions.contains('notifications');
  }

  /// Check if admin can manage sources
  bool canManageSources(Map<String, dynamic> currentAdmin) {
    if (currentAdmin.isEmpty) return false;

    final role = currentAdmin['role'] as String? ?? 'viewer';
    if (role == 'owner') return true;
    if (role == 'viewer') return false;

    final permissions = (currentAdmin['permissions'] as List?)?.cast<String>() ?? [];
    return permissions.contains('sources');
  }

  /// Check if admin can run fake checker
  bool canRunChecker(Map<String, dynamic> currentAdmin) {
    if (currentAdmin.isEmpty) return false;

    final role = currentAdmin['role'] as String? ?? 'viewer';
    if (role == 'owner') return true;
    if (role == 'viewer') return false;

    final permissions = (currentAdmin['permissions'] as List?)?.cast<String>() ?? [];
    return permissions.contains('checker');
  }

  /// Check if admin can view competitors
  bool canViewCompetitors(Map<String, dynamic> currentAdmin) {
    if (currentAdmin.isEmpty) return false;

    final role = currentAdmin['role'] as String? ?? 'viewer';
    if (role == 'owner') return true;
    if (role == 'viewer') return false;

    final permissions = (currentAdmin['permissions'] as List?)?.cast<String>() ?? [];
    return permissions.contains('competitors');
  }

  /// Check if admin can control scraper
  bool canControlScraper(Map<String, dynamic> currentAdmin) {
    if (currentAdmin.isEmpty) return false;

    final role = currentAdmin['role'] as String? ?? 'viewer';
    if (role == 'owner') return true;
    if (role == 'viewer') return false;

    final permissions = (currentAdmin['permissions'] as List?)?.cast<String>() ?? [];
    return permissions.contains('scraper_control');
  }

  /// Get list of accessible pages for admin
  List<String> getAccessiblePages(Map<String, dynamic> currentAdmin) {
    if (currentAdmin.isEmpty) return [];

    final role = currentAdmin['role'] as String? ?? 'viewer';
    final permissions = (currentAdmin['permissions'] as List?)?.cast<String>() ?? [];

    const allPages = [
      'dashboard',
      'users',
      'deals',
      'sources',
      'notifications',
      'checker',
      'competitors',
      'scraper_control',
    ];

    if (role == 'owner') return allPages;
    if (role == 'viewer') return allPages;

    // Editor: all pages except team, plus permission-based filtering
    return allPages.where((page) {
      if (page == 'dashboard') return true;
      const pagePermissions = {
        'users': 'users',
        'deals': 'deals',
        'sources': 'sources',
        'notifications': 'notifications',
        'checker': 'checker',
        'competitors': 'competitors',
        'scraper_control': 'scraper_control',
      };
      final requiredPerm = pagePermissions[page];
      return requiredPerm == null || permissions.contains(requiredPerm);
    }).toList();
  }
}

/// Riverpod provider for PermissionService
final permissionServiceProvider = Provider<PermissionService>((ref) {
  return PermissionService();
});
