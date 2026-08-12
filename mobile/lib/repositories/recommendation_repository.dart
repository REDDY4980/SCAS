import '../constants/api_endpoints.dart';
import '../models/recommendation.dart';
import '../services/api_client.dart';

class RecommendationRepository {
  final ApiClient _client = ApiClient.instance;

  Future<CropRecommendation> generate(String farmId) async {
    final response = await _client.post(ApiEndpoints.recommendation, queryParameters: {'farm_id': farmId});
    return CropRecommendation.fromJson(response['data'] as Map<String, dynamic>);
  }

  Future<CropRecommendation> getById(String recommendationId) async {
    final response = await _client.get(ApiEndpoints.recommendationById(recommendationId));
    return CropRecommendation.fromJson(response['data'] as Map<String, dynamic>);
  }
}
