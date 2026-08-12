import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../providers/auth_provider.dart';
import '../providers/farm_provider.dart';
import '../screens/ai_analysis_screen.dart';
import '../screens/crop_recommendation_screen.dart';
import '../screens/dashboard_screen.dart';
import '../screens/edit_farm_screen.dart';
import '../screens/farm_management_screen.dart';
import '../screens/farm_registration_screen.dart';
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
  static const farmRegistration = '/farm-registration';
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
    // than re-checking storage on every navigation. Also gates on farm
    // count: a farmer with zero farms is sent to farm registration
    // instead of the dashboard, which has nothing meaningful to show
    // without at least one farm (weather, recommendations, etc. are all
    // farm-scoped).
    redirect: (context, state) {
      final authState = ref.read(authProvider);
      final isAuthRoute = state.matchedLocation == AppRoutes.login ||
          state.matchedLocation == AppRoutes.register;
      final isSplash = state.matchedLocation == AppRoutes.splash;
      final isFarmRegistration = state.matchedLocation == AppRoutes.farmRegistration;

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
        final farmsAsync = ref.read(farmListProvider);

        // Farm list not resolved yet (first read after login lazily
        // creates the provider and kicks off its fetch) — hold on
        // splash rather than flashing the dashboard and immediately
        // yanking the farmer off it once we learn they have zero farms.
        if (farmsAsync.isLoading && !farmsAsync.hasValue) {
          return isSplash ? null : AppRoutes.splash;
        }

        // A farms-list fetch error shouldn't strand the farmer on
        // splash forever — fall through to the dashboard, which already
        // renders farmsAsync's own error/retry state.
        if (farmsAsync.hasError) {
          if (isAuthRoute || isSplash) return AppRoutes.dashboard;
          return null;
        }

        final hasNoFarms = (farmsAsync.value ?? const []).isEmpty;
        if (hasNoFarms) {
          return isFarmRegistration ? null : AppRoutes.farmRegistration;
        }
        if (isAuthRoute || isSplash || isFarmRegistration) return AppRoutes.dashboard;
        return null;
      }

      // Unauthenticated (or error): only auth routes are reachable.
      if (!isAuthRoute) return AppRoutes.login;
      return null;
    },
    refreshListenable: _AppStateListenable(ref),
    routes: [
      GoRoute(path: AppRoutes.splash, builder: (context, state) => const SplashScreen()),
      GoRoute(path: AppRoutes.login, builder: (context, state) => const LoginScreen()),
      GoRoute(path: AppRoutes.register, builder: (context, state) => const RegisterScreen()),
      GoRoute(
        path: AppRoutes.farmRegistration,
        builder: (context, state) => const FarmRegistrationScreen(),
      ),
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

/// Bridges Riverpod's authProvider and farmListProvider changes into
/// go_router's imperative refresh mechanism, so a login/logout or a
/// farm list load resolving immediately re-evaluates redirects (e.g.
/// the "waiting to learn if this farmer has any farms" splash detour
/// resolving into either farm-registration or the dashboard).
///
/// farmListProvider is only subscribed to AFTER the first
/// AuthAuthenticated sighting, not unconditionally at construction —
/// `ref.listen` eagerly creates the provider it targets, and this
/// listenable is built once at app boot (before any login), so an
/// unconditional listen would fire an unauthenticated GET /farms (401)
/// before the farmer ever signs in.
class _AppStateListenable extends ChangeNotifier {
  bool _watchingFarms = false;

  _AppStateListenable(Ref ref) {
    ref.listen<AuthState>(authProvider, (_, next) {
      notifyListeners();
      if (!_watchingFarms && next is AuthAuthenticated) {
        _watchingFarms = true;
        ref.listen(farmListProvider, (_, __) => notifyListeners());
      }
    });
  }
}
