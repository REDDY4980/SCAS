/// Matches app/schemas/auth.py::ProfileOut exactly (Vol 6.9 full profile).
class UserProfile {
  final String id;
  final String fullName;
  final String email;
  final String phone;
  final DateTime createdAt;
  final String language;
  final String theme;
  final bool notifications;

  const UserProfile({
    required this.id,
    required this.fullName,
    required this.email,
    required this.phone,
    required this.createdAt,
    required this.language,
    required this.theme,
    required this.notifications,
  });

  factory UserProfile.fromJson(Map<String, dynamic> json) {
    return UserProfile(
      id: json['id'] as String,
      fullName: json['full_name'] as String,
      email: json['email'] as String,
      phone: json['phone'] as String,
      createdAt: DateTime.parse(json['created_at'] as String),
      language: (json['language'] as String?) ?? 'en',
      theme: (json['theme'] as String?) ?? 'system',
      notifications: (json['notifications'] as bool?) ?? true,
    );
  }
}

/// Matches app/schemas/auth.py::TokenResponse.
class AuthToken {
  final String accessToken;
  final String tokenType;
  final int expiresInMinutes;

  const AuthToken({
    required this.accessToken,
    required this.tokenType,
    required this.expiresInMinutes,
  });

  factory AuthToken.fromJson(Map<String, dynamic> json) {
    return AuthToken(
      accessToken: json['access_token'] as String,
      tokenType: (json['token_type'] as String?) ?? 'bearer',
      expiresInMinutes: (json['expires_in_minutes'] as num?)?.toInt() ?? 1440,
    );
  }
}
