/// Matches app/schemas/weather.py::WeatherSnapshotOut exactly.
class WeatherSnapshot {
  final String id;
  final String farmId;
  final double? temperature;
  final double? humidity;
  final double? rainfall;
  final double? windSpeed;
  final String season;
  final DateTime capturedAt;
  final bool cacheHit;
  final String? provider;

  const WeatherSnapshot({
    required this.id,
    required this.farmId,
    this.temperature,
    this.humidity,
    this.rainfall,
    this.windSpeed,
    required this.season,
    required this.capturedAt,
    required this.cacheHit,
    this.provider,
  });

  factory WeatherSnapshot.fromJson(Map<String, dynamic> json) {
    return WeatherSnapshot(
      id: json['id'] as String,
      farmId: json['farm_id'] as String,
      temperature: (json['temperature'] as num?)?.toDouble(),
      humidity: (json['humidity'] as num?)?.toDouble(),
      rainfall: (json['rainfall'] as num?)?.toDouble(),
      windSpeed: (json['wind_speed'] as num?)?.toDouble(),
      season: json['season'] as String,
      capturedAt: DateTime.parse(json['captured_at'] as String),
      cacheHit: json['cache_hit'] as bool? ?? false,
      provider: json['provider'] as String?,
    );
  }
}
