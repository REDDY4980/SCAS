import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../providers/auth_provider.dart';
import '../screens/ai_analysis_screen.dart';
import '../screens/crop_recommendation_screen.dart';
import '../screens/dashboard_screen.dart';
import '../screens/edit_farm_screen.dart';
import '../screens/farm_management_screen.dart';
import '../screens/fertilizer_recommendation_screen.dart';
import '../screens/history_detail_screen.dart';
import '../screens/history_screen.dart';
import '../screens/login_screen.dart';
import '../screens/profile_screen.dart';
import '../screens/register_screen.dart';
import '../screens/splash_screen.dart';
import '../screens/upload_screen.dart';

/// AIB v1.0 Vol 13.5: "Use named routes with guarded authentication."
/// Vol 3.3: "Authentication is the entry gate. Upload cannot proceed
/// without an authenticated user and an active farm. Recommendation
/// screens are accessible only after a successful analysis."
class AppRoutes {
  AppRoutes._();
  static const splash = '/';
  static const login = '/login';
  static const register = '/register';
  static const dashboard = '/dashboard';
  static const farms = '/farms';
  static const editFarm = '/farms/:id/edit';
  static const upload = '/upload';
  static const aiAnalysis = '/analysis';
  static const cropRecommendation = '/recommendation';
  static const fertilizerRecommendation = '/fertilizer';
  static const history = '/history';
  static const historyDetail = '/history/:id';
  static const profile = '/profile';
}

final routerProvider = Provider<GoRouter>((ref) {
  return GoRouter(
    initialLocation: AppRoutes.splash,
    // Vol 13.5 auth guard: redirect based on live auth state rather
    // than re-checking storage on every navigation.
    redirect: (context, state) {
      final authState = ref.read(authProvider);
      final isAuthRoute = state.matchedLocation == AppRoutes.login ||
          state.matchedLocation == AppRoutes.register;
      final isSplash = state.matchedLocation == AppRoutes.splash;

      // AuthLoading also covers an interactive login/register submission
      // (AuthNotifier sets it before every network call, not just during
      // the one-time boot-time session restore) — only force a detour to
      // splash for that boot case. If the user is already on an auth
      // route and submits the form, staying put lets the screen's own
      // isLoading spinner and post-submit navigation (e.g. register's
      // context.pop()) run without the router yanking them to splash
      // and back mid-flight.
      if (authState is AuthLoading || authState is AuthInitial) {
        return (isSplash || isAuthRoute) ? null : AppRoutes.splash;
      }
      if (authState is AuthAuthenticated) {
        if (isAuthRoute || isSplash) return AppRoutes.dashboard;
        return null;
      }
      // Unauthenticated (or error): only auth routes are reachable.
      if (!isAuthRoute) return AppRoutes.login;
      return null;
    },
    refreshListenable: _AuthStateListenable(ref),
    routes: [
      GoRoute(path: AppRoutes.splash, builder: (context, state) => const SplashScreen()),
      GoRoute(path: AppRoutes.login, builder: (context, state) => const LoginScreen()),
      GoRoute(path: AppRoutes.register, builder: (context, state) => const RegisterScreen()),
      GoRoute(path: AppRoutes.dashboard, builder: (context, state) => const DashboardScreen()),
      GoRoute(path: AppRoutes.farms, builder: (context, state) => const FarmManagementScreen()),
      GoRoute(
        path: AppRoutes.editFarm,
        builder: (context, state) => EditFarmScreen(farmId: state.pathParameters['id']!),
      ),
      GoRoute(
        path: AppRoutes.upload,
        builder: (context, state) => UploadScreen(farmId: state.uri.queryParameters['farmId']!),
      ),
      GoRoute(
        path: AppRoutes.aiAnalysis,
        builder: (context, state) => AiAnalysisScreen(
          farmId: state.uri.queryParameters['farmId']!,
          reportId: state.uri.queryParameters['reportId']!,
        ),
      ),
      GoRoute(
        path: AppRoutes.cropRecommendation,
        builder: (context, state) =>
            CropRecommendationScreen(farmId: state.uri.queryParameters['farmId']!),
      ),
      GoRoute(
        path: AppRoutes.fertilizerRecommendation,
        builder: (context, state) => FertilizerRecommendationScreen(
          recommendationId: state.uri.queryParameters['recommendationId']!,
        ),
      ),
      GoRoute(path: AppRoutes.history, builder: (context, state) => const HistoryScreen()),
      GoRoute(
        path: AppRoutes.historyDetail,
        builder: (context, state) => HistoryDetailScreen(recommendationId: state.pathParameters['id']!),
      ),
      GoRoute(path: AppRoutes.profile, builder: (context, state) => const ProfileScreen()),
    ],
  );
});

/// Bridges Riverpod's authProvider changes into go_router's imperative
/// refresh mechanism, so a login/logout immediately re-evaluates redirects.
class _AuthStateListenable extends ChangeNotifier {
  _AuthStateListenable(Ref ref) {
    ref.listen(authProvider, (_, __) => notifyListeners());
  }
}
