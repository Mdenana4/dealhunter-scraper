class UserModel {
  final String id;
  final String name;
  final String email;
  final String? tier;
  final String? status;
  final int? dailyLimit;
  final DateTime? createdAt;

  UserModel({
    required this.id,
    required this.name,
    required this.email,
    this.tier,
    this.status,
    this.dailyLimit,
    this.createdAt,
  });

  factory UserModel.fromJson(Map<String, dynamic> json) {
    return UserModel(
      id: json['id'] as String,
      name: json['name'] as String? ?? '',
      email: json['email'] as String? ?? '',
      tier: json['tier'] as String?,
      status: json['status'] as String?,
      dailyLimit: json['dailyLimit'] as int?,
      createdAt: json['createdAt'] != null
          ? DateTime.parse(json['createdAt'] as String)
          : null,
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'id': id,
      'name': name,
      'email': email,
      'tier': tier,
      'status': status,
      'dailyLimit': dailyLimit,
      'createdAt': createdAt?.toIso8601String(),
    };
  }
}
