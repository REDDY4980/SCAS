/// Matches app/schemas/market.py exactly.
class MarketCrop {
  final String crop;
  final bool hasCurrentPrice;
  final bool seasonalForecastAvailable;
  final String? scope;

  const MarketCrop({required this.crop, required this.hasCurrentPrice, required this.seasonalForecastAvailable, this.scope});

  factory MarketCrop.fromJson(Map<String, dynamic> json) => MarketCrop(
        crop: json['crop'] as String,
        hasCurrentPrice: json['has_current_price'] as bool? ?? false,
        seasonalForecastAvailable: json['seasonal_forecast_available'] as bool? ?? false,
        scope: json['scope'] as String?,
      );
}

class ForecastPoint {
  final String month;
  final String label;
  final double expectedPrice;
  final double changePct;

  const ForecastPoint({required this.month, required this.label, required this.expectedPrice, required this.changePct});

  factory ForecastPoint.fromJson(Map<String, dynamic> json) => ForecastPoint(
        month: json['month'] as String,
        label: json['label'] as String,
        expectedPrice: (json['expected_price'] as num).toDouble(),
        changePct: (json['change_pct'] as num).toDouble(),
      );
}

class MarketOutlook {
  final String crop;
  final String unit;
  final double currentPrice;
  final double priceLow;
  final double priceHigh;
  final String scope;
  final String asOf;
  final int nRecords;
  final bool seasonalForecastAvailable;
  final List<ForecastPoint> forecast;
  final String? bestMonth;
  final double? expectedGainPct;
  final String trend; // rising | falling | stable | unknown
  final String action; // hold | sell_now | time_harvest | sell_when_ready
  final String advice;
  final bool perishable;
  final double? backtestMape;
  final double? naiveMape;
  final List<String> sources;
  final List<String> caveats;

  const MarketOutlook({
    required this.crop,
    required this.unit,
    required this.currentPrice,
    required this.priceLow,
    required this.priceHigh,
    required this.scope,
    required this.asOf,
    required this.nRecords,
    required this.seasonalForecastAvailable,
    required this.forecast,
    this.bestMonth,
    this.expectedGainPct,
    required this.trend,
    required this.action,
    required this.advice,
    required this.perishable,
    this.backtestMape,
    this.naiveMape,
    required this.sources,
    required this.caveats,
  });

  factory MarketOutlook.fromJson(Map<String, dynamic> json) => MarketOutlook(
        crop: json['crop'] as String,
        unit: json['unit'] as String,
        currentPrice: (json['current_price'] as num).toDouble(),
        priceLow: (json['price_low'] as num).toDouble(),
        priceHigh: (json['price_high'] as num).toDouble(),
        scope: json['scope'] as String,
        asOf: json['as_of'] as String,
        nRecords: json['n_records'] as int,
        seasonalForecastAvailable: json['seasonal_forecast_available'] as bool,
        forecast: (json['forecast'] as List<dynamic>? ?? [])
            .map((e) => ForecastPoint.fromJson(e as Map<String, dynamic>))
            .toList(),
        bestMonth: json['best_month'] as String?,
        expectedGainPct: (json['expected_gain_pct'] as num?)?.toDouble(),
        trend: json['trend'] as String,
        action: json['action'] as String,
        advice: json['advice'] as String,
        perishable: json['perishable'] as bool? ?? false,
        backtestMape: (json['backtest_mape'] as num?)?.toDouble(),
        naiveMape: (json['naive_mape'] as num?)?.toDouble(),
        sources: (json['sources'] as List<dynamic>? ?? []).cast<String>(),
        caveats: (json['caveats'] as List<dynamic>? ?? []).cast<String>(),
      );
}
