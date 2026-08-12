/// Standard API response envelope.
///
/// AIB v1.0 Vol 12.10 / Vol 14.3-14.4 — every backend response follows:
/// { success, message, data, errors, timestamp }
/// This mirrors app/schemas/common.py's success_response/error_response
/// exactly, field-for-field.
class ApiResponse<T> {
  final bool success;
  final String message;
  final T? data;
  final List<String> errors;
  final String timestamp;

  const ApiResponse({
    required this.success,
    required this.message,
    required this.data,
    required this.errors,
    required this.timestamp,
  });

  factory ApiResponse.fromJson(
    Map<String, dynamic> json,
    T Function(dynamic json)? fromData,
  ) {
    final rawData = json['data'];
    return ApiResponse<T>(
      success: json['success'] as bool? ?? false,
      message: json['message'] as String? ?? '',
      data: rawData == null || fromData == null ? null : fromData(rawData),
      errors: (json['errors'] as List<dynamic>? ?? const [])
          .map((e) => e.toString())
          .toList(),
      timestamp: json['timestamp'] as String? ?? '',
    );
  }
}
