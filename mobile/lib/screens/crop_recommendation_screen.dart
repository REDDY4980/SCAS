import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../models/recommendation.dart';
import '../providers/repository_providers.dart';
import '../routes/app_router.dart';
import '../services/api_exception.dart';
import '../widgets/common_widgets.dart';

/// SCR-008 Crop Recommendation.
/// Primary Components: Top recommendations with confidence.
/// Backend/API Mapping: POST /recommendation (this is where ML+Rules run).
/// Acceptance Criteria: Every crop includes explanation.
class CropRecommendationScreen extends ConsumerStatefulWidget {
  final String farmId;
  const CropRecommendationScreen({super.key, required this.farmId});

  @override
  ConsumerState<CropRecommendationScreen> createState() => _CropRecommendationScreenState();
}

class _CropRecommendationScreenState extends ConsumerState<CropRecommendationScreen> {
  CropRecommendation? _result;
  String? _error;
  bool _loading = true;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) => _generate());
  }

  Future<void> _generate() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final result = await ref.read(recommendationRepositoryProvider).generate(widget.farmId);
      if (!mounted) return;
      setState(() {
        _result = result;
        _loading = false;
      });
    } on ApiException catch (e) {
      if (!mounted) return;
      setState(() {
        _error = e.message;
        _loading = false;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Crop Recommendation')),
      body: _loading
          ? const LoadingView(message: 'Running the hybrid AI model...')
          : _error != null
              ? ErrorView(message: _error!, onRetry: _generate)
              : _buildResults(context, _result!),
    );
  }

  Widget _buildResults(BuildContext context, CropRecommendation result) {
    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        Card(
          color: Theme.of(context).colorScheme.primaryContainer,
          child: Padding(
            padding: const EdgeInsets.all(20),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    Text('Recommended Crop', style: Theme.of(context).textTheme.labelLarge),
                    ConfidenceBadge(confidence: result.confidence),
                  ],
                ),
                const SizedBox(height: 8),
                Text(
                  result.primaryCrop[0].toUpperCase() + result.primaryCrop.substring(1),
                  style: Theme.of(context).textTheme.headlineMedium,
                ),
                const SizedBox(height: 12),
                Text(result.explanation),
              ],
            ),
          ),
        ),
        const SizedBox(height: 20),
        Text('Top 5 Alternatives', style: Theme.of(context).textTheme.titleMedium),
        const SizedBox(height: 8),
        for (final item in result.topRecommendations)
          Card(
            child: ExpansionTile(
              leading: ConfidenceBadge(confidence: item.confidence),
              title: Text(item.crop[0].toUpperCase() + item.crop.substring(1)),
              children: [
                Padding(
                  padding: const EdgeInsets.fromLTRB(16, 0, 16, 16),
                  child: Align(alignment: Alignment.centerLeft, child: Text(item.reason)),
                ),
              ],
            ),
          ),
        const SizedBox(height: 24),
        PrimaryButton(
          label: 'View Fertilizer Recommendation',
          icon: Icons.science_outlined,
          onPressed: result.id == null
              ? null
              : () => context.push(
                    '${AppRoutes.fertilizerRecommendation}?recommendationId=${result.id}',
                  ),
        ),
        const SizedBox(height: 8),
        Text(
          'Model version: ${result.modelVersion}',
          style: Theme.of(context).textTheme.bodySmall,
          textAlign: TextAlign.center,
        ),
      ],
    );
  }
}
