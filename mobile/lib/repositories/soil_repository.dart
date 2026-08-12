import 'dart:typed_data';

import '../config/app_config.dart';
import '../constants/api_endpoints.dart';
import '../models/soil_report.dart';
import '../services/api_client.dart';

class SoilRepository {
  final ApiClient _client = ApiClient.instance;

  /// Vol 3 SCR-006: upload accepts JPG/PNG/PDF from camera, gallery, or
  /// file picker — `bytes` is the file's raw content regardless of
  /// source, so this works identically on web and native.
  Future<SoilReportUploadResult> uploadReport({
    required String farmId,
    required Uint8List bytes,
    required String fileName,
  }) async {
    final response = await _client.uploadFile(
      ApiEndpoints.soilUpload,
      bytes: bytes,
      fileName: fileName,
      queryParameters: {'farm_id': farmId},
    );
    return SoilReportUploadResult.fromJson(response['data'] as Map<String, dynamic>);
  }

  Future<OcrResult> triggerOcr(String reportId) async {
    final response = await _client.post(
      ApiEndpoints.soilOcr(reportId),
      receiveTimeout: AppConfig.ocrTimeout,
    );
    return OcrResult.fromJson(response['data'] as Map<String, dynamic>);
  }

  Future<SoilReport> getReport(String reportId) async {
    final response = await _client.get(ApiEndpoints.soilReport(reportId));
    return SoilReport.fromJson(response['data'] as Map<String, dynamic>);
  }

  /// Vol 7.11: manual correction path when OCR confidence is low or
  /// fields were missed — also used directly for manual data entry.
  Future<SoilReport> correctReport(String reportId, SoilParameters corrected) async {
    final response = await _client.put(
      ApiEndpoints.soilCorrect(reportId),
      data: corrected.toCorrectionJson(),
    );
    return SoilReport.fromJson(response['data'] as Map<String, dynamic>);
  }
}
