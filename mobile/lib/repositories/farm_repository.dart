import '../constants/api_endpoints.dart';
import '../models/farm.dart';
import '../services/api_client.dart';

class FarmRepository {
  final ApiClient _client = ApiClient.instance;

  Future<List<Farm>> listFarms() async {
    final response = await _client.get(ApiEndpoints.farms);
    final data = response['data'] as List<dynamic>? ?? [];
    return data.map((e) => Farm.fromJson(e as Map<String, dynamic>)).toList();
  }

  Future<Farm> getFarm(String farmId) async {
    final response = await _client.get(ApiEndpoints.farm(farmId));
    return Farm.fromJson(response['data'] as Map<String, dynamic>);
  }

  Future<Farm> createFarm(Farm farm) async {
    final response = await _client.post(ApiEndpoints.farms, data: farm.toCreateJson());
    return Farm.fromJson(response['data'] as Map<String, dynamic>);
  }

  Future<Farm> updateFarm(String farmId, Farm farm) async {
    final response = await _client.put(ApiEndpoints.farm(farmId), data: farm.toCreateJson());
    return Farm.fromJson(response['data'] as Map<String, dynamic>);
  }

  Future<void> deleteFarm(String farmId) => _client.delete(ApiEndpoints.farm(farmId));
}
