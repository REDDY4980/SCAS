import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../models/user.dart';
import '../providers/auth_provider.dart';
import '../providers/farm_provider.dart';
import '../providers/locale_provider.dart';
import '../providers/repository_providers.dart';
import '../localization/app_strings.dart';
import '../services/api_exception.dart';
import '../services/location_service.dart';
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
  bool _detecting = false;

  /// Detect the device location, save it on the profile and, if the farmer
  /// picks one, use it for a farm whose position is only approximate.
  Future<void> _detectAndSave() async {
    setState(() => _detecting = true);
    final messenger = ScaffoldMessenger.of(context);
    try {
      final r = await LocationService.detect();
      if (!r.ok) {
        messenger.showSnackBar(SnackBar(content: Text(r.message)));
        return;
      }
      final farms = ref.read(farmListProvider).valueOrNull ?? [];
      final approximate = farms.where((f) => !f.hasGps).toList();
      String? farmId;
      if (approximate.isNotEmpty && mounted) {
        farmId = await showDialog<String>(
          context: context,
          builder: (ctx) => SimpleDialog(
            title: const Text('Are you standing on one of your farms?'),
            children: [
              for (final f in approximate)
                SimpleDialogOption(
                  onPressed: () => Navigator.pop(ctx, f.id),
                  child: Text('Yes, use it for ${f.farmName}'),
                ),
              SimpleDialogOption(
                onPressed: () => Navigator.pop(ctx),
                child: const Text('No, save to my profile only'),
              ),
            ],
          ),
        );
      }
      await ref.read(authRepositoryProvider).updateLocation(
            latitude: r.latitude!,
            longitude: r.longitude!,
            accuracyM: r.accuracyM,
            applyToFarmId: farmId,
          );
      await ref.read(authProvider.notifier).refreshProfile();
      if (farmId != null) await ref.read(farmListProvider.notifier).load();
      messenger.showSnackBar(SnackBar(content: Text('${r.message}. Location saved.')));
    } on ApiException catch (e) {
      messenger.showSnackBar(SnackBar(content: Text(e.message)));
    } finally {
      if (mounted) setState(() => _detecting = false);
    }
  }

  Widget _locationCard(BuildContext context, UserProfile user) {
    final text = Theme.of(context).textTheme;
    final updated = user.locationUpdatedAt?.toLocal();
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(children: [
              Icon(user.hasLocation ? Icons.my_location : Icons.location_off_outlined),
              const SizedBox(width: 10),
              Text('My location', style: text.titleSmall),
            ]),
            const SizedBox(height: 8),
            if (user.hasLocation) ...[
              Text('${user.latitude!.toStringAsFixed(5)}, ${user.longitude!.toStringAsFixed(5)}'
                  '${user.locationAccuracyM != null ? '  (within ${user.locationAccuracyM!.round()} m)' : ''}'),
              if (updated != null)
                Text('Detected by GPS on ${updated.day}/${updated.month}/${updated.year} '
                    '${updated.hour.toString().padLeft(2, '0')}:${updated.minute.toString().padLeft(2, '0')}',
                    style: text.bodySmall),
            ] else
              Text('Not detected yet. Detect it so weather and advice use your exact location.', style: text.bodySmall),
            const SizedBox(height: 12),
            OutlinedButton.icon(
              onPressed: _detecting ? null : _detectAndSave,
              icon: _detecting
                  ? const SizedBox(width: 16, height: 16, child: CircularProgressIndicator(strokeWidth: 2))
                  : const Icon(Icons.gps_fixed),
              label: Text(_detecting ? 'Detecting...' : (user.hasLocation ? 'Update my location' : 'Detect my location')),
            ),
          ],
        ),
      ),
    );
  }

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
          const SizedBox(height: 20),
          _locationCard(context, user),
          const SizedBox(height: 12),
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
