import '../constants/api_endpoints.dart';
import '../models/market.dart';
import '../services/api_client.dart';

class MarketRepository {
  final ApiClient _client = ApiClient.instance;

  Future<List<MarketCrop>> getCrops() async {
    final response = await _client.get(ApiEndpoints.marketCrops);
    final data = response['data'] as List<dynamic>? ?? [];
    return data.map((e) => MarketCrop.fromJson(e as Map<String, dynamic>)).toList();
  }

  Future<MarketOutlook> getOutlook(String crop, {int months = 6}) async {
    final response = await _client.get(ApiEndpoints.marketOutlook(crop), queryParameters: {'months': months});
    return MarketOutlook.fromJson(response['data'] as Map<String, dynamic>);
  }
}
