import '../constants/api_endpoints.dart';
import '../models/user.dart';
import '../services/api_client.dart';
import '../services/secure_storage_service.dart';

/// AIB v1.0 Vol 13.3 repository layer — wraps ApiClient calls, returns
/// parsed domain models. Vol 13.13: "All backend interaction through
/// services/repositories" — screens never call ApiClient directly.
class AuthRepository {
  final ApiClient _client = ApiClient.instance;

  Future<UserProfile> register({
    required String fullName,
    required String email,
    required String phone,
    required String password,
  }) async {
    final response = await _client.post(
      ApiEndpoints.register,
      data: {'full_name': fullName, 'email': email, 'phone': phone, 'password': password},
    );
    return UserProfile.fromJson(response['data'] as Map<String, dynamic>);
  }

  /// Logs in and persists the JWT to secure storage (Vol 6.3 step 6:
  /// "Token stored securely by Flutter").
  Future<UserProfile> login({required String identifier, required String password}) async {
    final response = await _client.post(
      ApiEndpoints.login,
      data: {'identifier': identifier, 'password': password},
    );
    final data = response['data'] as Map<String, dynamic>;
    final token = AuthToken.fromJson(data);
    await SecureStorageService.instance.saveToken(token.accessToken);

    final userJson = data['user'] as Map<String, dynamic>;
    // /auth/login's `user` field is UserOut (no settings), while
    // /users/profile returns the full ProfileOut. Fetch the full
    // profile right after login so app state has settings from the start.
    return getProfile();
  }

  Future<UserProfile> getProfile() async {
    final response = await _client.get(ApiEndpoints.profile);
    return UserProfile.fromJson(response['data'] as Map<String, dynamic>);
  }

  Future<UserProfile> updateProfile({
    String? fullName,
    String? language,
    String? theme,
    bool? notifications,
  }) async {
    final response = await _client.put(
      ApiEndpoints.profile,
      data: {
        if (fullName != null) 'full_name': fullName,
        if (language != null) 'language': language,
        if (theme != null) 'theme': theme,
        if (notifications != null) 'notifications': notifications,
      },
    );
    return UserProfile.fromJson(response['data'] as Map<String, dynamic>);
  }

  /// Vol 6.3 step 8: "Logout removes local token."
  Future<void> logout() => SecureStorageService.instance.clearToken();

  Future<bool> hasStoredSession() async {
    final token = await SecureStorageService.instance.readToken();
    return token != null && token.isNotEmpty;
  }
}
