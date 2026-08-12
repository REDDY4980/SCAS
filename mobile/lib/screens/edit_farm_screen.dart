import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../models/farm.dart';
import '../providers/farm_provider.dart';
import '../providers/repository_providers.dart';
import '../services/api_exception.dart';
import '../widgets/common_widgets.dart';

/// Edit Farm — lets a farmer fix a farm's location text (District/State,
/// or any other field) after the fact, e.g. if weather ever fails to
/// load. No coordinate fields: same plain-text fields as farm creation.
/// Editing District/State without also supplying coordinates triggers
/// FarmService's automatic re-geocoding server-side.
class EditFarmScreen extends ConsumerStatefulWidget {
  final String farmId;
  const EditFarmScreen({super.key, required this.farmId});

  @override
  ConsumerState<EditFarmScreen> createState() => _EditFarmScreenState();
}

class _EditFarmScreenState extends ConsumerState<EditFarmScreen> {
  final _formKey = GlobalKey<FormState>();
  final _nameController = TextEditingController();
  final _stateController = TextEditingController();
  final _districtController = TextEditingController();
  final _villageController = TextEditingController();
  final _soilTypeController = TextEditingController();
  final _areaController = TextEditingController();

  bool _loading = true;
  bool _submitting = false;
  String? _loadError;
  String? _submitError;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) => _load());
  }

  Future<void> _load() async {
    setState(() {
      _loading = true;
      _loadError = null;
    });
    try {
      final farm = await ref.read(farmRepositoryProvider).getFarm(widget.farmId);
      _nameController.text = farm.farmName;
      _stateController.text = farm.state;
      _districtController.text = farm.district;
      _villageController.text = farm.village ?? '';
      _soilTypeController.text = farm.soilType ?? '';
      _areaController.text = farm.areaAcres?.toString() ?? '';
      if (!mounted) return;
      setState(() => _loading = false);
    } on ApiException catch (e) {
      if (!mounted) return;
      setState(() {
        _loadError = e.message;
        _loading = false;
      });
    }
  }

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
      _submitError = null;
    });
    try {
      // No latitude/longitude here on purpose — omitting them (rather
      // than resending stale values) is what tells the backend it's
      // safe to re-resolve location from the edited District/State.
      final updated = Farm(
        id: widget.farmId,
        userId: '',
        farmName: _nameController.text.trim(),
        state: _stateController.text.trim(),
        district: _districtController.text.trim(),
        village: _villageController.text.trim().isEmpty ? null : _villageController.text.trim(),
        soilType: _soilTypeController.text.trim().isEmpty ? null : _soilTypeController.text.trim(),
        areaAcres: double.tryParse(_areaController.text),
        createdAt: DateTime.now(),
        updatedAt: DateTime.now(),
      );
      await ref.read(farmListProvider.notifier).updateFarm(widget.farmId, updated);
      if (mounted) context.pop();
    } on ApiException catch (e) {
      setState(() => _submitError = e.message);
    } finally {
      if (mounted) setState(() => _submitting = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Edit Farm')),
      body: _loading
          ? const LoadingView()
          : _loadError != null
              ? ErrorView(message: _loadError!, onRetry: _load)
              : SingleChildScrollView(
                  padding: const EdgeInsets.all(20),
                  child: Form(
                    key: _formKey,
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.stretch,
                      children: [
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
                            "If weather isn't loading for this farm, double-check the "
                            'State and District spelling above — we use them to find '
                            'your farm automatically.',
                            style: Theme.of(context).textTheme.bodySmall,
                          ),
                        ),
                        if (_submitError != null) ...[
                          const SizedBox(height: 8),
                          Text(_submitError!, style: TextStyle(color: Theme.of(context).colorScheme.error)),
                        ],
                        const SizedBox(height: 20),
                        PrimaryButton(label: 'Save Changes', onPressed: _submit, isLoading: _submitting),
                      ],
                    ),
                  ),
                ),
    );
  }
}
