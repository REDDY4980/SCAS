import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../models/farm.dart';
import '../repositories/farm_repository.dart';
import 'repository_providers.dart';

/// Vol 13.4: "Responsibilities: ... " farm list state, refreshable.
class FarmListNotifier extends StateNotifier<AsyncValue<List<Farm>>> {
  final FarmRepository _repo;
  FarmListNotifier(this._repo) : super(const AsyncValue.loading()) {
    load();
  }

  Future<void> load() async {
    state = const AsyncValue.loading();
    try {
      final farms = await _repo.listFarms();
      state = AsyncValue.data(farms);
    } catch (e, st) {
      state = AsyncValue.error(e, st);
    }
  }

  Future<void> createFarm(Farm farm) async {
    await _repo.createFarm(farm);
    await load();
  }

  Future<void> updateFarm(String farmId, Farm farm) async {
    await _repo.updateFarm(farmId, farm);
    await load();
  }

  Future<void> deleteFarm(String farmId) async {
    await _repo.deleteFarm(farmId);
    await load();
  }
}

final farmListProvider = StateNotifierProvider<FarmListNotifier, AsyncValue<List<Farm>>>((ref) {
  return FarmListNotifier(ref.watch(farmRepositoryProvider));
});

/// Vol 13.7 "Recent farm selection" — the farm currently being worked
/// with across Upload -> AI Analysis -> Recommendation -> Fertilizer.
final selectedFarmIdProvider = StateProvider<String?>((ref) => null);
