import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../models/user.dart';
import '../repositories/auth_repository.dart';
import '../services/api_exception.dart';
import 'repository_providers.dart';

/// AIB v1.0 Vol 13.4: "Responsibilities: Authentication state..."
sealed class AuthState {
  const AuthState();
}

class AuthInitial extends AuthState {
  const AuthInitial();
}

class AuthLoading extends AuthState {
  const AuthLoading();
}

class AuthAuthenticated extends AuthState {
  final UserProfile user;
  const AuthAuthenticated(this.user);
}

class AuthUnauthenticated extends AuthState {
  const AuthUnauthenticated();
}

class AuthError extends AuthState {
  final String message;
  const AuthError(this.message);
}

class AuthNotifier extends StateNotifier<AuthState> {
  final AuthRepository _repo;
  AuthNotifier(this._repo) : super(const AuthInitial());

  /// Vol 6.8: "Session restored at app launch after validation." Called
  /// once from the splash screen (SCR-001).
  Future<void> restoreSession() async {
    state = const AuthLoading();
    final hasSession = await _repo.hasStoredSession();
    if (!hasSession) {
      state = const AuthUnauthenticated();
      return;
    }
    try {
      final profile = await _repo.getProfile();
      state = AuthAuthenticated(profile);
    } on ApiException {
      // Vol 6.8: "Automatic logout on invalid/expired token."
      await _repo.logout();
      state = const AuthUnauthenticated();
    }
  }

  Future<void> login({required String identifier, required String password}) async {
    state = const AuthLoading();
    try {
      final profile = await _repo.login(identifier: identifier, password: password);
      state = AuthAuthenticated(profile);
    } on ApiException catch (e) {
      state = AuthError(e.message);
    }
  }

  Future<bool> register({
    required String fullName,
    required String email,
    required String phone,
    required String password,
  }) async {
    state = const AuthLoading();
    try {
      await _repo.register(fullName: fullName, email: email, phone: phone, password: password);
      state = const AuthUnauthenticated(); // registered, but not yet logged in
      return true;
    } on ApiException catch (e) {
      state = AuthError(e.message);
      return false;
    }
  }

  Future<void> logout() async {
    await _repo.logout();
    state = const AuthUnauthenticated();
  }

  /// Clears a stale error left over from a previous submit on a
  /// different auth screen (e.g. a register failure bleeding into the
  /// login screen after navigating away) — the error is scoped to the
  /// form that produced it, not a durable app-wide condition.
  void clearError() {
    if (state is AuthError) state = const AuthUnauthenticated();
  }

  Future<void> refreshProfile() async {
    if (state is! AuthAuthenticated) return;
    try {
      final profile = await _repo.getProfile();
      state = AuthAuthenticated(profile);
    } on ApiException {
      // Keep prior state on a transient failure — don't kick the user
      // out just because a profile refresh hiccuped.
    }
  }
}

final authProvider = StateNotifierProvider<AuthNotifier, AuthState>((ref) {
  return AuthNotifier(ref.watch(authRepositoryProvider));
});
