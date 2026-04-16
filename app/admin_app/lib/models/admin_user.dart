// lib/models/admin_user.dart

class AdminUser {
  final String email;
  final String name;
  final String role; // 'owner', 'editor', 'viewer'
  final List<String> permissions; // ['sources', 'deals', 'users', 'notifications', 'checker', 'competitors', 'scraper_control']
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

  bool get isActive => status == 'active';

  // Convert from Firestore document
  factory AdminUser.fromJson(Map<String, dynamic> json) {
    return AdminUser(
      email: json['email'] as String,
      name: json['name'] as String,
      role: json['role'] as String? ?? 'viewer',
      permissions: List<String>.from(json['permissions'] as List? ?? []),
      status: json['status'] as String? ?? 'active',
      addedAt: json['added_at'] is DateTime
          ? json['added_at'] as DateTime
          : DateTime.parse(json['added_at'] as String? ?? DateTime.now().toIso8601String()),
      addedBy: json['added_by'] as String,
      lastLogin: json['last_login'] != null
          ? json['last_login'] is DateTime
              ? json['last_login'] as DateTime
              : DateTime.parse(json['last_login'] as String)
          : null,
      notes: json['notes'] as String?,
    );
  }

  // Convert to JSON for Firestore
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

  // Copy with modifications
  AdminUser copyWith({
    String? email,
    String? name,
    String? role,
    List<String>? permissions,
    String? status,
    DateTime? addedAt,
    String? addedBy,
    DateTime? lastLogin,
    String? notes,
  }) {
    return AdminUser(
      email: email ?? this.email,
      name: name ?? this.name,
      role: role ?? this.role,
      permissions: permissions ?? this.permissions,
      status: status ?? this.status,
      addedAt: addedAt ?? this.addedAt,
      addedBy: addedBy ?? this.addedBy,
      lastLogin: lastLogin ?? this.lastLogin,
      notes: notes ?? this.notes,
    );
  }
}
