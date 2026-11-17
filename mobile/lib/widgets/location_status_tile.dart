import 'package:flutter/material.dart';

import '../services/location_service.dart';
import '../theme/app_colors.dart';

/// Shows the farmer whether their location was detected, and why not if
/// it failed, with a Try again button. Used on the farm forms.
class LocationStatusTile extends StatelessWidget {
  final bool detecting;
  final LocationResult? result;
  final VoidCallback onRetry;

  const LocationStatusTile({super.key, required this.detecting, required this.result, required this.onRetry});

  @override
  Widget build(BuildContext context) {
    final ok = result?.ok ?? false;
    final icon = detecting
        ? const SizedBox(width: 20, height: 20, child: CircularProgressIndicator(strokeWidth: 2))
        : Icon(ok ? Icons.my_location : Icons.location_off_outlined,
            color: ok ? AppColors.primary : Theme.of(context).colorScheme.error);
    final text = detecting
        ? 'Detecting your location... please tap Allow if asked.'
        : ok
            ? '${result!.message}. It will be saved with this farm.'
            : '${result?.message ?? 'Location not detected.'} '
                'Without it, we will use the district you type (less accurate weather).';
    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: ok ? AppColors.surfaceMuted : Theme.of(context).colorScheme.errorContainer.withOpacity(0.35),
        borderRadius: BorderRadius.circular(10),
      ),
      child: Row(
        children: [
          icon,
          const SizedBox(width: 12),
          Expanded(child: Text(text, style: Theme.of(context).textTheme.bodySmall)),
          if (!detecting && !ok) TextButton(onPressed: onRetry, child: const Text('Try again')),
        ],
      ),
    );
  }
}
