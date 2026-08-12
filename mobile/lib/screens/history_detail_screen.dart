import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../models/history.dart';
import '../providers/repository_providers.dart';
import '../services/api_exception.dart';
import '../widgets/common_widgets.dart';

final historyDetailProvider =
    FutureProvider.autoDispose.family<HistoryDetail, String>((ref, recommendationId) {
  return ref.watch(historyRepositoryProvider).getDetail(recommendationId);
});

/// History detail — Vol 3.3: "History always links back to
/// recommendation details." Combines soil parameters, weather, and
/// fertilizer recommendations from that single past analysis.
class HistoryDetailScreen extends ConsumerWidget {
  final String recommendationId;
  const HistoryDetailScreen({super.key, required this.recommendationId});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final detailAsync = ref.watch(historyDetailProvider(recommendationId));

    return Scaffold(
      appBar: AppBar(title: const Text('Analysis Detail')),
      body: detailAsync.when(
        loading: () => const LoadingView(),
        error: (e, _) => ErrorView(
          message: e is ApiException ? e.message : e.toString(),
          onRetry: () => ref.invalidate(historyDetailProvider(recommendationId)),
        ),
        data: (detail) => _buildDetail(context, detail),
      ),
    );
  }

  Widget _buildDetail(BuildContext context, HistoryDetail detail) {
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
                    Text(
                      detail.recommendedCrop[0].toUpperCase() + detail.recommendedCrop.substring(1),
                      style: Theme.of(context).textTheme.headlineSmall,
                    ),
                    ConfidenceBadge(confidence: detail.confidenceScore),
                  ],
                ),
                Text(detail.farmName, style: Theme.of(context).textTheme.bodyMedium),
                const SizedBox(height: 12),
                Text(detail.reasoning),
              ],
            ),
          ),
        ),
        if (detail.soilParameters != null) ...[
          const SizedBox(height: 20),
          Text('Soil Parameters', style: Theme.of(context).textTheme.titleMedium),
          const SizedBox(height: 8),
          Card(
            child: Padding(
              padding: const EdgeInsets.all(16),
              child: Wrap(
                spacing: 16,
                runSpacing: 8,
                children: [
                  _stat('pH', detail.soilParameters!.ph),
                  _stat('EC', detail.soilParameters!.ec),
                  _stat('Organic Carbon', detail.soilParameters!.organicCarbon, unit: '%'),
                  _stat('Nitrogen', detail.soilParameters!.nitrogen, unit: 'kg/ha'),
                  _stat('Phosphorus', detail.soilParameters!.phosphorus, unit: 'kg/ha'),
                  _stat('Potassium', detail.soilParameters!.potassium, unit: 'kg/ha'),
                ],
              ),
            ),
          ),
        ],
        if (detail.weather != null) ...[
          const SizedBox(height: 20),
          Text('Weather Conditions', style: Theme.of(context).textTheme.titleMedium),
          const SizedBox(height: 8),
          Card(
            child: Padding(
              padding: const EdgeInsets.all(16),
              child: Wrap(
                spacing: 16,
                runSpacing: 8,
                children: [
                  _stat('Temperature', detail.weather!.temperature, unit: '°C'),
                  _stat('Humidity', detail.weather!.humidity, unit: '%'),
                  _stat('Rainfall', detail.weather!.rainfall, unit: 'mm'),
                ],
              ),
            ),
          ),
        ],
        if (detail.fertilizerRecommendations.isNotEmpty) ...[
          const SizedBox(height: 20),
          Text('Fertilizer Recommendations', style: Theme.of(context).textTheme.titleMedium),
          const SizedBox(height: 8),
          for (final f in detail.fertilizerRecommendations)
            Card(
              child: ListTile(
                title: Text(f.fertilizerName),
                subtitle: Text('${f.dosage}\n${f.reason}'),
                isThreeLine: true,
              ),
            ),
        ],
      ],
    );
  }

  Widget _stat(String label, double? value, {String unit = ''}) {
    return SizedBox(
      width: 140,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(label, style: const TextStyle(fontSize: 12, color: Colors.grey)),
          Text(value != null ? '${value.toStringAsFixed(2)} $unit' : '—'),
        ],
      ),
    );
  }
}
