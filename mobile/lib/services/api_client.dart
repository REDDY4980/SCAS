import 'dart:typed_data';

import 'package:dio/dio.dart';

import '../config/app_config.dart';
import 'api_exception.dart';
import 'secure_storage_service.dart';

/// Central API client.
///
/// AIB v1.0 Vol 13.6: "Use Dio client. Central API service. JWT
/// automatically attached. Global timeout and retry policy. Unified
/// response/error parsing."
/// Vol 8.14 / Vol 14 directive that Flutter never calls external
/// services (OCR engines, weather providers) directly — every request
/// this client makes goes to the SCAS backend, which is the only thing
/// that ever talks to PaddleOCR/Open-Meteo/etc.
class ApiClient {
  ApiClient._internal() {
    _dio = Dio(
      BaseOptions(
        baseUrl: AppConfig.apiBaseUrl,
        connectTimeout: AppConfig.apiConnectTimeout,
        receiveTimeout: AppConfig.apiReceiveTimeout,
        headers: {'Accept': 'application/json'},
      ),
    );

    _dio.interceptors.add(
      InterceptorsWrapper(
        onRequest: (options, handler) async {
          final token = await SecureStorageService.instance.readToken();
          if (token != null) {
            options.headers['Authorization'] = 'Bearer $token';
          }
          handler.next(options);
        },
        onError: (DioException error, handler) {
          handler.next(error);
        },
      ),
    );
  }

  static final ApiClient instance = ApiClient._internal();

  late final Dio _dio;

  Dio get dio => _dio;

  /// Wraps every call site's try/catch into one place: converts any
  /// DioException into the app's unified ApiException (Vol 13.10).
  Future<Map<String, dynamic>> _unwrap(Future<Response<dynamic>> Function() request) async {
    try {
      final response = await request();
      final body = response.data;
      if (body is Map<String, dynamic>) {
        return body;
      }
      throw const ApiException(message: 'Unexpected response format from server.');
    } on DioException catch (e) {
      throw _mapDioException(e);
    }
  }

  ApiException _mapDioException(DioException e) {
    if (e.type == DioExceptionType.connectionTimeout ||
        e.type == DioExceptionType.sendTimeout ||
        e.type == DioExceptionType.receiveTimeout) {
      return ApiException.timeout();
    }
    if (e.type == DioExceptionType.connectionError) {
      return ApiException.network();
    }

    final statusCode = e.response?.statusCode;
    final body = e.response?.data;

    String message = 'Something went wrong. Please try again.';
    List<String> errors = const [];

    if (body is Map<String, dynamic>) {
      message = (body['message'] as String?) ?? message;
      final rawErrors = body['errors'];
      if (rawErrors is List) {
        errors = rawErrors.map((x) => x.toString()).toList();
      }
    }

    if (statusCode == 401) {
      return ApiException.unauthorized();
    }

    return ApiException(message: message, statusCode: statusCode, errors: errors);
  }

  Future<Map<String, dynamic>> get(String path, {Map<String, dynamic>? queryParameters}) {
    return _unwrap(() => _dio.get(path, queryParameters: queryParameters));
  }

  Future<Map<String, dynamic>> post(
    String path, {
    dynamic data,
    Map<String, dynamic>? queryParameters,
    Duration? receiveTimeout,
  }) {
    return _unwrap(
      () => _dio.post(
        path,
        data: data,
        queryParameters: queryParameters,
        // On web, dio's XHR adapter starts a *separate* timer for
        // connectTimeout that aborts the request if response headers
        // haven't arrived yet — independent of receiveTimeout. FastAPI
        // (like most non-streaming JSON APIs) doesn't emit headers until
        // the handler returns, so for a slow endpoint that timer fires
        // as a de facto "time to first byte" limit regardless of how
        // long receiveTimeout allows. Both must be raised together, or
        // the shorter default connectTimeout silently wins.
        options: receiveTimeout == null
            ? null
            : Options(connectTimeout: receiveTimeout, receiveTimeout: receiveTimeout),
      ),
    );
  }

  Future<Map<String, dynamic>> put(String path, {dynamic data}) {
    return _unwrap(() => _dio.put(path, data: data));
  }

  Future<Map<String, dynamic>> delete(String path) {
    return _unwrap(() => _dio.delete(path));
  }

  /// Multipart upload for soil report files (Vol 7.2: PDF/JPG/PNG, Vol
  /// 3 SCR-006). Uses a longer timeout than the default JSON endpoints.
  ///
  /// Takes raw bytes rather than a file path: `MultipartFile.fromFileSync`
  /// reads via `dart:io`, which throws `UnsupportedError` on Flutter web
  /// (there is no filesystem to read from) — `fromBytes` works identically
  /// on every platform since the caller already has the bytes in memory
  /// from image_picker/file_picker.
  Future<Map<String, dynamic>> uploadFile(
    String path, {
    required Uint8List bytes,
    required String fileName,
    required Map<String, dynamic> queryParameters,
  }) {
    return _unwrap(
      () => _dio.post(
        path,
        queryParameters: queryParameters,
        data: FormData.fromMap({
          'file': MultipartFile.fromBytes(bytes, filename: fileName),
        }),
        options: Options(sendTimeout: AppConfig.uploadTimeout, receiveTimeout: AppConfig.uploadTimeout),
      ),
    );
  }
}
