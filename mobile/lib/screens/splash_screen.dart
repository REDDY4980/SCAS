import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:google_fonts/google_fonts.dart';

import '../providers/auth_provider.dart';
import '../providers/locale_provider.dart';
import '../routes/app_router.dart';
import '../theme/app_colors.dart';

/// SCR-001 Splash Screen — matches reference design exactly:
/// deep green background, leaf logo, "SCAS" wordmark, tagline,
/// white "Get Started" pill button.
class SplashScreen extends ConsumerStatefulWidget {
  const SplashScreen({super.key});

  @override
  ConsumerState<SplashScreen> createState() => _SplashScreenState();
}

class _SplashScreenState extends ConsumerState<SplashScreen> {
  bool _sessionChecked = false;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) async {
      // Vol 6.8: "Session restored at app launch after validation."
      // Skipped if already authenticated: the router's redirect logic
      // (app_router.dart) detours back through splash while it waits to
      // learn whether a just-logged-in farmer has any farms yet — that
      // isn't a fresh boot, so re-validating the session here would be
      // a redundant network call and a spurious AuthLoading blip.
      if (ref.read(authProvider) is! AuthAuthenticated) {
        await ref.read(authProvider.notifier).restoreSession();
      }
      if (mounted) setState(() => _sessionChecked = true);
    });
  }

  @override
  Widget build(BuildContext context) {
    final s = ref.watch(appStringsProvider);
    return Scaffold(
      backgroundColor: AppColors.primaryDark,
      body: SafeArea(
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 32),
          child: Column(
            children: [
              const Spacer(flex: 3),
              Container(
                width: 96,
                height: 96,
                decoration: BoxDecoration(
                  color: Colors.white.withOpacity(0.12),
                  borderRadius: BorderRadius.circular(24),
                ),
                child: const Icon(Icons.eco_outlined, color: Color(0xFF8FBF7A), size: 44),
              ),
              const SizedBox(height: 28),
              Text(
                'SCAS',
                style: GoogleFonts.poppins(color: Colors.white, fontSize: 34, fontWeight: FontWeight.w800, letterSpacing: 1),
              ),
              const SizedBox(height: 10),
              Text(
                'SCAS — Smart Crop Advisory System',
                textAlign: TextAlign.center,
                style: GoogleFonts.poppins(color: Colors.white, fontSize: 15, fontWeight: FontWeight.w600),
              ),
              const SizedBox(height: 8),
              Text(
                s.t('appTagline'),
                textAlign: TextAlign.center,
                style: GoogleFonts.poppins(color: AppColors.textOnDarkMuted, fontSize: 13),
              ),
              const Spacer(flex: 4),
              SizedBox(
                width: double.infinity,
                child: FilledButton(
                  style: FilledButton.styleFrom(
                    backgroundColor: Colors.white,
                    foregroundColor: AppColors.primaryDark,
                    minimumSize: const Size.fromHeight(56),
                  ),
                  onPressed: _sessionChecked
                      ? () {
                          // The router's own redirect (app_router.dart) already
                          // auto-navigates once auth state resolves — this is a
                          // safe fallback in case that hasn't fired yet.
                          final state = ref.read(authProvider);
                          if (state is! AuthAuthenticated) {
                            context.go(AppRoutes.login);
                          }
                        }
                      : null,
                  child: _sessionChecked
                      ? Text(s.t('getStarted'), style: GoogleFonts.poppins(fontWeight: FontWeight.w700))
                      : const SizedBox(
                          width: 20,
                          height: 20,
                          child: CircularProgressIndicator(strokeWidth: 2, color: AppColors.primaryDark),
                        ),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
