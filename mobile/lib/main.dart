// SCAS Mobile — Flutter application entrypoint.
// AIB v1.0 Vol 13 (Flutter Engineering).
//
// Phase 3 (AIB Vol 17.3 "Flutter Foundation"): full navigation
// (go_router with auth guards), Riverpod state management, a Dio-based
// API client wired to all 12 real, tested backend endpoints (Phases
// 2/4/5/7/8/9), and the complete Vol 3 screen set.

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'routes/app_router.dart';
import 'theme/app_theme.dart';

void main() {
  runApp(const ProviderScope(child: ScasApp()));
}

class ScasApp extends ConsumerWidget {
  const ScasApp({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final router = ref.watch(routerProvider);

    return MaterialApp.router(
      title: 'Smart Crop Advisory System',
      debugShowCheckedModeBanner: false,
      theme: AppTheme.light,
      // Reference design only defines one theme (warm cream/forest
      // green); no dark-mode variant was provided, so we don't force
      // one — themeMode defaults to system, but without a `darkTheme`
      // override Flutter falls back to `theme` regardless of device
      // setting, which is the correct behavior here.
      routerConfig: router,
    );
  }
}
