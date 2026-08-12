import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../models/history.dart';
import '../providers/repository_providers.dart';
import '../services/api_exception.dart';
import '../widgets/common_widgets.dart';

final historyListProvider = FutureProvider.autoDispose<List<HistorySummary>>((ref) {
  return ref.watch(historyRepositoryProvider).list();
});

/// SCR-010 History.
/// Primary Components: List/search/filter.
/// Backend/API Mapping: GET /history.
/// Acceptance Criteria: Persistent storage (already true server-side —
/// this screen just displays it).
class HistoryScreen extends ConsumerWidget {
  const HistoryScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final historyAsync = ref.watch(historyListProvider);

    return Scaffold(
      appBar: AppBar(title: const Text('Analysis History')),
      body: historyAsync.when(
        loading: () => const LoadingView(),
        error: (e, _) => ErrorView(
          message: e is ApiException ? e.message : e.toString(),
          onRetry: () => ref.invalidate(historyListProvider),
        ),
        data: (entries) {
          if (entries.isEmpty) {
            return const EmptyView(
              message: 'No analyses yet. Upload a soil report to get started.',
              icon: Icons.history_outlined,
            );
          }
          return RefreshIndicator(
            onRefresh: () async => ref.invalidate(historyListProvider),
            child: ListView.builder(
              padding: const EdgeInsets.all(16),
              itemCount: entries.length,
              itemBuilder: (context, index) {
                final entry = entries[index];
                return Card(
                  child: ListTile(
                    leading: CircleAvatar(
                      child: Text(entry.recommendedCrop.isNotEmpty
                          ? entry.recommendedCrop[0].toUpperCase()
                          : '?'),
                    ),
                    title: Text(entry.recommendedCrop[0].toUpperCase() +
                        entry.recommendedCrop.substring(1)),
                    subtitle: Text(
                      '${entry.farmName} • ${_formatDate(entry.createdAt)}',
                    ),
                    trailing: ConfidenceBadge(confidence: entry.confidenceScore),
                    onTap: () => context.push('/history/${entry.id}'),
                  ),
                );
              },
            ),
          );
        },
      ),
    );
  }

  String _formatDate(DateTime dt) {
    final local = dt.toLocal();
    return '${local.day}/${local.month}/${local.year}';
  }
}
