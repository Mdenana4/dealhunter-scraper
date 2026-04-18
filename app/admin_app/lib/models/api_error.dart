class ApiError implements Exception {
  final String message;
  final String? details;
  final int? statusCode;
  final dynamic originalError;

  ApiError({
    required this.message,
    this.details,
    this.statusCode,
    this.originalError,
  });

  @override
  String toString() => message;

  String get displayMessage {
    if (statusCode == null) {
      return 'Connection failed: $message';
    }
    return 'Error $statusCode: $message';
  }
}
