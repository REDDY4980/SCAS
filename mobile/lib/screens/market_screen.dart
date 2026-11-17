import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:google_fonts/google_fonts.dart';

import '../localization/app_strings.dart';
import '../models/market.dart';
import '../providers/locale_provider.dart';
import '../providers/repository_providers.dart';
import '../services/api_exception.dart';
import '../theme/app_colors.dart';
import '../widgets/common_widgets.dart';

/// SCR-Market: price outlook and best time to sell (project Objective 3).
/// Backend/API Mapping: GET /market/crops, GET /market/{crop}/outlook.
/// A seasonal forecast is only drawn when the backend says it passed the
/// backtest; otherwise the screen shows the current price range and says why.
class MarketScreen extends ConsumerStatefulWidget {
  final String? initialCrop;
  const MarketScreen({super.key, this.initialCrop});

  @override
  ConsumerState<MarketScreen> createState() => _MarketScreenState();
}

class _MarketScreenState extends ConsumerState<MarketScreen> {
  List<MarketCrop> _crops = [];
  String? _crop;
  MarketOutlook? _outlook;
  String? _error;
  bool _loading = true;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) => _loadCrops());
  }

  Future<void> _loadCrops() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final crops = (await ref.read(marketRepositoryProvider).getCrops()).where((c) => c.hasCurrentPrice).toList();
      if (!mounted) return;
      final wanted = widget.initialCrop?.toLowerCase();
      _crops = crops;
      _crop = crops.any((c) => c.crop == wanted) ? wanted : (crops.isNotEmpty ? crops.first.crop : null);
      if (_crop != null) {
        await _loadOutlook(_crop!);
      } else {
        setState(() => _loading = false);
      }
    } on ApiException catch (e) {
      if (!mounted) return;
      setState(() {
        _error = e.message;
        _loading = false;
      });
    }
  }

  Future<void> _loadOutlook(String crop) async {
    setState(() {
      _crop = crop;
      _loading = true;
      _error = null;
    });
    try {
      final o = await ref.read(marketRepositoryProvider).getOutlook(crop);
      if (!mounted) return;
      setState(() {
        _outlook = o;
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
    final s = ref.watch(appStringsProvider);
    return Scaffold(
      backgroundColor: AppColors.background,
      appBar: AppBar(title: Text(s.t('marketPrices'))),
      body: _error != null
          ? ErrorView(message: _error!, onRetry: _loadCrops)
          : ListView(
              padding: const EdgeInsets.all(16),
              children: [
                if (_crops.isNotEmpty)
                  DropdownButtonFormField<String>(
                    value: _crop,
                    decoration: InputDecoration(labelText: s.t('selectCrop'), filled: true, fillColor: AppColors.surface),
                    items: [
                      for (final c in _crops)
                        DropdownMenuItem(
                          value: c.crop,
                          child: Text('${_cap(c.crop)}${c.seasonalForecastAvailable ? '  •  forecast' : ''}'),
                        ),
                    ],
                    onChanged: (v) => v == null ? null : _loadOutlook(v),
                  ),
                const SizedBox(height: 16),
                if (_loading)
                  const Padding(padding: EdgeInsets.only(top: 48), child: LoadingView(message: 'Reading mandi prices...'))
                else if (_outlook != null)
                  ..._buildOutlook(context, _outlook!, s),
              ],
            ),
    );
  }

  List<Widget> _buildOutlook(BuildContext context, MarketOutlook o, AppStrings s) {
    final text = Theme.of(context).textTheme;
    return [
      // Current price
      Card(
        color: AppColors.primaryDark,
        child: Padding(
          padding: const EdgeInsets.all(20),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(s.t('currentPrice'), style: GoogleFonts.poppins(color: AppColors.textOnDarkMuted, fontSize: 13)),
              const SizedBox(height: 4),
              Text('₹${_fmt(o.currentPrice)} / quintal',
                  style: GoogleFonts.poppins(color: AppColors.textOnDark, fontSize: 26, fontWeight: FontWeight.w800)),
              const SizedBox(height: 4),
              Text('Most mandis: ₹${_fmt(o.priceLow)} – ₹${_fmt(o.priceHigh)}',
                  style: GoogleFonts.poppins(color: AppColors.textOnDarkMuted, fontSize: 13)),
              Text('${o.scope} · ${o.nRecords} records · as of ${o.asOf}',
                  style: GoogleFonts.poppins(color: AppColors.textOnDarkMuted, fontSize: 12)),
            ],
          ),
        ),
      ),
      const SizedBox(height: 12),
      // Decision
      Card(
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Icon(_actionIcon(o.action), color: AppColors.primary, size: 28),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text('${s.t('whenToSell')}: ${_actionLabel(o)}', style: text.titleSmall),
                    const SizedBox(height: 6),
                    Text(o.advice),
                  ],
                ),
              ),
            ],
          ),
        ),
      ),
      const SizedBox(height: 12),
      // Forecast
      if (o.seasonalForecastAvailable && o.forecast.isNotEmpty) ...[
        Text(s.t('priceOutlook'), style: text.titleMedium),
        const SizedBox(height: 8),
        Card(
          child: Padding(
            padding: const EdgeInsets.all(16),
            child: Column(children: [
              _ForecastBars(points: o.forecast, current: o.currentPrice, best: o.bestMonth),
              const SizedBox(height: 8),
              if (o.backtestMape != null && o.naiveMape != null)
                Text(
                  'Tested on past prices: average error ${(o.backtestMape! * 100).toStringAsFixed(0)}% '
                  '(vs ${(o.naiveMape! * 100).toStringAsFixed(0)}% if you assume prices stay the same).',
                  style: text.bodySmall,
                ),
            ]),
          ),
        ),
      ],
      const SizedBox(height: 12),
      for (final c in o.caveats)
        Padding(
          padding: const EdgeInsets.only(bottom: 4),
          child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
            const Icon(Icons.info_outline, size: 16, color: AppColors.textSecondary),
            const SizedBox(width: 6),
            Expanded(child: Text(c, style: text.bodySmall)),
          ]),
        ),
      const SizedBox(height: 8),
      Text('Source: ${o.sources.join('; ')}', style: text.bodySmall),
    ];
  }

  static String _cap(String v) => v.isEmpty ? v : v[0].toUpperCase() + v.substring(1);
  static String _fmt(double v) => v.round().toString().replaceAllMapped(RegExp(r'(\d)(?=(\d{3})+$)'), (m) => '${m[1]},');

  static IconData _actionIcon(String action) => switch (action) {
        'hold' => Icons.inventory_2_outlined,
        'time_harvest' => Icons.event_outlined,
        'sell_now' => Icons.sell_outlined,
        _ => Icons.storefront_outlined,
      };

  static String _actionLabel(MarketOutlook o) => switch (o.action) {
        'hold' => 'hold until ${o.bestMonth}',
        'time_harvest' => 'aim harvest for ${o.bestMonth}',
        'sell_now' => 'sell now',
        _ => 'sell when ready',
      };
}

/// Simple bar chart of expected monthly prices (no chart package needed).
class _ForecastBars extends StatelessWidget {
  final List<ForecastPoint> points;
  final double current;
  final String? best;
  const _ForecastBars({required this.points, required this.current, this.best});

  @override
  Widget build(BuildContext context) {
    final all = [current, ...points.map((p) => p.expectedPrice)];
    final maxV = all.reduce((a, b) => a > b ? a : b);
    Widget bar(String label, double v, {bool now = false, bool highlight = false}) => Expanded(
          child: Column(mainAxisAlignment: MainAxisAlignment.end, children: [
            Text('₹${(v / 1000).toStringAsFixed(1)}k', style: const TextStyle(fontSize: 10)),
            const SizedBox(height: 2),
            Container(
              height: 110 * v / maxV,
              margin: const EdgeInsets.symmetric(horizontal: 3),
              decoration: BoxDecoration(
                color: now ? AppColors.textSecondary : (highlight ? AppColors.primaryDark : AppColors.primaryLight),
                borderRadius: BorderRadius.circular(4),
              ),
            ),
            const SizedBox(height: 4),
            Text(label.split(' ').first, style: const TextStyle(fontSize: 11)),
          ]),
        );
    return SizedBox(
      height: 160,
      child: Row(crossAxisAlignment: CrossAxisAlignment.end, children: [
        bar('Now', current, now: true),
        for (final p in points) bar(p.label, p.expectedPrice, highlight: p.label == best),
      ]),
    );
  }
}
