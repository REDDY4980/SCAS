/// Unified API exception.
///
/// AIB v1.0 Vol 13.10: "Display friendly messages. Handle network
/// failures gracefully." Every API call surfaces failures as this one
/// exception type so every screen can catch and display consistently,
/// rather than each screen handling raw DioException differently.
class ApiException implements Exception {
  final String message;
  final int? statusCode;
  final List<String> errors;
  final bool isNetworkError;

  const ApiException({
    required this.message,
    this.statusCode,
    this.errors = const [],
    this.isNetworkError = false,
  });

  factory ApiException.network() => const ApiException(
        message: 'Could not reach the server. Check your internet connection and try again.',
        isNetworkError: true,
      );

  factory ApiException.timeout() => const ApiException(
        message: 'The request took too long. Please try again.',
        isNetworkError: true,
      );

  factory ApiException.unauthorized() => const ApiException(
        message: 'Your session has expired. Please log in again.',
        statusCode: 401,
      );

  @override
  String toString() => message;
}
