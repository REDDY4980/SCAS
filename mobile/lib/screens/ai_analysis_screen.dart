import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:google_fonts/google_fonts.dart';

import '../config/app_config.dart';
import '../localization/app_strings.dart';
import '../models/soil_report.dart';
import '../providers/locale_provider.dart';
import '../providers/repository_providers.dart';
import '../routes/app_router.dart';
import '../services/api_exception.dart';
import '../theme/app_colors.dart';
import '../widgets/common_widgets.dart';

enum _Stage { ocr, review, results, proceeding, error }

/// SCR-007 AI Analysis. Real pipeline: OCR -> (manual review if needed)
/// -> "Extracted Health Status" results (matches reference design) ->
/// weather fetch -> crop recommendation (which itself runs the real
/// XGBoost model + agronomic rules, Phase 7).
///
/// Note: the reference design shows separate "Fertilizer Guide" and
/// "Recommended Crops" buttons from the results screen. Both lead to
/// the same next screen here because the real backend requires a crop
/// recommendation to exist before fertilizer advice can be generated
/// (Vol 11.4) — Fertilizer Guide can't skip ahead of that dependency.
class AiAnalysisScreen extends ConsumerStatefulWidget {
  final String farmId;
  final String reportId;
  const AiAnalysisScreen({super.key, required this.farmId, required this.reportId});

  @override
  ConsumerState<AiAnalysisScreen> createState() => _AiAnalysisScreenState();
}

class _AiAnalysisScreenState extends ConsumerState<AiAnalysisScreen> {
  _Stage _stage = _Stage.ocr;
  String? _errorMessage;
  OcrResult? _ocrResult;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) => _runOcr());
  }

  Future<void> _runOcr() async {
    setState(() {
      _stage = _Stage.ocr;
      _errorMessage = null;
    });
    try {
      final result = await ref.read(soilRepositoryProvider).triggerOcr(widget.reportId);
      if (!mounted) return;
      _showOcrResult(result);
    } on ApiException catch (e) {
      // The server may still be reading the report even though this
      // request ended: the connection dropped or timed out, or another
      // request for the same report is already running (409). Wait for
      // that run to finish instead of failing.
      final stillRunning = e.isNetworkError || e.statusCode == 409 || e.statusCode == 502 || e.statusCode == 504;
      final report = stillRunning ? await _waitForOcrToFinish() : null;
      if (!mounted) return;
      if (report != null) {
        _showOcrResult(_resultFromReport(report));
        return;
      }
      setState(() {
        _errorMessage = e.message;
        _stage = _Stage.error;
      });
    }
  }

  void _showOcrResult(OcrResult result) {
    setState(() {
      _ocrResult = result;
      _stage = result.needsManualReview ? _Stage.review : _Stage.results;
    });
  }

  OcrResult _resultFromReport(SoilReport report) => OcrResult(
        reportId: report.id,
        ocrStatus: report.ocrStatus,
        ocrConfidence: report.ocrConfidence ?? 0.0,
        soilParameters: report.soilParameters,
        warnings: const [],
        missingFields: const [],
      );

  /// Polls the report while the server reports it as `processing`.
  /// Returns the finished report, or null if it never started / finished.
  Future<SoilReport?> _waitForOcrToFinish() async {
    final deadline = DateTime.now().add(AppConfig.ocrTimeout);
    final repo = ref.read(soilRepositoryProvider);
    while (mounted && DateTime.now().isBefore(deadline)) {
      await Future<void>.delayed(AppConfig.ocrPollInterval);
      if (!mounted) return null;
      try {
        final report = await repo.getReport(widget.reportId);
        if (report.ocrStatus == 'processing') continue;
        if (report.ocrStatus == 'pending') return null; // the run never started
        return report;
      } on ApiException {
        continue; // transient (e.g. instance waking up) — keep waiting
      }
    }
    return null;
  }

  Future<void> _submitCorrection(SoilParameters corrected) async {
    setState(() => _stage = _Stage.ocr);
    try {
      final report = await ref.read(soilRepositoryProvider).correctReport(widget.reportId, corrected);
      if (!mounted) return;
      setState(() {
        _ocrResult = OcrResult(
          reportId: report.id,
          ocrStatus: report.ocrStatus,
          ocrConfidence: report.ocrConfidence ?? 1.0,
          soilParameters: report.soilParameters,
          warnings: const [],
          missingFields: const [],
        );
        _stage = _Stage.results;
      });
    } on ApiException catch (e) {
      setState(() {
        _errorMessage = e.message;
        _stage = _Stage.error;
      });
    }
  }

  Future<void> _proceedToRecommendation() async {
    setState(() {
      _stage = _Stage.proceeding;
      _errorMessage = null;
    });
    try {
      await ref.read(weatherRepositoryProvider).getCurrent(widget.farmId);
      if (!mounted) return;
      context.pushReplacement('${AppRoutes.cropRecommendation}?farmId=${widget.farmId}');
    } on ApiException catch (e) {
      setState(() {
        _errorMessage = e.message;
        _stage = _Stage.error;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    final s = ref.watch(appStringsProvider);
    return Scaffold(
      appBar: AppBar(title: Text(s.t('analyzingYourSoil'))),
      body: switch (_stage) {
        _Stage.ocr => const LoadingView(
            message: 'Reading your soil report (OCR)...\nThis can take a few minutes. Please keep this screen open.'),
        _Stage.proceeding => const LoadingView(message: 'Fetching local weather and generating your AI recommendation...'),
        _Stage.error => ErrorView(message: _errorMessage ?? 'Something went wrong.', onRetry: _runOcr),
        _Stage.review => _ManualReviewForm(ocrResult: _ocrResult!, onSubmit: _submitCorrection, s: s),
        _Stage.results => _SoilResultsView(ocrResult: _ocrResult!, onProceed: _proceedToRecommendation, s: s),
      },
    );
  }
}

/// "Extracted Health Status" screen — matches reference design exactly:
/// health status card with score circle, NPK & pH progress bars, two
/// action buttons.
class _SoilResultsView extends StatelessWidget {
  final OcrResult ocrResult;
  final VoidCallback onProceed;
  final AppStrings s;
  const _SoilResultsView({required this.ocrResult, required this.onProceed, required this.s});

  @override
  Widget build(BuildContext context) {
    final params = ocrResult.soilParameters;
    // Simple derived health label from how many core nutrients are
    // present and physically plausible — real data, honestly labeled
    // (not a fabricated "AI health score"; see Phase 8 completion doc
    // for why SCAS doesn't invent scores without a sourced basis).
    final coreValues = [params?.nitrogen, params?.phosphorus, params?.potassium, params?.organicCarbon];
    final presentCount = coreValues.where((v) => v != null).length;
    final healthLabel = presentCount == 4 ? 'Complete' : '$presentCount of 4 values read';

    return SingleChildScrollView(
      padding: const EdgeInsets.all(20),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Container(
            padding: const EdgeInsets.all(20),
            decoration: BoxDecoration(
              color: AppColors.surfaceMuted,
              borderRadius: BorderRadius.circular(AppRadii.card),
            ),
            child: Row(
              children: [
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(s.t('extractedHealthStatus'), style: GoogleFonts.poppins(fontSize: 12, color: AppColors.textSecondary)),
                      const SizedBox(height: 6),
                      Text(healthLabel, style: GoogleFonts.poppins(fontSize: 20, fontWeight: FontWeight.w800, color: AppColors.primary)),
                      Text(
                        'OCR confidence: ${(ocrResult.ocrConfidence * 100).toStringAsFixed(0)}%',
                        style: GoogleFonts.poppins(fontSize: 12, color: AppColors.textSecondary),
                      ),
                    ],
                  ),
                ),
                ScoreCircle(score: (ocrResult.ocrConfidence * 100).round()),
              ],
            ),
          ),
          const SizedBox(height: 24),
          Text(s.t('nutrientValues'), style: GoogleFonts.poppins(fontSize: 16, fontWeight: FontWeight.w800)),
          const SizedBox(height: 16),
          Container(
            padding: const EdgeInsets.all(18),
            decoration: BoxDecoration(color: AppColors.surface, borderRadius: BorderRadius.circular(AppRadii.card), border: Border.all(color: AppColors.borderLight)),
            child: Column(
              children: [
                NutrientBar(label: 'Nitrogen (N) — ${params?.nitrogen?.toStringAsFixed(0) ?? '—'} kg/ha', value: params?.nitrogen ?? 0, maxValue: 560),
                NutrientBar(label: 'Phosphorus (P) — ${params?.phosphorus?.toStringAsFixed(0) ?? '—'} kg/ha', value: params?.phosphorus ?? 0, maxValue: 50),
                NutrientBar(label: 'Potassium (K) — ${params?.potassium?.toStringAsFixed(0) ?? '—'} kg/ha', value: params?.potassium ?? 0, maxValue: 600),
                NutrientBar(label: 'pH Level — ${params?.ph?.toStringAsFixed(1) ?? '—'}', value: params?.ph ?? 0, maxValue: 14),
              ],
            ),
          ),
          const SizedBox(height: 24),
          Row(
            children: [
              Expanded(
                child: OutlinedButton(onPressed: onProceed, child: Text(s.t('fertilizerGuide'))),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: FilledButton(onPressed: onProceed, child: Text(s.t('recommendedCrops'))),
              ),
            ],
          ),
          const SizedBox(height: 8),
          Text(
            'Both continue to your AI crop recommendation first — fertilizer advice is generated from the recommended crop.',
            textAlign: TextAlign.center,
            style: GoogleFonts.poppins(fontSize: 11, color: AppColors.textSecondary),
          ),
        ],
      ),
    );
  }
}

/// Manual review form — Vol 7.11 "Low confidence -> editable extracted values."
class _ManualReviewForm extends StatefulWidget {
  final OcrResult ocrResult;
  final void Function(SoilParameters) onSubmit;
  final AppStrings s;
  const _ManualReviewForm({required this.ocrResult, required this.onSubmit, required this.s});

  @override
  State<_ManualReviewForm> createState() => _ManualReviewFormState();
}

class _ManualReviewFormState extends State<_ManualReviewForm> {
  final _formKey = GlobalKey<FormState>();
  late final Map<String, TextEditingController> _controllers;

  static const _mandatory = {'ph', 'ec', 'organicCarbon', 'nitrogen', 'phosphorus', 'potassium'};

  static const _fields = [
    ('ph', 'pH (0-14)'),
    ('ec', 'EC'),
    ('organicCarbon', 'Organic Carbon (%)'),
    ('nitrogen', 'Nitrogen (kg/ha)'),
    ('phosphorus', 'Phosphorus (kg/ha)'),
    ('potassium', 'Potassium (kg/ha)'),
    ('zinc', 'Zinc (ppm)'),
    ('iron', 'Iron (ppm)'),
    ('manganese', 'Manganese (ppm)'),
    ('copper', 'Copper (ppm)'),
    ('boron', 'Boron (ppm)'),
  ];

  @override
  void initState() {
    super.initState();
    final params = widget.ocrResult.soilParameters;
    _controllers = {for (final (key, _) in _fields) key: TextEditingController(text: _valueFor(params, key)?.toString() ?? '')};
  }

  double? _valueFor(SoilParameters? p, String key) {
    if (p == null) return null;
    return switch (key) {
      'ph' => p.ph,
      'ec' => p.ec,
      'organicCarbon' => p.organicCarbon,
      'nitrogen' => p.nitrogen,
      'phosphorus' => p.phosphorus,
      'potassium' => p.potassium,
      'zinc' => p.zinc,
      'iron' => p.iron,
      'manganese' => p.manganese,
      'copper' => p.copper,
      'boron' => p.boron,
      _ => null,
    };
  }

  @override
  void dispose() {
    for (final c in _controllers.values) {
      c.dispose();
    }
    super.dispose();
  }

  void _submit() {
    if (!_formKey.currentState!.validate()) return;
    double? parse(String key) => double.tryParse(_controllers[key]!.text);
    widget.onSubmit(SoilParameters(
      ph: parse('ph'),
      ec: parse('ec'),
      organicCarbon: parse('organicCarbon'),
      nitrogen: parse('nitrogen'),
      phosphorus: parse('phosphorus'),
      potassium: parse('potassium'),
      zinc: parse('zinc'),
      iron: parse('iron'),
      manganese: parse('manganese'),
      copper: parse('copper'),
      boron: parse('boron'),
    ));
  }

  @override
  Widget build(BuildContext context) {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(20),
      child: Form(
        key: _formKey,
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Container(
              padding: const EdgeInsets.all(14),
              decoration: BoxDecoration(color: AppColors.surfaceMuted, borderRadius: BorderRadius.circular(14)),
              child: Row(
                children: [
                  const Icon(Icons.info_outline, color: AppColors.primary),
                  const SizedBox(width: 12),
                  Expanded(
                    child: Text(
                      'Some values could not be read confidently '
                      '(confidence: ${(widget.ocrResult.ocrConfidence * 100).toStringAsFixed(0)}%). '
                      'Please check and correct them below.',
                      style: GoogleFonts.poppins(fontSize: 13),
                    ),
                  ),
                ],
              ),
            ),
            // Backend validation warnings (e.g. "different values for the
            // same parameter (zinc: 15, 0.27)") tell the farmer exactly
            // which values to check.
            for (final warning in widget.ocrResult.warnings) ...[
              const SizedBox(height: 10),
              Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Icon(Icons.warning_amber_rounded, color: AppColors.primary, size: 20),
                  const SizedBox(width: 10),
                  Expanded(child: Text(warning, style: GoogleFonts.poppins(fontSize: 12.5))),
                ],
              ),
            ],
            const SizedBox(height: 20),
            for (final (key, label) in _fields) ...[
              Text(label, style: GoogleFonts.poppins(fontWeight: FontWeight.w700, fontSize: 13)),
              const SizedBox(height: 6),
              TextFormField(
                controller: _controllers[key],
                decoration: InputDecoration(
                  // API field names are snake_case (organic_carbon); form keys are camelCase.
                  errorText: widget.ocrResult.missingFields
                          .contains(key.replaceAllMapped(RegExp('[A-Z]'), (m) => '_${m[0]!.toLowerCase()}'))
                      ? 'Missing — please enter'
                      : null,
                ),
                keyboardType: const TextInputType.numberWithOptions(decimal: true),
                // The six mandatory parameters must be filled in: the
                // backend keeps an incomplete report in review, and crop
                // recommendations need all of them.
                validator: (value) {
                  final text = value?.trim() ?? '';
                  if (text.isEmpty) return _mandatory.contains(key) ? 'Required — please enter' : null;
                  return double.tryParse(text) == null ? 'Enter a number' : null;
                },
              ),
              const SizedBox(height: 14),
            ],
            const SizedBox(height: 8),
            PrimaryButton(label: widget.s.t('saveAndContinue'), onPressed: _submit),
          ],
        ),
      ),
    );
  }
}
