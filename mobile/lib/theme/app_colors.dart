import 'package:flutter/material.dart';

/// Design tokens matched directly from the reference UI screenshots
/// (splash, language select, login, dashboard, OCR upload, results,
/// market, drawer). These are the single source of truth for every
/// screen's colors/spacing so the whole app stays visually consistent.
class AppColors {
  AppColors._();

  // Deep forest green — splash background, primary buttons, selected states
  static const primaryDark = Color(0xFF2D4A22);
  static const primary = Color(0xFF3F6B32);
  static const primaryLight = Color(0xFF4A7C3C);

  // Warm cream — main app background throughout
  static const background = Color(0xFFF3EEE3);
  static const backgroundAlt = Color(0xFFEFE9DB);

  // Card surfaces
  static const surface = Color(0xFFFFFFFF);
  static const surfaceMuted = Color(0xFFFAF7F0);

  // Text
  static const textPrimary = Color(0xFF2B2A26);
  static const textSecondary = Color(0xFF8B8378);
  static const textOnDark = Color(0xFFFFFFFF);
  static const textOnDarkMuted = Color(0xFFD9E4D3);

  // Accents
  static const logoutRed = Color(0xFFC1502E);
  static const warningAmber = Color(0xFFD9A441);
  static const success = Color(0xFF3F6B32);

  // Borders
  static const borderLight = Color(0xFFE3DCCB);
  static const borderDashed = Color(0xFF3F6B32);
}

class AppRadii {
  AppRadii._();
  static const card = 20.0;
  static const button = 16.0;
  static const chip = 24.0;
  static const iconBox = 18.0;
}

class AppSpacing {
  AppSpacing._();
  static const xs = 4.0;
  static const sm = 8.0;
  static const md = 16.0;
  static const lg = 24.0;
  static const xl = 32.0;
}
