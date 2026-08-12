/// Matches app/schemas/recommendation.py::CropRecommendationItem.
class CropRecommendationItem {
  final String crop;
  final double confidence;
  final String reason;

  const CropRecommendationItem({
    required this.crop,
    required this.confidence,
    required this.reason,
  });

  factory CropRecommendationItem.fromJson(Map<String, dynamic> json) {
    return CropRecommendationItem(
      crop: json['crop'] as String,
      confidence: (json['confidence'] as num).toDouble(),
      reason: json['reason'] as String,
    );
  }
}

/// Matches app/schemas/recommendation.py::RecommendationOut exactly.
class CropRecommendation {
  final String? id;
  final String farmId;
  final String primaryCrop;
  final double confidence;
  final String explanation;
  final List<CropRecommendationItem> topRecommendations;
  final String modelVersion;
  final DateTime? createdAt;

  const CropRecommendation({
    this.id,
    required this.farmId,
    required this.primaryCrop,
    required this.confidence,
    required this.explanation,
    required this.topRecommendations,
    required this.modelVersion,
    this.createdAt,
  });

  factory CropRecommendation.fromJson(Map<String, dynamic> json) {
    return CropRecommendation(
      id: json['id'] as String?,
      farmId: json['farm_id'] as String,
      primaryCrop: json['primary_crop'] as String,
      confidence: (json['confidence'] as num).toDouble(),
      explanation: json['explanation'] as String,
      topRecommendations: (json['top_recommendations'] as List<dynamic>? ?? [])
          .map((e) => CropRecommendationItem.fromJson(e as Map<String, dynamic>))
          .toList(),
      modelVersion: json['model_version'] as String? ?? '',
      createdAt: json['created_at'] == null ? null : DateTime.parse(json['created_at'] as String),
    );
  }
}
