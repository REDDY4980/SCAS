import 'package:geolocator/geolocator.dart';

/// Silent GPS resolution for farm location.
///
/// Real product requirement: farmers never see or type latitude/
/// longitude anywhere in this app. This wraps the browser Geolocation
/// API (via package:geolocator's web implementation) behind a single
/// call that either quietly succeeds with a coordinate pair or quietly
/// returns null — every failure mode (permission denied, location
/// services off, no fix within the time budget, unsupported platform)
/// is treated identically and silently, because the backend's
/// district/state geocoding (FarmService._resolve_coordinates) is a
/// fully adequate fallback, not an error state that needs surfacing.
class LocationService {
  LocationService._();

  static Future<(double, double)?> tryGetCurrentCoordinates() async {
    try {
      // Wraps the ENTIRE attempt, not just getCurrentPosition's own
      // timeLimit: the browser's native permission prompt has no
      // deadline of its own — if the farmer never answers it (or the
      // dialog is somehow unreachable), requestPermission() never
      // resolves. Without this outer timeout, farm creation would hang
      // indefinitely instead of falling back to server-side geocoding.
      return await _resolve().timeout(const Duration(seconds: 8), onTimeout: () => null);
    } catch (_) {
      return null;
    }
  }

  static Future<(double, double)?> _resolve() async {
    final serviceEnabled = await Geolocator.isLocationServiceEnabled();
    if (!serviceEnabled) return null;

    var permission = await Geolocator.checkPermission();
    if (permission == LocationPermission.denied) {
      permission = await Geolocator.requestPermission();
    }
    if (permission == LocationPermission.denied || permission == LocationPermission.deniedForever) {
      return null;
    }

    final position = await Geolocator.getCurrentPosition(
      locationSettings: const LocationSettings(
        accuracy: LocationAccuracy.medium,
        timeLimit: Duration(seconds: 6),
      ),
    );
    return (position.latitude, position.longitude);
  }
}
