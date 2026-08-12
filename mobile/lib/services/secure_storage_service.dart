import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:shared_preferences/shared_preferences.dart';

/// Secure local storage service.
///
/// AIB v1.0 Vol 13.7:
///   flutter_secure_storage: JWT, Refresh token (future)
///   SharedPreferences: Theme, Language, Recent farm selection
/// Vol 13.11: "Never store passwords. Store JWT securely."
class SecureStorageService {
  SecureStorageService._();
  static final SecureStorageService instance = SecureStorageService._();

  final _secureStorage = const FlutterSecureStorage(
    aOptions: AndroidOptions(encryptedSharedPreferences: true),
  );

  static const _tokenKey = 'scas_jwt_access_token';

  // On web, flutter_secure_storage encrypts every value via the Web
  // Crypto API and reads/writes go through IndexedDB — each of those
  // round trips can take tens of seconds, and concurrent reads (the
  // dashboard's farms/history/profile calls all fire near-simultaneously
  // on login) appear to serialize against each other, multiplying the
  // delay. The token itself never changes between requests in a
  // session, so it's safe to cache in memory after the first real read
  // and skip storage entirely on every subsequent request.
  String? _cachedToken;
  Future<String?>? _pendingRead;

  Future<void> saveToken(String token) async {
    _cachedToken = token;
    await _secureStorage.write(key: _tokenKey, value: token);
  }

  Future<String?> readToken() {
    if (_cachedToken != null) return Future.value(_cachedToken);
    return _pendingRead ??= _secureStorage.read(key: _tokenKey).then((token) {
      _cachedToken = token;
      _pendingRead = null;
      return token;
    });
  }

  Future<void> clearToken() async {
    _cachedToken = null;
    _pendingRead = null;
    await _secureStorage.delete(key: _tokenKey);
  }

  // --- Non-sensitive preferences (Vol 13.7: SharedPreferences) ---

  static const _recentFarmKey = 'scas_recent_farm_id';

  Future<void> saveRecentFarmId(String farmId) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(_recentFarmKey, farmId);
  }

  Future<String?> readRecentFarmId() async {
    final prefs = await SharedPreferences.getInstance();
    return prefs.getString(_recentFarmKey);
  }
}
