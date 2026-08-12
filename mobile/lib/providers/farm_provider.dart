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
    // copyWithPrevious, not a bare AsyncValue.loading(): a reload (after
    // creating/deleting a farm, or pull-to-refresh) must keep hasValue
    // true with the last-known list while it refetches. app_router.dart's
    // redirect treats "loading with no value yet" as "still resolving
    // the very first farms fetch after login" and detours to splash —
    // without this, every later reload would incorrectly retrigger that
    // detour and bounce the farmer off whatever screen they're on.
    state = AsyncValue<List<Farm>>.loading().copyWithPrevious(state);
    try {
      final farms = await _repo.listFarms();
      state = AsyncValue.data(farms);
    } catch (e, st) {
      state = AsyncValue<List<Farm>>.error(e, st).copyWithPrevious(state);
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
