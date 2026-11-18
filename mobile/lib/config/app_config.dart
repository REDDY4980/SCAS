/// App configuration.
///
/// AIB v1.0 Vol 13.6: "Central API service." The base URL is injected
/// via --dart-define at build time rather than hardcoded, mirroring
/// the backend's environment-variable-only secrets policy (Vol 16.5) —
/// no production/staging URL is baked into source control.
///
/// Local development default assumes the backend from Vol 16.4's
/// docker-compose is running on the same machine. Android emulators
/// must use 10.0.2.2 instead of localhost to reach the host machine;
/// iOS simulators and physical devices on the same network use the
/// host's actual LAN IP. Override with:
///   flutter run --dart-define=API_BASE_URL=http://10.0.2.2:8000
library;

class AppConfig {
  AppConfig._();

  static const String apiBaseUrl = String.fromEnvironment(
    'API_BASE_URL',
    defaultValue: 'http://localhost:8000',
  );

  static const Duration apiConnectTimeout = Duration(seconds: 10);
  static const Duration apiReceiveTimeout = Duration(seconds: 15);
  // Soil report upload/OCR can legitimately take longer (Vol 7.13: OCR
  // <=5s, but multi-page real-world scans plus network latency warrant
  // headroom beyond the pure-processing budget).
  static const Duration uploadTimeout = Duration(seconds: 30);
  // The OCR trigger call runs the actual OCR inference server-side (not
  // just a byte transfer like uploadTimeout above). Measured on a
  // container limited like Render's free tier (0.1 CPU, 512 MB): ~130 s
  // per report page, and the backend accepts up to 5 pages (plus a short
  // wait if another report is being read). The backend never runs two
  // OCR jobs at once, so this is a ceiling, not a typical wait.
  static const Duration ocrTimeout = Duration(minutes: 15);
  // While a report is still being read server-side (after a dropped
  // connection, a client timeout or a "409 already processing"), the
  // analysis screen re-checks the report at this interval.
  static const Duration ocrPollInterval = Duration(seconds: 10);

  static const int maxUploadSizeMb = 10; // must match backend MAX_UPLOAD_SIZE_MB (Vol 16.5)
}
