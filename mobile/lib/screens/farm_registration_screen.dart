import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:google_fonts/google_fonts.dart';

import '../models/farm.dart';
import '../providers/auth_provider.dart';
import '../providers/farm_provider.dart';
import '../services/api_exception.dart';
import '../services/location_service.dart';
import '../theme/app_colors.dart';
import '../widgets/common_widgets.dart';

/// First-run gate (app_router.dart): a freshly-registered/logged-in
/// user with zero farms lands here instead of the dashboard — the
/// dashboard's weather/recommendation flow is meaningless without at
/// least one farm. Same fields and no-coordinates policy as the
/// "Add Farm" sheet on FarmManagementScreen: farmers never see or type
/// latitude/longitude. Location is captured silently via one GPS
/// permission prompt here, or resolved server-side from district/state
/// if denied — see FarmService._resolve_coordinates.
class FarmRegistrationScreen extends ConsumerStatefulWidget {
  const FarmRegistrationScreen({super.key});

  @override
  ConsumerState<FarmRegistrationScreen> createState() => _FarmRegistrationScreenState();
}

class _FarmRegistrationScreenState extends ConsumerState<FarmRegistrationScreen> {
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
      // Silent, best-effort, ONE-TIME: a single permission prompt here
      // at registration, never repeated on later logins. If denied or
      // unavailable, coordinates stay null and the backend resolves an
      // approximate location from District/State instead — either way
      // the farmer never sees a coordinate field.
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
      // No explicit navigation needed: app_router.dart's redirect
      // re-evaluates the moment farmListProvider's data changes (it's
      // wired into the router's refreshListenable) and sends the user
      // on to the dashboard automatically now that farms is non-empty.
    } on ApiException catch (e) {
      setState(() => _error = e.message);
    } finally {
      if (mounted) setState(() => _submitting = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: SafeArea(
        child: SingleChildScrollView(
          padding: const EdgeInsets.all(24),
          child: Form(
            key: _formKey,
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                Row(
                  children: [
                    Expanded(
                      child: Text(
                        'Register your farm',
                        style: GoogleFonts.poppins(fontSize: 24, fontWeight: FontWeight.w800),
                      ),
                    ),
                    TextButton(
                      onPressed: _submitting
                          ? null
                          : () => ref.read(authProvider.notifier).logout(),
                      child: const Text('Log out'),
                    ),
                  ],
                ),
                const SizedBox(height: 6),
                Text(
                  "One last step — add your first farm so we can show you weather, "
                  "soil analysis, and crop recommendations for it.",
                  style: GoogleFonts.poppins(color: AppColors.textSecondary, fontSize: 13),
                ),
                const SizedBox(height: 28),
                Text('Farm name *', style: GoogleFonts.poppins(fontWeight: FontWeight.w700, fontSize: 13)),
                const SizedBox(height: 8),
                TextFormField(
                  controller: _nameController,
                  decoration: const InputDecoration(hintText: "e.g. Ramesh's Farm"),
                  validator: (v) => (v == null || v.trim().isEmpty) ? 'Required' : null,
                ),
                const SizedBox(height: 18),
                Row(
                  children: [
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text('State *', style: GoogleFonts.poppins(fontWeight: FontWeight.w700, fontSize: 13)),
                          const SizedBox(height: 8),
                          TextFormField(
                            controller: _stateController,
                            decoration: const InputDecoration(hintText: 'Karnataka'),
                            validator: (v) => (v == null || v.trim().isEmpty) ? 'Required' : null,
                          ),
                        ],
                      ),
                    ),
                    const SizedBox(width: 12),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text('District *', style: GoogleFonts.poppins(fontWeight: FontWeight.w700, fontSize: 13)),
                          const SizedBox(height: 8),
                          TextFormField(
                            controller: _districtController,
                            decoration: const InputDecoration(hintText: 'Bagalkote'),
                            validator: (v) => (v == null || v.trim().isEmpty) ? 'Required' : null,
                          ),
                        ],
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 18),
                Text('Village (optional)', style: GoogleFonts.poppins(fontWeight: FontWeight.w700, fontSize: 13)),
                const SizedBox(height: 8),
                TextFormField(controller: _villageController),
                const SizedBox(height: 18),
                Row(
                  children: [
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text('Soil type (optional)', style: GoogleFonts.poppins(fontWeight: FontWeight.w700, fontSize: 13)),
                          const SizedBox(height: 8),
                          TextFormField(controller: _soilTypeController, decoration: const InputDecoration(hintText: 'Black Soil')),
                        ],
                      ),
                    ),
                    const SizedBox(width: 12),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text('Area (acres)', style: GoogleFonts.poppins(fontWeight: FontWeight.w700, fontSize: 13)),
                          const SizedBox(height: 8),
                          TextFormField(
                            controller: _areaController,
                            keyboardType: const TextInputType.numberWithOptions(decimal: true),
                          ),
                        ],
                      ),
                    ),
                  ],
                ),
                Padding(
                  padding: const EdgeInsets.only(top: 12),
                  child: Text(
                    "We'll automatically detect your farm's location for weather forecasts.",
                    style: GoogleFonts.poppins(fontSize: 12, color: AppColors.textSecondary),
                  ),
                ),
                if (_error != null) ...[
                  const SizedBox(height: 12),
                  Text(_error!, style: TextStyle(color: Theme.of(context).colorScheme.error)),
                ],
                const SizedBox(height: 24),
                PrimaryButton(label: 'Save Farm', onPressed: _submit, isLoading: _submitting),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
