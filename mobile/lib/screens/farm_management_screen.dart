import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../models/farm.dart';
import '../providers/farm_provider.dart';
import '../routes/app_router.dart';
import '../services/api_exception.dart';
import '../services/location_service.dart';
import '../widgets/common_widgets.dart';

/// SCR-005 Farm Management.
/// Primary Components: Farm location, soil type, acreage.
/// Backend/API Mapping: POST/PUT /farms.
/// Acceptance Criteria: One user can manage multiple farms.
class FarmManagementScreen extends ConsumerWidget {
  const FarmManagementScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final farmsAsync = ref.watch(farmListProvider);

    return Scaffold(
      appBar: AppBar(title: const Text('My Farms')),
      body: farmsAsync.when(
        loading: () => const LoadingView(),
        error: (e, _) => ErrorView(
          message: e.toString(),
          onRetry: () => ref.read(farmListProvider.notifier).load(),
        ),
        data: (farms) {
          if (farms.isEmpty) {
            return const EmptyView(
              message: 'No farms yet. Tap + to add your first farm.',
              icon: Icons.agriculture_outlined,
            );
          }
          return RefreshIndicator(
            onRefresh: () => ref.read(farmListProvider.notifier).load(),
            child: ListView.builder(
              padding: const EdgeInsets.all(16),
              itemCount: farms.length,
              itemBuilder: (context, index) {
                final farm = farms[index];
                return Card(
                  child: ListTile(
                    leading: const Icon(Icons.landscape_outlined),
                    title: Text(farm.farmName),
                    subtitle: Text(
                      '${farm.district}, ${farm.state}'
                      '${farm.soilType != null ? ' • ${farm.soilType}' : ''}'
                      '${farm.areaAcres != null ? ' • ${farm.areaAcres} acres' : ''}',
                    ),
                    trailing: Row(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        if (!farm.hasCoordinates)
                          IconButton(
                            icon: const Icon(Icons.warning_amber, color: Colors.orange, size: 20),
                            tooltip: "Weather isn't available yet — tap to check this farm's location",
                            onPressed: () => context.push('/farms/${farm.id}/edit'),
                          ),
                        IconButton(
                          icon: const Icon(Icons.edit_outlined),
                          tooltip: 'Edit farm',
                          onPressed: () => context.push('/farms/${farm.id}/edit'),
                        ),
                        IconButton(
                          icon: const Icon(Icons.delete_outline),
                          onPressed: () => _confirmDelete(context, ref, farm),
                        ),
                      ],
                    ),
                    onTap: () => context.push('${AppRoutes.upload}?farmId=${farm.id}'),
                  ),
                );
              },
            ),
          );
        },
      ),
      floatingActionButton: FloatingActionButton.extended(
        onPressed: () => _showCreateFarmSheet(context, ref),
        icon: const Icon(Icons.add),
        label: const Text('Add Farm'),
      ),
    );
  }

  void _confirmDelete(BuildContext context, WidgetRef ref, Farm farm) {
    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Delete farm?'),
        content: Text('This will remove "${farm.farmName}" and its history.'),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx), child: const Text('Cancel')),
          FilledButton(
            onPressed: () {
              Navigator.pop(ctx);
              ref.read(farmListProvider.notifier).deleteFarm(farm.id);
            },
            child: const Text('Delete'),
          ),
        ],
      ),
    );
  }

  void _showCreateFarmSheet(BuildContext context, WidgetRef ref) {
    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      builder: (ctx) => const _CreateFarmSheet(),
    );
  }
}

class _CreateFarmSheet extends ConsumerStatefulWidget {
  const _CreateFarmSheet();

  @override
  ConsumerState<_CreateFarmSheet> createState() => _CreateFarmSheetState();
}

class _CreateFarmSheetState extends ConsumerState<_CreateFarmSheet> {
  final _formKey = GlobalKey<FormState>();
  final _nameController = TextEditingController();
  final _stateController = TextEditingController();
  final _districtController = TextEditingController();
  final _villageController = TextEditingController();
  final _soilTypeController = TextEditingController();
  final _areaController = TextEditingController();
  bool _submitting = false;
  String? _error;

  @override
  void dispose() {
    _nameController.dispose();
    _stateController.dispose();
    _districtController.dispose();
    _villageController.dispose();
    _soilTypeController.dispose();
    _areaController.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    if (!_formKey.currentState!.validate()) return;
    setState(() {
      _submitting = true;
      _error = null;
    });
    try {
      // Silent, best-effort: one permission prompt, no coordinates ever
      // shown. If denied/unavailable, coords stay null and the backend
      // resolves an approximate location from District/State instead.
      final coords = await LocationService.tryGetCurrentCoordinates();
      final farm = Farm(
        id: '',
        userId: '',
        farmName: _nameController.text.trim(),
        state: _stateController.text.trim(),
        district: _districtController.text.trim(),
        village: _villageController.text.trim().isEmpty ? null : _villageController.text.trim(),
        soilType: _soilTypeController.text.trim().isEmpty ? null : _soilTypeController.text.trim(),
        areaAcres: double.tryParse(_areaController.text),
        latitude: coords?.$1,
        longitude: coords?.$2,
        createdAt: DateTime.now(),
        updatedAt: DateTime.now(),
      );
      await ref.read(farmListProvider.notifier).createFarm(farm);
      if (mounted) Navigator.pop(context);
    } on ApiException catch (e) {
      setState(() => _error = e.message);
    } finally {
      if (mounted) setState(() => _submitting = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: EdgeInsets.only(
        left: 24,
        right: 24,
        top: 24,
        bottom: MediaQuery.of(context).viewInsets.bottom + 24,
      ),
      child: SingleChildScrollView(
        child: Form(
          key: _formKey,
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              Text('Add a farm', style: Theme.of(context).textTheme.titleLarge),
              const SizedBox(height: 16),
              TextFormField(
                controller: _nameController,
                decoration: const InputDecoration(labelText: 'Farm name *'),
                validator: (v) => (v == null || v.trim().isEmpty) ? 'Required' : null,
              ),
              const SizedBox(height: 12),
              Row(
                children: [
                  Expanded(
                    child: TextFormField(
                      controller: _stateController,
                      decoration: const InputDecoration(labelText: 'State *'),
                      validator: (v) => (v == null || v.trim().isEmpty) ? 'Required' : null,
                    ),
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: TextFormField(
                      controller: _districtController,
                      decoration: const InputDecoration(labelText: 'District *'),
                      validator: (v) => (v == null || v.trim().isEmpty) ? 'Required' : null,
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 12),
              TextFormField(
                controller: _villageController,
                decoration: const InputDecoration(labelText: 'Village (optional)'),
              ),
              const SizedBox(height: 12),
              Row(
                children: [
                  Expanded(
                    child: TextFormField(
                      controller: _soilTypeController,
                      decoration: const InputDecoration(labelText: 'Soil type (optional)'),
                    ),
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: TextFormField(
                      controller: _areaController,
                      decoration: const InputDecoration(labelText: 'Area (acres)'),
                      keyboardType: const TextInputType.numberWithOptions(decimal: true),
                    ),
                  ),
                ],
              ),
              Padding(
                padding: const EdgeInsets.only(top: 4),
                child: Text(
                  "We'll automatically detect your farm's location for weather forecasts.",
                  style: Theme.of(context).textTheme.bodySmall,
                ),
              ),
              if (_error != null) ...[
                const SizedBox(height: 8),
                Text(_error!, style: TextStyle(color: Theme.of(context).colorScheme.error)),
              ],
              const SizedBox(height: 20),
              PrimaryButton(label: 'Save Farm', onPressed: _submit, isLoading: _submitting),
            ],
          ),
        ),
      ),
    );
  }
}
