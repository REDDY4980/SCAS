import 'dart:async';

import 'package:flutter/foundation.dart' show kIsWeb;
import 'package:geolocator/geolocator.dart';

/// Why a location attempt ended the way it did. The UI shows a message
/// for every status, so the farmer always knows whether their location
/// was saved and what to do if it was not.
enum LocationStatus {
  success,
  serviceDisabled, // phone GPS / location turned off
  denied, // permission refused this time
  deniedForever, // permission blocked in browser / phone settings
  insecureContext, // web page opened over plain http (not https / localhost)
  timeout, // no position fix in time
  error, // anything else (unsupported browser, plugin error)
}

class LocationResult {
  final LocationStatus status;
  final double? latitude;
  final double? longitude;
  final double? accuracyM;
  final String? detail;

  const LocationResult(this.status, {this.latitude, this.longitude, this.accuracyM, this.detail});

  bool get ok => status == LocationStatus.success;

  /// Farmer-facing explanation (English; kept short for the status tile).
  String get message => switch (status) {
        LocationStatus.success => 'Location detected'
            '${accuracyM != null ? ' (within ${accuracyM!.round()} m)' : ''}',
        LocationStatus.serviceDisabled => 'Location is turned off on this device. Turn it on and tap Try again.',
        LocationStatus.denied => 'Location permission was not given. Tap Try again and choose Allow.',
        LocationStatus.deniedForever =>
          'Location is blocked for this app. Allow it in your browser or phone settings, then tap Try again.',
        LocationStatus.insecureContext =>
          'Browsers only share location on secure (https) pages. Open the app using its https link.',
        LocationStatus.timeout => 'Could not get a GPS fix. Move to an open area and tap Try again.',
        LocationStatus.error => 'Location is not available on this device'
            '${detail != null ? ' ($detail)' : ''}.',
      };
}

/// Device location for farms and the farmer profile.
///
/// What was wrong before: the whole attempt (including the time the
/// farmer took to answer the browser's permission pop-up) had to finish
/// within 8 seconds, every failure was silently turned into "no
/// location", and on browsers without the Permissions API (Safari)
/// `checkPermission()` throws, so location was never detected there.
///
/// Now: the permission step has no deadline (the farmer decides), only
/// the GPS fix is time-limited, a slower low-accuracy fix is tried
/// before giving up, and the reason for any failure is returned.
class LocationService {
  LocationService._();

  /// Browsers expose geolocation only in a secure context.
  static bool get _insecureWebPage {
    if (!kIsWeb) return false;
    final uri = Uri.base;
    final localHost = uri.host == 'localhost' || uri.host == '127.0.0.1' || uri.host == '[::1]';
    return uri.scheme != 'https' && !localHost;
  }

  static Future<LocationResult> detect() async {
    if (_insecureWebPage) return const LocationResult(LocationStatus.insecureContext);

    try {
      if (!kIsWeb && !await Geolocator.isLocationServiceEnabled()) {
        return const LocationResult(LocationStatus.serviceDisabled);
      }

      // Permission. On web, checkPermission() throws where the browser has
      // no Permissions API; in that case getCurrentPosition() below shows
      // the browser's own prompt, so we simply carry on.
      LocationPermission? permission;
      try {
        permission = await Geolocator.checkPermission();
        if (permission == LocationPermission.denied) {
          permission = await Geolocator.requestPermission(); // no timeout: farmer decides
        }
      } catch (_) {
        if (!kIsWeb) rethrow;
      }
      if (permission == LocationPermission.deniedForever) {
        return const LocationResult(LocationStatus.deniedForever);
      }
      if (permission == LocationPermission.denied) {
        return const LocationResult(LocationStatus.denied);
      }

      final position = await _currentPosition();
      if (position == null) return const LocationResult(LocationStatus.timeout);
      return LocationResult(
        LocationStatus.success,
        latitude: position.latitude,
        longitude: position.longitude,
        accuracyM: position.accuracy,
      );
    } on PermissionDeniedException {
      return const LocationResult(LocationStatus.denied);
    } on LocationServiceDisabledException {
      return const LocationResult(LocationStatus.serviceDisabled);
    } catch (e) {
      return LocationResult(LocationStatus.error, detail: e.runtimeType.toString());
    }
  }

  /// High-accuracy fix first, then a quicker network-based fix, then (on
  /// phones) the last known position. Returns null if all of them fail.
  static Future<Position?> _currentPosition() async {
    for (final settings in const [
      LocationSettings(accuracy: LocationAccuracy.high, timeLimit: Duration(seconds: 20)),
      LocationSettings(accuracy: LocationAccuracy.low, timeLimit: Duration(seconds: 15)),
    ]) {
      try {
        return await Geolocator.getCurrentPosition(locationSettings: settings);
      } on TimeoutException {
        continue;
      }
    }
    if (!kIsWeb) {
      try {
        return await Geolocator.getLastKnownPosition();
      } catch (_) {}
    }
    return null;
  }

  /// Backwards-compatible helper: coordinates or null.
  static Future<(double, double)?> tryGetCurrentCoordinates() async {
    final r = await detect();
    return r.ok ? (r.latitude!, r.longitude!) : null;
  }
}
