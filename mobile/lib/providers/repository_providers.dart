import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../repositories/auth_repository.dart';
import '../repositories/farm_repository.dart';
import '../repositories/fertilizer_repository.dart';
import '../repositories/history_repository.dart';
import '../repositories/recommendation_repository.dart';
import '../repositories/soil_repository.dart';
import '../repositories/weather_repository.dart';

/// AIB v1.0 Vol 13.4: Riverpod providers as the single source of truth
/// for dependency wiring — screens `ref.watch`/`ref.read` these instead
/// of constructing repositories themselves.
final authRepositoryProvider = Provider((ref) => AuthRepository());
final farmRepositoryProvider = Provider((ref) => FarmRepository());
final soilRepositoryProvider = Provider((ref) => SoilRepository());
final weatherRepositoryProvider = Provider((ref) => WeatherRepository());
final recommendationRepositoryProvider = Provider((ref) => RecommendationRepository());
final fertilizerRepositoryProvider = Provider((ref) => FertilizerRepository());
final historyRepositoryProvider = Provider((ref) => HistoryRepository());
