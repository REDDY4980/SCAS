import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:google_fonts/google_fonts.dart';

import '../models/farm.dart';
import '../models/history.dart';
import '../models/weather.dart';
import '../localization/app_strings.dart';
import '../providers/auth_provider.dart';
import '../providers/farm_provider.dart';
import '../providers/locale_provider.dart';
import '../providers/repository_providers.dart';
import '../routes/app_router.dart';
import '../screens/profile_drawer.dart';
import '../theme/app_colors.dart';
import '../widgets/common_widgets.dart';

/// Loads the current weather for a specific farm (Vol 13.7 "recent farm
/// selection" concept, simplified for the dashboard's at-a-glance card).
/// Keyed by farmId so Riverpod caches per-farm rather than re-fetching
/// on every rebuild.
final _weatherForFarmProvider = FutureProvider.autoDispose.family<WeatherSnapshot, String>((ref, farmId) {
  return ref.watch(weatherRepositoryProvider).getCurrent(farmId);
});

/// Loads the single most recent completed analysis, if any, across all
/// of the user's farms — real data from the Phase 9 /history endpoint.
final _latestAnalysisProvider = FutureProvider.autoDispose<HistorySummary?>((ref) async {
  final results = await ref.watch(historyRepositoryProvider).list(limit: 1);
  return results.isEmpty ? null : results.first;
});

/// SCR-004 Home Dashboard — matches reference design: greeting header,
/// weather card, AI recommendation card, quick-actions grid, farm
/// overview stats, notched bottom bar with a floating center action.
class DashboardScreen extends ConsumerWidget {
  const DashboardScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final authState = ref.watch(authProvider);
    final farmsAsync = ref.watch(farmListProvider);
    final latestAsync = ref.watch(_latestAnalysisProvider);
    final s = ref.watch(appStringsProvider);
    final userName = authState is AuthAuthenticated ? authState.user.fullName : 'Farmer';
    final hour = DateTime.now().hour;
    final greeting = hour < 12 ? s.t('goodMorning') : (hour < 17 ? s.t('goodAfternoon') : s.t('goodEvening'));

    // Resolve weather only once the farm list is loaded and a farm
    // with coordinates exists — avoids the earlier design's invalid
    // attempt to await a StateNotifierProvider as if it were a Future.
    final farmsList = farmsAsync.value ?? const <Farm>[];
    final farmsWithCoords = farmsList.where((f) => f.hasCoordinates).toList();
    final weatherFarm = farmsWithCoords.isEmpty ? null : farmsWithCoords.first;
    final weatherFarmId = weatherFarm?.id;
    final weatherFarmLocationLabel =
        weatherFarm != null ? '${weatherFarm.district}, ${weatherFarm.state}' : null;
    final weatherAsync = weatherFarmId == null ? null : ref.watch(_weatherForFarmProvider(weatherFarmId));

    return Scaffold(
      endDrawer: const ProfileDrawer(),
      body: SafeArea(
        child: RefreshIndicator(
          onRefresh: () async {
            ref.invalidate(farmListProvider);
            ref.invalidate(_latestAnalysisProvider);
          },
          child: ListView(
            padding: const EdgeInsets.fromLTRB(20, 12, 20, 100),
            children: [
              Builder(builder: (context) {
                return Row(
                  children: [
                    const CircleAvatar(radius: 24, backgroundColor: AppColors.surfaceMuted, child: Icon(Icons.person, color: AppColors.primary)),
                    const SizedBox(width: 12),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Row(children: [
                            Text('$greeting ', style: GoogleFonts.poppins(fontSize: 13, color: AppColors.textSecondary)),
                            const Text('⭐', style: TextStyle(fontSize: 13)),
                          ]),
                          Text(userName, style: GoogleFonts.poppins(fontSize: 17, fontWeight: FontWeight.w800)),
                        ],
                      ),
                    ),
                    IconButton(
                      icon: const Icon(Icons.settings_outlined, color: AppColors.textPrimary),
                      style: IconButton.styleFrom(
                        backgroundColor: AppColors.surfaceMuted,
                        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                      ),
                      onPressed: () => Scaffold.of(context).openEndDrawer(),
                    ),
                  ],
                );
              }),
              const SizedBox(height: 20),
              if (weatherAsync == null)
                const WeatherCard(location: "We're locating your farm for weather...")
              else
                weatherAsync.when(
                  loading: () => const WeatherCard(location: 'Loading weather...'),
                  error: (_, __) => const WeatherCard(location: 'Weather temporarily unavailable'),
                  data: (weather) => WeatherCard(
                    location: weatherFarmLocationLabel ?? 'Your Farm',
                    temperatureC: weather.temperature,
                    condition: weather.season.replaceAll('_', ' '),
                  ),
                ),
              const SizedBox(height: 16),
              latestAsync.when(
                loading: () => const SizedBox(height: 140, child: LoadingView()),
                error: (_, __) => AiRecommendationCard(
                  headline: s.t('uploadFirstRecommendation'),
                  ctaLabel: s.t('analyzeSoilReport'),
                  onTap: () => _goToUpload(context, ref),
                ),
                data: (latest) => AiRecommendationCard(
                  headline: latest != null
                      ? '${_capitalize(latest.recommendedCrop)} is recommended for ${latest.farmName} '
                          '(${(latest.confidenceScore * 100).toStringAsFixed(0)}% confidence).'
                          '${s.language == AppLanguage.en ? '' : '\n${s.t('aiTextEnglishNote')}'}'
                      : s.t('uploadFirstRecommendation'),
                  ctaLabel: latest != null ? s.t('viewDetails') : s.t('analyzeSoilReport'),
                  onTap: () {
                    if (latest != null) {
                      context.push('/history/${latest.id}');
                    } else {
                      _goToUpload(context, ref);
                    }
                  },
                ),
              ),
              const SizedBox(height: 24),
              Text(s.t('quickActions'), style: GoogleFonts.poppins(fontSize: 16, fontWeight: FontWeight.w800)),
              const SizedBox(height: 14),
              GridView.count(
                shrinkWrap: true,
                physics: const NeverScrollableScrollPhysics(),
                crossAxisCount: 4,
                mainAxisSpacing: 16,
                crossAxisSpacing: 8,
                childAspectRatio: 0.85,
                children: [
                  QuickActionButton(icon: Icons.upload_outlined, label: s.t('soilTest'), onTap: () => _goToUpload(context, ref)),
                  QuickActionButton(icon: Icons.eco_outlined, label: s.t('crops'), onTap: () => _goToLatestOrUpload(context, ref, latestAsync, toFertilizer: false)),
                  QuickActionButton(icon: Icons.water_drop_outlined, label: s.t('fertilizer'), onTap: () => _goToLatestOrUpload(context, ref, latestAsync, toFertilizer: true)),
                  QuickActionButton(icon: Icons.camera_alt_outlined, label: s.t('diseaseScan'), onTap: _noop, comingSoon: true),
                  QuickActionButton(icon: Icons.bar_chart_outlined, label: s.t('market'), onTap: () => context.push(AppRoutes.market)),
                  QuickActionButton(
                    icon: Icons.cloud_outlined,
                    label: s.t('weather'),
                    onTap: () {
                      if (weatherFarmId != null) ref.invalidate(_weatherForFarmProvider(weatherFarmId));
                    },
                  ),
                  QuickActionButton(icon: Icons.error_outline, label: s.t('aiAdvisor'), onTap: () => _goToLatestOrUpload(context, ref, latestAsync, toFertilizer: false)),
                  QuickActionButton(icon: Icons.history, label: s.t('history'), onTap: () => context.push(AppRoutes.history)),
                ],
              ),
              const SizedBox(height: 24),
              Text(s.t('farmOverview'), style: GoogleFonts.poppins(fontSize: 16, fontWeight: FontWeight.w800)),
              const SizedBox(height: 12),
              farmsAsync.when(
                loading: () => const LoadingView(),
                error: (e, _) => ErrorView(message: e.toString(), onRetry: () => ref.invalidate(farmListProvider)),
                data: (farms) {
                  if (farms.isEmpty) {
                    return EmptyView(
                      message: s.t('noFarmsYet'),
                      icon: Icons.agriculture_outlined,
                      action: FilledButton(onPressed: () => context.push(AppRoutes.farms), child: Text(s.t('addFarm'))),
                    );
                  }
                  final farm = farms.first;
                  return latestAsync.when(
                    loading: () => const SizedBox.shrink(),
                    error: (_, __) => _farmStatsRow(farm, null, s),
                    data: (latest) => _farmStatsRow(farm, latest, s),
                  );
                },
              ),
              const SizedBox(height: 12),
              farmsAsync.maybeWhen(
                data: (farms) => farms.isEmpty
                    ? const SizedBox.shrink()
                    : Column(
                        children: farms
                            .map((farm) => Card(
                                  child: ListTile(
                                    leading: const Icon(Icons.landscape_outlined, color: AppColors.primary),
                                    title: Text(farm.farmName, style: GoogleFonts.poppins(fontWeight: FontWeight.w700)),
                                    subtitle: Text('${farm.district}, ${farm.state}'),
                                    trailing: const Icon(Icons.chevron_right),
                                    onTap: () => context.push('${AppRoutes.upload}?farmId=${farm.id}'),
                                  ),
                                ))
                            .toList(),
                      ),
                orElse: () => const SizedBox.shrink(),
              ),
            ],
          ),
        ),
      ),
      floatingActionButton: FloatingActionButton(
        backgroundColor: AppColors.primaryDark,
        onPressed: () => _goToLatestOrUpload(context, ref, latestAsync, toFertilizer: false),
        child: const Icon(Icons.priority_high, color: Colors.white),
      ),
      floatingActionButtonLocation: FloatingActionButtonLocation.centerDocked,
      bottomNavigationBar: BottomAppBar(
        shape: const CircularNotchedRectangle(),
        notchMargin: 8,
        color: AppColors.surface,
        child: Row(
          mainAxisAlignment: MainAxisAlignment.spaceAround,
          children: [
            _NavItem(icon: Icons.home_outlined, label: s.t('home'), active: true, onTap: () {}),
            _NavItem(icon: Icons.history_outlined, label: s.t('history'), onTap: () => context.push(AppRoutes.history)),
            const SizedBox(width: 40), // space for the notch
            _NavItem(
              icon: Icons.cloud_outlined,
              label: s.t('weather'),
              onTap: () {
                if (weatherFarmId != null) ref.invalidate(_weatherForFarmProvider(weatherFarmId));
              },
            ),
            Builder(
              builder: (context) => _NavItem(
                icon: Icons.person_outline,
                label: s.t('farmerProfile'),
                onTap: () => Scaffold.of(context).openEndDrawer(),
              ),
            ),
          ],
        ),
      ),
    );
  }

  static void _noop() {}

  static void _goToUpload(BuildContext context, WidgetRef ref) {
    final farms = ref.read(farmListProvider).value ?? [];
    if (farms.isEmpty) {
      context.push(AppRoutes.farms);
      return;
    }
    context.push('${AppRoutes.upload}?farmId=${farms.first.id}');
  }

  static void _goToLatestOrUpload(
    BuildContext context,
    WidgetRef ref,
    AsyncValue<HistorySummary?> latestAsync, {
    required bool toFertilizer,
  }) {
    final latest = latestAsync.value;
    if (latest == null) {
      _goToUpload(context, ref);
      return;
    }
    if (toFertilizer) {
      context.push('${AppRoutes.fertilizerRecommendation}?recommendationId=${latest.id}');
    } else {
      context.push('/history/${latest.id}');
    }
  }

  static String _capitalize(String s) => s.isEmpty ? s : s[0].toUpperCase() + s.substring(1);

  Widget _farmStatsRow(Farm farm, HistorySummary? latest, AppStrings s) {
    return Row(
      children: [
        Expanded(
          child: StatCard(
            label: s.t('aiConfidence'),
            value: latest != null ? '${(latest.confidenceScore * 100).toStringAsFixed(0)}%' : '—',
            subtext: latest != null ? _capitalize(latest.recommendedCrop) : s.t('noAnalysisYet'),
          ),
        ),
        const SizedBox(width: 10),
        Expanded(
          child: StatCard(
            label: s.t('land'),
            value: farm.areaAcres != null ? '${farm.areaAcres} Acres' : '—',
            subtext: farm.soilType ?? farm.district,
          ),
        ),
      ],
    );
  }
}

class _NavItem extends StatelessWidget {
  final IconData icon;
  final String label;
  final bool active;
  final VoidCallback onTap;
  const _NavItem({required this.icon, required this.label, required this.onTap, this.active = false});

  @override
  Widget build(BuildContext context) {
    final color = active ? AppColors.primary : AppColors.textSecondary;
    return InkWell(
      onTap: onTap,
      child: Padding(
        padding: const EdgeInsets.symmetric(vertical: 8, horizontal: 6),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(icon, color: color, size: 22),
            const SizedBox(height: 2),
            Text(label, style: GoogleFonts.poppins(fontSize: 10, color: color, fontWeight: FontWeight.w600)),
          ],
        ),
      ),
    );
  }
}
