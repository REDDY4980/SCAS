import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../models/fertilizer.dart';
import '../providers/repository_providers.dart';
import '../routes/app_router.dart';
import '../services/api_exception.dart';
import '../widgets/common_widgets.dart';

/// SCR-009 Fertilizer Recommendation.
/// Primary Components: NPK deficiencies, dosage.
/// Backend/API Mapping: POST /fertilizer/{recommendation_id}.
/// Acceptance Criteria: Explain each fertilizer.
class FertilizerRecommendationScreen extends ConsumerStatefulWidget {
  final String recommendationId;
  const FertilizerRecommendationScreen({super.key, required this.recommendationId});

  @override
  ConsumerState<FertilizerRecommendationScreen> createState() =>
      _FertilizerRecommendationScreenState();
}

class _FertilizerRecommendationScreenState extends ConsumerState<FertilizerRecommendationScreen> {
  FertilizerRecommendation? _result;
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
      final result =
          await ref.read(fertilizerRepositoryProvider).generate(widget.recommendationId);
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
      appBar: AppBar(title: const Text('Fertilizer Recommendation')),
      body: _loading
          ? const LoadingView(message: 'Analyzing nutrient deficiencies...')
          : _error != null
              ? ErrorView(message: _error!, onRetry: _generate)
              : _buildResults(context, _result!),
      floatingActionButton: FloatingActionButton.extended(
        onPressed: () => context.go(AppRoutes.dashboard),
        icon: const Icon(Icons.check),
        label: const Text('Done'),
      ),
    );
  }

  Widget _buildResults(BuildContext context, FertilizerRecommendation result) {
    final isFallback = result.knowledgeBaseCoverage == 'fallback';

    return ListView(
      padding: const EdgeInsets.fromLTRB(16, 16, 16, 80),
      children: [
        if (result.deficiencyProfile.isNotEmpty) ...[
          Text('Soil Nutrient Status', style: Theme.of(context).textTheme.titleMedium),
          const SizedBox(height: 8),
          Wrap(
            spacing: 8,
            runSpacing: 8,
            children: result.deficiencyProfile.entries
                .map((e) => Chip(
                      label: Text('${e.key}: ${e.value}'),
                      backgroundColor: e.value == 'low'
                          ? Colors.red.withOpacity(0.12)
                          : e.value == 'medium'
                              ? Colors.orange.withOpacity(0.12)
                              : Colors.green.withOpacity(0.12),
                    ))
                .toList(),
          ),
          const SizedBox(height: 20),
        ],
        if (isFallback)
          Card(
            color: Theme.of(context).colorScheme.tertiaryContainer,
            child: const Padding(
              padding: EdgeInsets.all(12),
              child: Row(
                children: [
                  Icon(Icons.info_outline),
                  SizedBox(width: 12),
                  Expanded(
                    child: Text(
                      'A verified dosage is not yet available for this crop in our '
                      'knowledge base. The recommendations below tell you which '
                      'nutrient to address — please consult a local agricultural '
                      'extension officer for exact quantities.',
                    ),
                  ),
                ],
              ),
            ),
          ),
        const SizedBox(height: 12),
        for (final item in result.fertilizers)
          Card(
            child: Padding(
              padding: const EdgeInsets.all(16),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      Icon(
                        item.hasSourcedDosage ? Icons.check_circle_outline : Icons.help_outline,
                        color: item.hasSourcedDosage ? Colors.green : Colors.orange,
                      ),
                      const SizedBox(width: 8),
                      Expanded(
                        child: Text(item.fertilizerName, style: Theme.of(context).textTheme.titleMedium),
                      ),
                    ],
                  ),
                  const SizedBox(height: 8),
                  Text(item.dosage, style: Theme.of(context).textTheme.bodyMedium),
                  const SizedBox(height: 8),
                  Text(item.reason),
                  if (item.applicationMethod.isNotEmpty) ...[
                    const SizedBox(height: 8),
                    Text('Application: ${item.applicationMethod}',
                        style: Theme.of(context).textTheme.bodySmall),
                  ],
                  if (item.precautions.isNotEmpty) ...[
                    const SizedBox(height: 4),
                    Text(
                      'Caution: ${item.precautions}',
                      style: Theme.of(context)
                          .textTheme
                          .bodySmall
                          ?.copyWith(fontStyle: FontStyle.italic),
                    ),
                  ],
                  if (item.source.isNotEmpty) ...[
                    const SizedBox(height: 8),
                    Text('Source: ${item.source}', style: Theme.of(context).textTheme.labelSmall),
                  ],
                ],
              ),
            ),
          ),
      ],
    );
  }
}
