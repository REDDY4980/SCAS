import '../constants/api_endpoints.dart';
import '../models/history.dart';
import '../services/api_client.dart';

class HistoryRepository {
  final ApiClient _client = ApiClient.instance;

  Future<List<HistorySummary>> list({String? farmId, int limit = 50}) async {
    final response = await _client.get(
      ApiEndpoints.history,
      queryParameters: {if (farmId != null) 'farm_id': farmId, 'limit': limit},
    );
    final data = response['data'] as List<dynamic>? ?? [];
    return data.map((e) => HistorySummary.fromJson(e as Map<String, dynamic>)).toList();
  }

  Future<HistoryDetail> getDetail(String recommendationId) async {
    final response = await _client.get(ApiEndpoints.historyDetail(recommendationId));
    return HistoryDetail.fromJson(response['data'] as Map<String, dynamic>);
  }
}
