#!/usr/bin/env bash
# Adds the location permissions that package:geolocator needs on Android/iOS.
# The repo only ships the web/ platform; after generating the phone platforms
#   flutter create --platforms=android,ios .
# run (from mobile/):  bash tool/enable_location_permissions.sh
# Without these entries the OS refuses location silently and GPS is never saved.
set -euo pipefail
cd "$(dirname "$0")/.."

MANIFEST=android/app/src/main/AndroidManifest.xml
if [ -f "$MANIFEST" ]; then
  for perm in ACCESS_FINE_LOCATION ACCESS_COARSE_LOCATION INTERNET; do
    if ! grep -q "android.permission.$perm" "$MANIFEST"; then
      perl -0pi -e "s#<application#<uses-permission android:name=\"android.permission.$perm\"/>\n    <application#" "$MANIFEST"
      echo "Android: added $perm"
    fi
  done
else
  echo "Android: $MANIFEST not found (run: flutter create --platforms=android .)"
fi

PLIST=ios/Runner/Info.plist
if [ -f "$PLIST" ]; then
  if ! grep -q NSLocationWhenInUseUsageDescription "$PLIST"; then
    perl -0pi -e 's#<dict>#<dict>\n\t<key>NSLocationWhenInUseUsageDescription</key>\n\t<string>SCAS uses your location to save where your farm is and to fetch local weather.</string>#' "$PLIST"
    echo "iOS: added NSLocationWhenInUseUsageDescription"
  fi
else
  echo "iOS: $PLIST not found (run: flutter create --platforms=ios .)"
fi
