import '../constants/api_endpoints.dart';
import '../models/weather.dart';
import '../services/api_client.dart';

class WeatherRepository {
  final ApiClient _client = ApiClient.instance;

  Future<WeatherSnapshot> getCurrent(String farmId) async {
    final response = await _client.get(ApiEndpoints.weatherCurrent, queryParameters: {'farm_id': farmId});
    return WeatherSnapshot.fromJson(response['data'] as Map<String, dynamic>);
  }

  Future<WeatherSnapshot> refresh(String farmId) async {
    final response = await _client.post(ApiEndpoints.weatherRefresh, queryParameters: {'farm_id': farmId});
    return WeatherSnapshot.fromJson(response['data'] as Map<String, dynamic>);
  }

  Future<List<WeatherSnapshot>> getHistory(String farmId) async {
    final response = await _client.get(ApiEndpoints.weatherHistory(farmId));
    final data = response['data'] as List<dynamic>? ?? [];
    return data.map((e) => WeatherSnapshot.fromJson(e as Map<String, dynamic>)).toList();
  }
}
