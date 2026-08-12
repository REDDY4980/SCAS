/// Matches app/schemas/fertilizer.py::FertilizerRecommendationOut.
class FertilizerItem {
  final String fertilizerName;
  final String dosage;
  final List<String> targetNutrients;
  final String reason;
  final String applicationMethod;
  final String precautions;
  final String source;

  const FertilizerItem({
    required this.fertilizerName,
    required this.dosage,
    required this.targetNutrients,
    required this.reason,
    required this.applicationMethod,
    required this.precautions,
    required this.source,
  });

  /// Vol 11.9: a fallback-path item always says "not available" in its
  /// dosage text (Phase 8's central safety property) — surfaced here so
  /// the UI can render it with a distinct, honest visual treatment
  /// rather than looking identical to a sourced kg/ha number.
  bool get hasSourcedDosage => !dosage.toLowerCase().contains('not available');

  factory FertilizerItem.fromJson(Map<String, dynamic> json) {
    return FertilizerItem(
      fertilizerName: json['fertilizer_name'] as String,
      dosage: json['dosage'] as String,
      targetNutrients:
          (json['target_nutrients'] as List<dynamic>? ?? []).map((e) => e.toString()).toList(),
      reason: json['reason'] as String,
      applicationMethod: json['application_method'] as String? ?? '',
      precautions: json['precautions'] as String? ?? '',
      source: json['source'] as String? ?? '',
    );
  }
}

/// Matches app/schemas/fertilizer.py::FertilizerResponseOut exactly.
class FertilizerRecommendation {
  final String recommendationId;
  final String crop;
  final Map<String, String> deficiencyProfile;
  final List<FertilizerItem> fertilizers;
  final String knowledgeBaseCoverage; // "sourced" | "fallback"

  const FertilizerRecommendation({
    required this.recommendationId,
    required this.crop,
    required this.deficiencyProfile,
    required this.fertilizers,
    required this.knowledgeBaseCoverage,
  });

  factory FertilizerRecommendation.fromJson(Map<String, dynamic> json) {
    return FertilizerRecommendation(
      recommendationId: json['recommendation_id'] as String,
      crop: json['crop'] as String,
      deficiencyProfile: (json['deficiency_profile'] as Map<String, dynamic>? ?? {})
          .map((k, v) => MapEntry(k, v.toString())),
      fertilizers: (json['fertilizers'] as List<dynamic>? ?? [])
          .map((e) => FertilizerItem.fromJson(e as Map<String, dynamic>))
          .toList(),
      knowledgeBaseCoverage: json['knowledge_base_coverage'] as String? ?? '',
    );
  }
}
