import 'soil_report.dart';

/// Matches app/schemas/history.py::HistorySummaryOut exactly.
class HistorySummary {
  final String id;
  final String farmId;
  final String farmName;
  final String recommendedCrop;
  final double confidenceScore;
  final DateTime createdAt;

  const HistorySummary({
    required this.id,
    required this.farmId,
    required this.farmName,
    required this.recommendedCrop,
    required this.confidenceScore,
    required this.createdAt,
  });

  factory HistorySummary.fromJson(Map<String, dynamic> json) {
    return HistorySummary(
      id: json['id'] as String,
      farmId: json['farm_id'] as String,
      farmName: json['farm_name'] as String,
      recommendedCrop: json['recommended_crop'] as String,
      confidenceScore: (json['confidence_score'] as num).toDouble(),
      createdAt: DateTime.parse(json['created_at'] as String),
    );
  }
}

/// Matches app/schemas/history.py::WeatherSnapshotSummary.
class HistoryWeatherSummary {
  final double? temperature;
  final double? humidity;
  final double? rainfall;
  final double? windSpeed;

  const HistoryWeatherSummary({this.temperature, this.humidity, this.rainfall, this.windSpeed});

  factory HistoryWeatherSummary.fromJson(Map<String, dynamic> json) {
    return HistoryWeatherSummary(
      temperature: (json['temperature'] as num?)?.toDouble(),
      humidity: (json['humidity'] as num?)?.toDouble(),
      rainfall: (json['rainfall'] as num?)?.toDouble(),
      windSpeed: (json['wind_speed'] as num?)?.toDouble(),
    );
  }
}

/// Matches app/schemas/history.py::FertilizerHistoryItem.
class HistoryFertilizerItem {
  final String fertilizerName;
  final String dosage;
  final String reason;

  const HistoryFertilizerItem({
    required this.fertilizerName,
    required this.dosage,
    required this.reason,
  });

  factory HistoryFertilizerItem.fromJson(Map<String, dynamic> json) {
    return HistoryFertilizerItem(
      fertilizerName: json['fertilizer_name'] as String,
      dosage: json['dosage'] as String,
      reason: json['reason'] as String,
    );
  }
}

/// Matches app/schemas/history.py::HistoryDetailOut exactly.
class HistoryDetail {
  final String id;
  final String farmId;
  final String farmName;
  final String recommendedCrop;
  final double confidenceScore;
  final String reasoning;
  final DateTime createdAt;
  final SoilParameters? soilParameters;
  final HistoryWeatherSummary? weather;
  final List<HistoryFertilizerItem> fertilizerRecommendations;

  const HistoryDetail({
    required this.id,
    required this.farmId,
    required this.farmName,
    required this.recommendedCrop,
    required this.confidenceScore,
    required this.reasoning,
    required this.createdAt,
    this.soilParameters,
    this.weather,
    required this.fertilizerRecommendations,
  });

  factory HistoryDetail.fromJson(Map<String, dynamic> json) {
    return HistoryDetail(
      id: json['id'] as String,
      farmId: json['farm_id'] as String,
      farmName: json['farm_name'] as String,
      recommendedCrop: json['recommended_crop'] as String,
      confidenceScore: (json['confidence_score'] as num).toDouble(),
      reasoning: json['reasoning'] as String,
      createdAt: DateTime.parse(json['created_at'] as String),
      soilParameters: json['soil_parameters'] == null
          ? null
          : SoilParameters.fromJson(json['soil_parameters'] as Map<String, dynamic>),
      weather: json['weather'] == null
          ? null
          : HistoryWeatherSummary.fromJson(json['weather'] as Map<String, dynamic>),
      fertilizerRecommendations: (json['fertilizer_recommendations'] as List<dynamic>? ?? [])
          .map((e) => HistoryFertilizerItem.fromJson(e as Map<String, dynamic>))
          .toList(),
    );
  }
}
