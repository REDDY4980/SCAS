/// Matches app/schemas/soil.py::SoilParametersOut exactly.
class SoilParameters {
  final double? ph;
  final double? ec;
  final double? organicCarbon;
  final double? nitrogen;
  final double? phosphorus;
  final double? potassium;
  final double? zinc;
  final double? iron;
  final double? manganese;
  final double? copper;
  final double? boron;

  const SoilParameters({
    this.ph,
    this.ec,
    this.organicCarbon,
    this.nitrogen,
    this.phosphorus,
    this.potassium,
    this.zinc,
    this.iron,
    this.manganese,
    this.copper,
    this.boron,
  });

  factory SoilParameters.fromJson(Map<String, dynamic> json) {
    return SoilParameters(
      ph: (json['ph'] as num?)?.toDouble(),
      ec: (json['ec'] as num?)?.toDouble(),
      organicCarbon: (json['organic_carbon'] as num?)?.toDouble(),
      nitrogen: (json['nitrogen'] as num?)?.toDouble(),
      phosphorus: (json['phosphorus'] as num?)?.toDouble(),
      potassium: (json['potassium'] as num?)?.toDouble(),
      zinc: (json['zinc'] as num?)?.toDouble(),
      iron: (json['iron'] as num?)?.toDouble(),
      manganese: (json['manganese'] as num?)?.toDouble(),
      copper: (json['copper'] as num?)?.toDouble(),
      boron: (json['boron'] as num?)?.toDouble(),
    );
  }

  /// For the manual-correction form (Vol 7.10 PUT /soil/{id}/correct) —
  /// only non-null fields should be sent, matching the backend's
  /// SoilParametersCorrection schema semantics (null = "don't change").
  Map<String, dynamic> toCorrectionJson() => {
        if (ph != null) 'ph': ph,
        if (ec != null) 'ec': ec,
        if (organicCarbon != null) 'organic_carbon': organicCarbon,
        if (nitrogen != null) 'nitrogen': nitrogen,
        if (phosphorus != null) 'phosphorus': phosphorus,
        if (potassium != null) 'potassium': potassium,
        if (zinc != null) 'zinc': zinc,
        if (iron != null) 'iron': iron,
        if (manganese != null) 'manganese': manganese,
        if (copper != null) 'copper': copper,
        if (boron != null) 'boron': boron,
      };
}

/// Matches app/schemas/soil.py::SoilReportOut exactly.
class SoilReport {
  final String id;
  final String farmId;
  final String fileType;
  final String ocrStatus; // pending | processing | success | needs_review | failed
  final double? ocrConfidence;
  final DateTime uploadedAt;
  final SoilParameters? soilParameters;

  const SoilReport({
    required this.id,
    required this.farmId,
    required this.fileType,
    required this.ocrStatus,
    this.ocrConfidence,
    required this.uploadedAt,
    this.soilParameters,
  });

  bool get isValidated => ocrStatus == 'success';
  bool get needsReview => ocrStatus == 'needs_review';
  bool get failed => ocrStatus == 'failed';

  factory SoilReport.fromJson(Map<String, dynamic> json) {
    return SoilReport(
      id: json['id'] as String,
      farmId: json['farm_id'] as String,
      fileType: json['file_type'] as String,
      ocrStatus: json['ocr_status'] as String,
      ocrConfidence: (json['ocr_confidence'] as num?)?.toDouble(),
      uploadedAt: DateTime.parse(json['uploaded_at'] as String),
      soilParameters: json['soil_parameters'] == null
          ? null
          : SoilParameters.fromJson(json['soil_parameters'] as Map<String, dynamic>),
    );
  }
}

/// Matches app/schemas/soil.py::SoilReportUploadOut.
class SoilReportUploadResult {
  final String reportId;
  final String farmId;
  final String ocrStatus;
  final String message;

  const SoilReportUploadResult({
    required this.reportId,
    required this.farmId,
    required this.ocrStatus,
    required this.message,
  });

  factory SoilReportUploadResult.fromJson(Map<String, dynamic> json) {
    return SoilReportUploadResult(
      reportId: json['report_id'] as String,
      farmId: json['farm_id'] as String,
      ocrStatus: json['ocr_status'] as String,
      message: json['message'] as String,
    );
  }
}

/// Matches app/schemas/soil.py::OCRTriggerOut.
class OcrResult {
  final String reportId;
  final String ocrStatus;
  final double ocrConfidence;
  final SoilParameters? soilParameters;
  final List<String> warnings;
  final List<String> missingFields;

  const OcrResult({
    required this.reportId,
    required this.ocrStatus,
    required this.ocrConfidence,
    this.soilParameters,
    required this.warnings,
    required this.missingFields,
  });

  bool get needsManualReview => ocrStatus == 'needs_review' || ocrStatus == 'failed';

  factory OcrResult.fromJson(Map<String, dynamic> json) {
    return OcrResult(
      reportId: json['report_id'] as String,
      ocrStatus: json['ocr_status'] as String,
      ocrConfidence: (json['ocr_confidence'] as num).toDouble(),
      soilParameters: json['soil_parameters'] == null
          ? null
          : SoilParameters.fromJson(json['soil_parameters'] as Map<String, dynamic>),
      warnings: (json['warnings'] as List<dynamic>? ?? []).map((e) => e.toString()).toList(),
      missingFields:
          (json['missing_fields'] as List<dynamic>? ?? []).map((e) => e.toString()).toList(),
    );
  }
}
