import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../localization/app_strings.dart';
import 'auth_provider.dart';
import 'repository_providers.dart';

const _languagePrefsKey = 'scas_ui_language';

/// Current UI language, persisted locally (SharedPreferences, Vol 13.7)
/// and synced to the backend profile (Vol 6.9 language field) once the
/// user is authenticated. Works before login too — DECISIONS.md and the
/// reference design both show language selection on the login screen,
/// before any account exists.
class LocaleNotifier extends StateNotifier<AppLanguage> {
  LocaleNotifier() : super(AppLanguage.en) {
    _restore();
  }

  Future<void> _restore() async {
    final prefs = await SharedPreferences.getInstance();
    final saved = prefs.getString(_languagePrefsKey);
    if (saved != null) {
      state = AppLanguageX.fromCode(saved);
    }
  }

  Future<void> setLanguage(AppLanguage language, {WidgetRef? ref}) async {
    state = language;
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(_languagePrefsKey, language.code);

    // If logged in, also persist to the backend profile (Vol 6.9) so
    // the preference follows the account across devices — best-effort,
    // failure here shouldn't block the UI language switch itself.
    if (ref != null) {
      final authState = ref.read(authProvider);
      if (authState is AuthAuthenticated) {
        try {
          await ref.read(authRepositoryProvider).updateProfile(language: language.code);
        } catch (_) {
          // Non-fatal: local preference already applied.
        }
      }
    }
  }
}

final localeProvider = StateNotifierProvider<LocaleNotifier, AppLanguage>((ref) => LocaleNotifier());

/// Convenience provider: the translated-strings lookup for the current
/// language. Screens do `ref.watch(appStringsProvider).t('key')`.
final appStringsProvider = Provider<AppStrings>((ref) {
  final language = ref.watch(localeProvider);
  return AppStrings(language);
});
