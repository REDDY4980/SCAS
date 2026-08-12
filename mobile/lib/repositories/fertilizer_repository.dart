import '../constants/api_endpoints.dart';
import '../models/fertilizer.dart';
import '../services/api_client.dart';

class FertilizerRepository {
  final ApiClient _client = ApiClient.instance;

  Future<FertilizerRecommendation> generate(String recommendationId) async {
    final response = await _client.post(ApiEndpoints.fertilizer(recommendationId));
    return FertilizerRecommendation.fromJson(response['data'] as Map<String, dynamic>);
  }

  Future<FertilizerRecommendation> get(String recommendationId) async {
    final response = await _client.get(ApiEndpoints.fertilizer(recommendationId));
    return FertilizerRecommendation.fromJson(response['data'] as Map<String, dynamic>);
  }
}
