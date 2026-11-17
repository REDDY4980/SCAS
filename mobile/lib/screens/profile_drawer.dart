import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:google_fonts/google_fonts.dart';

import '../localization/app_strings.dart';
import '../providers/auth_provider.dart';
import '../providers/farm_provider.dart';
import '../providers/locale_provider.dart';
import '../routes/app_router.dart';
import '../theme/app_colors.dart';

/// Side navigation drawer — matches reference design's menu screen:
/// name header, icon+label rows for every major section, red Logout
/// at the bottom.
class ProfileDrawer extends ConsumerWidget {
  const ProfileDrawer({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final authState = ref.watch(authProvider);
    final userName = authState is AuthAuthenticated ? authState.user.fullName : 'Farmer';
    final s = ref.watch(appStringsProvider);

    return Drawer(
      backgroundColor: AppColors.background,
      width: MediaQuery.of(context).size.width * 0.86,
      child: SafeArea(
        child: Padding(
          padding: const EdgeInsets.fromLTRB(20, 20, 20, 20),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  Expanded(
                    child: Text(
                      userName,
                      style: GoogleFonts.poppins(fontSize: 20, fontWeight: FontWeight.w800),
                      overflow: TextOverflow.ellipsis,
                    ),
                  ),
                  InkWell(
                    onTap: () => Navigator.of(context).pop(),
                    borderRadius: BorderRadius.circular(12),
                    child: Container(
                      width: 40,
                      height: 40,
                      decoration: BoxDecoration(
                        color: AppColors.surfaceMuted,
                        borderRadius: BorderRadius.circular(12),
                        border: Border.all(color: AppColors.borderLight),
                      ),
                      child: const Icon(Icons.chevron_left, color: AppColors.textPrimary),
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 24),
              _DrawerItem(
                icon: Icons.home_outlined,
                label: s.t('home'),
                onTap: () {
                  Navigator.of(context).pop();
                  context.go(AppRoutes.dashboard);
                },
              ),
              _DrawerItem(
                icon: Icons.upload_outlined,
                label: s.t('soilTest'),
                onTap: () {
                  Navigator.of(context).pop();
                  final farms = ref.read(farmListProvider).value ?? [];
                  if (farms.isEmpty) {
                    context.push(AppRoutes.farms);
                  } else {
                    context.push('${AppRoutes.upload}?farmId=${farms.first.id}');
                  }
                },
              ),
              _DrawerItem(
                icon: Icons.eco_outlined,
                label: s.t('crops'),
                onTap: () {
                  Navigator.of(context).pop();
                  context.push(AppRoutes.history);
                },
              ),
              _DrawerItem(
                icon: Icons.water_drop_outlined,
                label: s.t('fertilizer'),
                onTap: () {
                  Navigator.of(context).pop();
                  context.push(AppRoutes.history);
                },
              ),
              _DrawerItem(
                icon: Icons.camera_alt_outlined,
                label: s.t('diseaseScan'),
                comingSoon: true,
                comingSoonLabel: s.t('comingSoon'),
                onTap: () => Navigator.of(context).pop(),
              ),
              _DrawerItem(
                icon: Icons.bar_chart_outlined,
                label: s.t('market'),
                onTap: () {
                  Navigator.of(context).pop();
                  context.push(AppRoutes.market);
                },
              ),
              _DrawerItem(
                icon: Icons.error_outline,
                label: s.t('aiAdvisor'),
                onTap: () {
                  Navigator.of(context).pop();
                  context.push(AppRoutes.history);
                },
              ),
              _DrawerItem(
                icon: Icons.cloud_outlined,
                label: s.t('weather'),
                onTap: () {
                  Navigator.of(context).pop();
                  context.go(AppRoutes.dashboard);
                },
              ),
              _DrawerItem(
                icon: Icons.history_outlined,
                label: s.t('history'),
                onTap: () {
                  Navigator.of(context).pop();
                  context.push(AppRoutes.history);
                },
              ),
              _DrawerItem(
                icon: Icons.person_outline,
                label: s.t('farmerProfile'),
                onTap: () {
                  Navigator.of(context).pop();
                  context.push(AppRoutes.profile);
                },
              ),
              const Spacer(),
              _DrawerItem(
                icon: Icons.logout,
                label: s.t('logout'),
                isDestructive: true,
                onTap: () {
                  Navigator.of(context).pop();
                  ref.read(authProvider.notifier).logout();
                },
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _DrawerItem extends StatelessWidget {
  final IconData icon;
  final String label;
  final VoidCallback onTap;
  final bool isDestructive;
  final bool comingSoon;
  final String comingSoonLabel;

  const _DrawerItem({
    required this.icon,
    required this.label,
    required this.onTap,
    this.isDestructive = false,
    this.comingSoon = false,
    this.comingSoonLabel = '(soon)',
  });

  @override
  Widget build(BuildContext context) {
    final color = isDestructive ? AppColors.logoutRed : AppColors.textPrimary;
    final iconColor = isDestructive ? AppColors.logoutRed : AppColors.primary;
    return InkWell(
      onTap: () {
        if (comingSoon) {
          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(content: Text('$label is coming in a future update.')),
          );
          return;
        }
        onTap();
      },
      child: Padding(
        padding: const EdgeInsets.symmetric(vertical: 14),
        child: Row(
          children: [
            Icon(icon, color: iconColor, size: 22),
            const SizedBox(width: 16),
            Text(label, style: GoogleFonts.poppins(fontSize: 15, fontWeight: FontWeight.w600, color: color)),
            if (comingSoon) ...[
              const SizedBox(width: 8),
              Text(comingSoonLabel, style: GoogleFonts.poppins(fontSize: 11, color: AppColors.textSecondary)),
            ],
          ],
        ),
      ),
    );
  }
}
