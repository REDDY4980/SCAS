# Phase 3 — Flutter Foundation: Completion Record

Per AIB v1.0 Vol 17.3 "Phase 3 – Flutter Foundation":
> Implement navigation, authentication screens, state management and API client.

## A different kind of verification than every prior phase — read this first

Every backend phase (1, 2, 4-9) had 156 passing pytest tests, a real trained ML model, and real files processed end-to-end. This phase has none of that, for one concrete reason: no Flutter/Dart SDK is available in this sandbox, and the network egress allowlist does not include Flutter's download domains (storage.googleapis.com etc.), so it could not be installed either. I confirmed this directly (`which flutter dart` -> nothing; `apt-cache search flutter` -> nothing relevant).

What I did instead: wrote every file by hand against the exact, already-tested backend API contracts, then did a systematic manual review pass -- grepping every screen for Riverpod/go_router/model usage and cross-checking it against that file's actual import list. This caught one real bug (see below) the same way a compiler would have. But it is not the same as compiling. Treat this phase's code as structurally reviewed, not verified -- the first `flutter pub get && flutter analyze` run after cloning this repo is a required step, not an optional sanity check.

## Deliverables

- [x] `lib/config/`, `lib/constants/api_endpoints.dart` -- API base URL (via `--dart-define`, no hardcoded secrets/URLs) and every one of the 12 real backend endpoint paths in one place
- [x] `lib/services/api_client.dart` -- Dio client, JWT auto-attach interceptor (Vol 13.6), unified `ApiException` error mapping (timeout/network/401/validation), multipart upload support
- [x] `lib/services/secure_storage_service.dart` -- JWT in flutter_secure_storage, non-sensitive prefs in SharedPreferences (Vol 13.7)
- [x] `lib/models/*.dart` -- 8 model files, every field name and JSON key checked by hand against the actual Pydantic schemas
- [x] `lib/repositories/*.dart` -- 7 repositories (Auth, Farm, Soil, Weather, Recommendation, Fertilizer, History), Vol 13.13 "all backend interaction through services/repositories"
- [x] `lib/providers/auth_provider.dart` -- sealed-class AuthState (Initial/Loading/Authenticated/Unauthenticated/Error), session restore on launch (Vol 6.8), auto-logout on expired token
- [x] `lib/providers/farm_provider.dart` -- farm list state
- [x] `lib/routes/app_router.dart` -- go_router with a live auth-state redirect guard (Vol 3.3)
- [x] All 11 Vol 3 screens: Splash (SCR-001), Login (SCR-002), Register (SCR-003), Dashboard (SCR-004), Farm Management (SCR-005), Upload (SCR-006), AI Analysis (SCR-007), Crop Recommendation (SCR-008), Fertilizer Recommendation (SCR-009), History list + detail (SCR-010), Profile/Settings (SCR-011)
- [x] `lib/theme/app_theme.dart`, `analysis_options.yaml` (using the flutter_lints package already in pubspec.yaml from Phase 1 -- present but never wired up until now)

## The AI Analysis screen is the real integration test of everything before it

SCR-007 is where Phases 4, 5, 7 actually meet: it calls POST /soil/{id}/ocr, branches to a manual-correction form if confidence is low or fields are missing (Vol 7.11), then calls GET /weather/current, then hands off to the Crop Recommendation screen which calls POST /recommendation -- the same real trained-model pipeline verified in Phase 7's integration tests. Every field in the manual-correction form mirrors the exact validation rules in app/schemas/soil.py::SoilParametersCorrection (pH 0-14, others >=0).

## A real bug found by manual review, not a compiler

profile_screen.dart called `ref.read(authRepositoryProvider)` for the language/theme/notification dropdowns, but only imported providers/auth_provider.dart -- authRepositoryProvider is actually defined in providers/repository_providers.dart. This is exactly the kind of "would fail on flutter analyze instantly" bug that a compiler catches for free and a human has to go looking for. Found it by systematically grepping every screen for identifier usage against its import list, and fixed it the same way I'd fix any other bug in this project.

## What manual review specifically checked (and found clean, beyond the bug above)

- Every screen using context.push/pop/go imports go_router (9 screens checked)
- Every screen using AppRoutes.* imports routes/app_router.dart (7 screens checked)
- Every screen using ConsumerWidget/ConsumerStatefulWidget/ref.watch/ref.read imports flutter_riverpod (all screens checked)
- Dio 5.x API usage (DioException, DioExceptionType.connectionTimeout etc., MultipartFile.fromFileSync, FormData.fromMap) matches the actual Dio 5.4.3 API surface
- flutter_secure_storage's constructor parameter name (aOptions) matches the actual package API
- Dart 3 pattern-matching syntax (sealed classes, switch expressions, record destructuring) is consistent with the >=3.3.0 SDK constraint already set in pubspec.yaml since Phase 1
- pubspec.yaml declares every package actually imported -- no missing dependency

## What was NOT verified (the honest gap)

- No flutter pub get, flutter analyze, flutter test, or flutter build was ever run. Dependency version compatibility, subtle type errors, and anything a human reviewer's eyes would miss are all real possibilities.
- No widget tests were written, despite Vol 13.12 calling for them. Writing tests for code that has never been run through the toolchain that would execute those tests felt like manufacturing false confidence -- better to be explicit that this is the next required step.
- The Android-emulator-vs-localhost networking note in app_config.dart is standard Flutter dev knowledge, not something tested against a real emulator here.

## Recommended next step for whoever picks this up

```bash
cd mobile
flutter pub get
flutter analyze          # first real compiler check of everything in this phase
flutter test              # once widget tests are written
flutter run --dart-define=API_BASE_URL=http://10.0.2.2:8000   # Android emulator against local backend
```

## Explicitly deferred to later phases (not gaps)

- Widget/navigation/golden tests (Vol 13.12) -- flagged above as the most important immediate follow-up, not silently skipped.
- Offline history caching (Vol 13.10) -- the History screen currently requires a live connection.
- CI pipeline running flutter analyze/flutter test automatically -- recommend as the very first Phase 10 task specifically because of this phase's verification gap.

## AIB Compliance Notes

- No business logic in widgets (Vol 13.13) -- every screen delegates to a repository or provider.
- JWT is never logged or exposed in UI (Vol 13.11).
- Flutter never calls OCR/weather providers directly -- every network call goes through ApiClient to the SCAS backend (Vol 8.14 principle extended to the mobile layer).
