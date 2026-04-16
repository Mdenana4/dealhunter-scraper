// lib/models/notification.dart

class NotificationModel {
  final String id;
  final String title;
  final String message;
  final String targetType; // 'all', 'tier', 'group'
  final String? targetTier; // Used if targetType is 'tier'
  final String? targetGroup; // Used if targetType is 'group'
  final int sentCount;
  final DateTime sentAt;
  final String sentBy; // Email of admin who sent

  NotificationModel({
    required this.id,
    required this.title,
    required this.message,
    required this.targetType,
    this.targetTier,
    this.targetGroup,
    required this.sentCount,
    required this.sentAt,
    required this.sentBy,
  });

  // Convert from Firestore document
  factory NotificationModel.fromJson(Map<String, dynamic> json, String docId) {
    return NotificationModel(
      id: docId,
      title: json['title'] as String,
      message: json['message'] as String,
      targetType: json['target_type'] as String? ?? 'all',
      targetTier: json['target_tier'] as String?,
      targetGroup: json['target_group'] as String?,
      sentCount: json['sent_count'] as int? ?? 0,
      sentAt: json['sent_at'] is DateTime
          ? json['sent_at'] as DateTime
          : DateTime.parse(json['sent_at'] as String? ?? DateTime.now().toIso8601String()),
      sentBy: json['sent_by'] as String,
    );
  }

  // Convert to JSON for Firestore
  Map<String, dynamic> toJson() {
    return {
      'title': title,
      'message': message,
      'target_type': targetType,
      'target_tier': targetTier,
      'target_group': targetGroup,
      'sent_count': sentCount,
      'sent_at': sentAt.toIso8601String(),
      'sent_by': sentBy,
    };
  }

  NotificationModel copyWith({
    String? id,
    String? title,
    String? message,
    String? targetType,
    String? targetTier,
    String? targetGroup,
    int? sentCount,
    DateTime? sentAt,
    String? sentBy,
  }) {
    return NotificationModel(
      id: id ?? this.id,
      title: title ?? this.title,
      message: message ?? this.message,
      targetType: targetType ?? this.targetType,
      targetTier: targetTier ?? this.targetTier,
      targetGroup: targetGroup ?? this.targetGroup,
      sentCount: sentCount ?? this.sentCount,
      sentAt: sentAt ?? this.sentAt,
      sentBy: sentBy ?? this.sentBy,
    );
  }
}
