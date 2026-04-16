// lib/services/api_client.dart
import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';

const String apiBaseUrl = 'https://dealhunter-scraper.onrender.com/api/v1';

final apiClientProvider = Provider<DioClient>((ref) {
  return DioClient();
});

class DioClient {
  late Dio dio;
  final secureStorage = const FlutterSecureStorage();

  DioClient() {
    dio = Dio(
      BaseOptions(
        baseUrl: apiBaseUrl,
        connectTimeout: const Duration(seconds: 10),
        receiveTimeout: const Duration(seconds: 10),
        headers: {
          'Content-Type': 'application/json',
        },
      ),
    );

    // Add interceptors
    dio.interceptors.add(
      InterceptorsWrapper(
        onRequest: (options, handler) async {
          // Add auth token to all requests
          final token = await secureStorage.read(key: 'admin_token');
          if (token != null) {
            options.headers['Authorization'] = 'Bearer $token';
          }
          return handler.next(options);
        },
        onError: (DioException e, handler) {
          // Handle 401 - token expired
          if (e.response?.statusCode == 401) {
            // Clear token and redirect to login
            secureStorage.delete(key: 'admin_token');
          }
          return handler.next(e);
        },
      ),
    );

    // Add logging
    dio.interceptors.add(LoggingInterceptor());
  }

  Future<Response> get(
    String path, {
    Map<String, dynamic>? queryParameters,
    Options? options,
  }) {
    return dio.get(
      path,
      queryParameters: queryParameters,
      options: options,
    );
  }

  Future<Response> post(
    String path, {
    dynamic data,
    Map<String, dynamic>? queryParameters,
    Options? options,
  }) {
    return dio.post(
      path,
      data: data,
      queryParameters: queryParameters,
      options: options,
    );
  }

  Future<Response> put(
    String path, {
    dynamic data,
    Map<String, dynamic>? queryParameters,
    Options? options,
  }) {
    return dio.put(
      path,
      data: data,
      queryParameters: queryParameters,
      options: options,
    );
  }

  Future<Response> delete(
    String path, {
    Map<String, dynamic>? queryParameters,
    Options? options,
  }) {
    return dio.delete(
      path,
      queryParameters: queryParameters,
      options: options,
    );
  }
}

class LoggingInterceptor extends Interceptor {
  @override
  void onRequest(RequestOptions options, RequestInterceptorHandler handler) {
    print('🌐 [${options.method}] ${options.baseUrl}${options.path}');
    if (options.data != null) {
      print('📤 Data: ${options.data}');
    }
    super.onRequest(options, handler);
  }

  @override
  void onResponse(Response response, ResponseInterceptorHandler handler) {
    print('✅ [${response.statusCode}] ${response.requestOptions.path}');
    super.onResponse(response, handler);
  }

  @override
  void onError(DioException err, ErrorInterceptorHandler handler) {
    print('❌ [${err.response?.statusCode}] ${err.message}');
    super.onError(err, handler);
  }
}

// ============================================================================
// lib/services/auth_service.dart
import 'package:firebase_auth/firebase_auth.dart';
import 'package:cloud_firestore/cloud_firestore.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';

final authServiceProvider = Provider<AuthService>((ref) {
  return AuthService();
});

class AuthService {
  final FirebaseAuth _auth = FirebaseAuth.instance;
  final FirebaseFirestore _firestore = FirebaseFirestore.instance;
  final secureStorage = const FlutterSecureStorage();

  Future<void> login(String email, String password) async {
    try {
      // Firebase auth
      final userCredential = await _auth.signInWithEmailAndPassword(
        email: email,
        password: password,
      );

      // Check if user is in admin_users collection
      final adminDoc = await _firestore
          .collection('admin_users')
          .doc(email)
          .get();

      if (!adminDoc.exists) {
        await _auth.signOut();
        throw Exception('User is not an admin');
      }

      // Get ID token and save it
      final idToken = await userCredential.user?.getIdToken();
      if (idToken != null) {
        await secureStorage.write(key: 'admin_token', value: idToken);
      }

      // Save admin data locally
      await secureStorage.write(
        key: 'admin_email',
        value: email,
      );

      print('✅ Admin login successful: $email');
    } on FirebaseAuthException catch (e) {
      if (e.code == 'user-not-found') {
        throw Exception('User not found');
      } else if (e.code == 'wrong-password') {
        throw Exception('Wrong password');
      }
      throw Exception('Login failed: ${e.message}');
    }
  }

  Future<void> logout() async {
    try {
      await _auth.signOut();
      await secureStorage.delete(key: 'admin_token');
      await secureStorage.delete(key: 'admin_email');
      print('✅ Admin logout successful');
    } catch (e) {
      throw Exception('Logout failed: $e');
    }
  }

  Future<String?> getStoredToken() async {
    return await secureStorage.read(key: 'admin_token');
  }

  Future<String?> getStoredEmail() async {
    return await secureStorage.read(key: 'admin_email');
  }

  Future<void> resetPassword(String email) async {
    try {
      await _auth.sendPasswordResetEmail(email: email);
      print('✅ Password reset email sent to $email');
    } catch (e) {
      throw Exception('Failed to send password reset: $e');
    }
  }
}

// ============================================================================
// lib/services/permission_service.dart
import 'package:cloud_firestore/cloud_firestore.dart';

final permissionServiceProvider = Provider<PermissionService>((ref) {
  return PermissionService();
});

class PermissionService {
  final FirebaseFirestore _firestore = FirebaseFirestore.instance;

  // Cache current admin data
  Map<String, dynamic>? _currentAdminCache;
  DateTime? _cacheExpiry;

  Future<Map<String, dynamic>?> getCurrentAdmin(String email) async {
    // Return cached if still valid
    if (_currentAdminCache != null && _cacheExpiry != null && DateTime.now().isBefore(_cacheExpiry!)) {
      return _currentAdminCache;
    }

    try {
      final doc = await _firestore
          .collection('admin_users')
          .doc(email)
          .get();

      if (doc.exists) {
        final data = doc.data() as Map<String, dynamic>;
        _currentAdminCache = data;
        _cacheExpiry = DateTime.now().add(const Duration(minutes: 5));
        return data;
      }
      return null;
    } catch (e) {
      print('❌ Error fetching admin: $e');
      return null;
    }
  }

  bool canAccessPage(String pageName, Map<String, dynamic> adminData) {
    final role = adminData['role'] as String?;
    final permissions = adminData['permissions'] as List? ?? [];

    // Owners can access everything
    if (role == 'owner') {
      return true;
    }

    // Map page names to required permissions
    const pagePermissions = {
      'dashboard': null, // Accessible to all authenticated admins
      'users': 'users',
      'deals': 'deals',
      'sources': 'sources',
      'notifications': 'notifications',
      'checker': 'checker',
      'competitors': 'competitors',
      'scraper_control': 'scraper_control',
      'team': 'team',
      'tiers': 'tiers',
      'analytics': 'analytics',
    };

    final requiredPerm = pagePermissions[pageName];
    if (requiredPerm == null) {
      return true; // No specific permission required
    }

    return permissions.contains(requiredPerm);
  }

  bool canEditDeal(Map<String, dynamic> adminData) {
    final permissions = adminData['permissions'] as List? ?? [];
    return adminData['role'] == 'owner' || permissions.contains('deals');
  }

  bool canManageUsers(Map<String, dynamic> adminData) {
    final permissions = adminData['permissions'] as List? ?? [];
    return adminData['role'] == 'owner' || permissions.contains('users');
  }

  bool canSendNotifications(Map<String, dynamic> adminData) {
    final permissions = adminData['permissions'] as List? ?? [];
    return adminData['role'] == 'owner' || permissions.contains('notifications');
  }

  bool canPauseScraper(Map<String, dynamic> adminData) {
    final permissions = adminData['permissions'] as List? ?? [];
    return adminData['role'] == 'owner' || permissions.contains('scraper_control');
  }

  bool canManageTeam(Map<String, dynamic> adminData) {
    return adminData['role'] == 'owner';
  }

  bool isViewer(Map<String, dynamic> adminData) {
    return adminData['role'] == 'viewer';
  }

  bool isEditor(Map<String, dynamic> adminData) {
    return adminData['role'] == 'editor';
  }

  bool isOwner(Map<String, dynamic> adminData) {
    return adminData['role'] == 'owner';
  }

  void clearCache() {
    _currentAdminCache = null;
    _cacheExpiry = null;
  }
}

// ============================================================================
// lib/models/admin_user.dart

class AdminUser {
  final String email;
  final String name;
  final String role; // 'owner', 'editor', 'viewer'
  final List<String> permissions;
  final String status; // 'active', 'inactive'
  final DateTime addedAt;
  final String addedBy;
  final DateTime? lastLogin;
  final String? notes;

  AdminUser({
    required this.email,
    required this.name,
    required this.role,
    required this.permissions,
    required this.status,
    required this.addedAt,
    required this.addedBy,
    this.lastLogin,
    this.notes,
  });

  factory AdminUser.fromJson(Map<String, dynamic> json) {
    return AdminUser(
      email: json['email'] as String,
      name: json['name'] as String,
      role: json['role'] as String? ?? 'editor',
      permissions: List<String>.from(json['permissions'] as List? ?? []),
      status: json['status'] as String? ?? 'active',
      addedAt: DateTime.parse(json['added_at'] as String),
      addedBy: json['added_by'] as String,
      lastLogin: json['last_login'] != null
          ? DateTime.parse(json['last_login'] as String)
          : null,
      notes: json['notes'] as String?,
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'email': email,
      'name': name,
      'role': role,
      'permissions': permissions,
      'status': status,
      'added_at': addedAt.toIso8601String(),
      'added_by': addedBy,
      'last_login': lastLogin?.toIso8601String(),
      'notes': notes,
    };
  }

  bool get isActive => status == 'active';
}
