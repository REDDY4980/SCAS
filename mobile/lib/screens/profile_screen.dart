import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../providers/auth_provider.dart';
import '../providers/locale_provider.dart';
import '../providers/repository_providers.dart';
import '../localization/app_strings.dart';
import '../widgets/common_widgets.dart';

/// SCR-011 Profile & Settings.
/// Primary Components: Language, account, logout.
/// Backend/API Mapping: GET/PUT profile.
/// Acceptance Criteria: Secure logout.
class ProfileScreen extends ConsumerStatefulWidget {
  const ProfileScreen({super.key});

  @override
  ConsumerState<ProfileScreen> createState() => _ProfileScreenState();
}

class _ProfileScreenState extends ConsumerState<ProfileScreen> {
  static const _themes = {'system': 'System', 'light': 'Light', 'dark': 'Dark'};

  @override
  Widget build(BuildContext context) {
    final authState = ref.watch(authProvider);

    if (authState is! AuthAuthenticated) {
      return const Scaffold(body: LoadingView());
    }
    final user = authState.user;

    return Scaffold(
      appBar: AppBar(title: const Text('Profile & Settings')),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          Center(
            child: Column(
              children: [
                CircleAvatar(
                  radius: 40,
                  child: Text(
                    user.fullName.isNotEmpty ? user.fullName[0].toUpperCase() : '?',
                    style: const TextStyle(fontSize: 32),
                  ),
                ),
                const SizedBox(height: 12),
                Text(user.fullName, style: Theme.of(context).textTheme.titleLarge),
                Text(user.email, style: Theme.of(context).textTheme.bodyMedium),
                Text(user.phone, style: Theme.of(context).textTheme.bodyMedium),
              ],
            ),
          ),
          const SizedBox(height: 24),
          const Divider(),
          ListTile(
            leading: const Icon(Icons.language_outlined),
            title: const Text('Language'),
            trailing: DropdownButton<AppLanguage>(
              value: ref.watch(localeProvider),
              items: AppLanguage.values
                  .map((lang) => DropdownMenuItem(value: lang, child: Text(lang.nativeName)))
                  .toList(),
              onChanged: (lang) {
                if (lang == null) return;
                // Updates the live UI language immediately (same
                // mechanism as the login screen's language chips) AND
                // persists to the backend profile since the user is
                // authenticated here.
                ref.read(localeProvider.notifier).setLanguage(lang, ref: ref);
              },
            ),
          ),
          ListTile(
            leading: const Icon(Icons.palette_outlined),
            title: const Text('Theme'),
            trailing: DropdownButton<String>(
              value: _themes.containsKey(user.theme) ? user.theme : 'system',
              items: _themes.entries
                  .map((e) => DropdownMenuItem(value: e.key, child: Text(e.value)))
                  .toList(),
              onChanged: (value) {
                if (value != null) {
                  ref.read(authRepositoryProvider).updateProfile(theme: value).then(
                        (_) => ref.read(authProvider.notifier).refreshProfile(),
                      );
                }
              },
            ),
          ),
          SwitchListTile(
            secondary: const Icon(Icons.notifications_outlined),
            title: const Text('Notifications'),
            value: user.notifications,
            onChanged: (value) {
              ref.read(authRepositoryProvider).updateProfile(notifications: value).then(
                    (_) => ref.read(authProvider.notifier).refreshProfile(),
                  );
            },
          ),
          const SizedBox(height: 24),
          const Divider(),
          const SizedBox(height: 12),
          // Vol 6.14 acceptance criterion: "Secure logout."
          OutlinedButton.icon(
            onPressed: () => _confirmLogout(context),
            icon: const Icon(Icons.logout),
            label: const Text('Log out'),
            style: OutlinedButton.styleFrom(
              minimumSize: const Size.fromHeight(48),
              foregroundColor: Theme.of(context).colorScheme.error,
            ),
          ),
        ],
      ),
    );
  }

  void _confirmLogout(BuildContext context) {
    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Log out?'),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx), child: const Text('Cancel')),
          FilledButton(
            onPressed: () {
              Navigator.pop(ctx);
              ref.read(authProvider.notifier).logout(); // clears secure storage + resets state
            },
            child: const Text('Log out'),
          ),
        ],
      ),
    );
  }
}
