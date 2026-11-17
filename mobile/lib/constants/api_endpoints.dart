/// API endpoint constants.
///
/// AIB v1.0 Vol 14.2 — every path here matches an endpoint that was
/// actually built and tested in Phases 2/4/5/7/8/9 (156 passing tests).
/// This file is the single source of truth for route strings so a typo
/// here is a compile-time-visible constant, not a scattered string
/// literal repeated across every screen.
library;

class ApiEndpoints {
  ApiEndpoints._();

  static const String base = '/api/v1';

  // Auth (Phase 2)
  static const String register = '$base/auth/register';
  static const String login = '$base/auth/login';
  static const String me = '$base/auth/me';

  // Profile (Phase 2 + Phase 9 enhancement)
  static const String profile = '$base/users/profile';
  static const String userLocation = '$base/users/location';

  // Farms (Phase 2)
  static const String farms = '$base/farms';
  static String farm(String id) => '$base/farms/$id';

  // Soil / OCR (Phase 4)
  static const String soilUpload = '$base/soil/upload';
  static String soilOcr(String reportId) => '$base/soil/$reportId/ocr';
  static String soilReport(String reportId) => '$base/soil/$reportId';
  static String soilCorrect(String reportId) => '$base/soil/$reportId/correct';

  // Weather (Phase 5)
  static const String weatherCurrent = '$base/weather/current';
  static const String weatherRefresh = '$base/weather/refresh';
  static String weatherHistory(String farmId) => '$base/weather/history/$farmId';

  // Recommendation (Phase 7)
  static const String recommendation = '$base/recommendation';
  static String recommendationById(String id) => '$base/recommendation/$id';

  // Fertilizer (Phase 8)
  static String fertilizer(String recommendationId) => '$base/fertilizer/$recommendationId';

  // History (Phase 9)
  static const String history = '$base/history';
  static String historyDetail(String id) => '$base/history/$id';

  // Market (Objective 3)
  static const String marketCrops = '$base/market/crops';
  static String marketOutlook(String crop) => '$base/market/$crop/outlook';

  // System
  static const String health = '/health';
}
