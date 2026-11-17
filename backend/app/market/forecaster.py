"""
Market price outlook and selling decision support (project Objective 3).

Data (built by ml/market/build_market_data.py from Government of India
Agmarknet / data.gov.in open data, see datasets/market/SOURCES.md):

  current_prices.csv  latest 30-day median mandi price per crop (Karnataka
                      when >= 20 records, otherwise all-India)
  seasonal_index.csv  month-of-year price index per crop (mean = 1.0)
  backtest.json       out-of-sample accuracy of the seasonal forecast vs a
                      naive "price stays the same" forecast

Method:
  expected_price(month m) = current_price * S(m) / S(reference month)

Validation gate: a seasonal forecast is ONLY shown for crops where it beat
the naive forecast in the backtest. For every other crop the outlook says so
plainly and gives the current price range instead of an unproven forecast.
"""

from __future__ import annotations

import calendar
import csv
import json
import logging
from dataclasses import dataclass, field
from datetime import date
from functools import lru_cache
from pathlib import Path

logger = logging.getLogger("scas.market")

_DEFAULT_DIR = Path(__file__).resolve().parents[3] / "datasets" / "market"

# A hold is only suggested when the expected gain clearly exceeds typical
# storage loss + interest for a small farmer (rule of thumb, documented).
HOLD_THRESHOLD_PCT = 8.0
TREND_THRESHOLD_PCT = 3.0
PERISHABLE = {"banana", "mango", "grapes", "watermelon", "muskmelon", "apple", "orange", "papaya", "pomegranate"}
UNIT = "INR per quintal"
SOURCES = [
    "Agmarknet daily mandi prices via data.gov.in (Government of India open data), Aug-Sep 2026",
    "Agmarknet monthly APMC prices, Maharashtra, Sep 2014 - Nov 2016 (seasonal pattern only)",
]


class UnknownCropError(KeyError):
    pass


@dataclass
class ForecastPoint:
    month: str          # "2026-11"
    label: str          # "Nov 2026"
    expected_price: float
    change_pct: float   # vs current price


@dataclass
class MarketOutlook:
    crop: str
    unit: str
    current_price: float
    price_range: tuple[float, float]
    scope: str
    as_of: str
    n_records: int
    seasonal_forecast_available: bool
    forecast: list[ForecastPoint] = field(default_factory=list)
    best_month: str | None = None
    expected_gain_pct: float | None = None
    trend: str = "unknown"
    action: str = "sell_when_ready"
    advice: str = ""
    perishable: bool = False
    backtest: dict | None = None
    sources: list[str] = field(default_factory=lambda: list(SOURCES))
    caveats: list[str] = field(default_factory=list)


def _month_add(year: int, month: int, k: int) -> tuple[int, int]:
    total = year * 12 + (month - 1) + k
    return total // 12, total % 12 + 1


class MarketForecaster:
    def __init__(self, data_dir: str | Path | None = None):
        self.data_dir = Path(data_dir) if data_dir else _DEFAULT_DIR
        self.prices: dict[str, dict] = {}
        with open(self.data_dir / "current_prices.csv", newline="") as f:
            for row in csv.DictReader(f):
                self.prices[row["crop"]] = row
        self.seasonal: dict[str, dict[int, float]] = {}
        with open(self.data_dir / "seasonal_index.csv", newline="") as f:
            for row in csv.DictReader(f):
                self.seasonal.setdefault(row["crop"], {})[int(row["month"])] = float(row["index"])
        bt = json.loads((self.data_dir / "backtest.json").read_text())
        self.backtest = bt.get("per_crop", {})
        self.validated = set(bt.get("crops_where_seasonal_beats_naive", []))

    # ----------------------------------------------------------------- API
    def crops(self) -> list[dict]:
        names = sorted(set(self.prices) | set(self.seasonal))
        return [{
            "crop": c,
            "has_current_price": c in self.prices,
            "seasonal_forecast_available": c in self.validated and c in self.seasonal and c in self.prices,
            "scope": self.prices.get(c, {}).get("scope"),
        } for c in names]

    def outlook(self, crop: str, months: int = 6) -> MarketOutlook:
        crop = crop.strip().lower()
        if crop not in self.prices:
            raise UnknownCropError(crop)
        p = self.prices[crop]
        price = float(p["median_price"])
        as_of = date.fromisoformat(p["last_date"])
        out = MarketOutlook(
            crop=crop, unit=UNIT, current_price=price, price_range=(float(p["p25"]), float(p["p75"])),
            scope=p["scope"], as_of=p["last_date"], n_records=int(p["n_records"]),
            seasonal_forecast_available=crop in self.validated and crop in self.seasonal,
            perishable=crop in PERISHABLE, backtest=self.backtest.get(crop),
        )
        if out.scope != "Karnataka":
            out.caveats.append("Fewer than 20 Karnataka records; the all-India median price is shown.")
        if out.n_records < 20:
            out.caveats.append(f"Only {out.n_records} price records - treat the price as indicative.")

        if not out.seasonal_forecast_available:
            out.trend = "unknown"
            out.action = "sell_when_ready"
            out.advice = (
                f"Current {crop} price is about Rs {price:,.0f}/quintal (most mandis between "
                f"Rs {out.price_range[0]:,.0f} and Rs {out.price_range[1]:,.0f}). "
                + (f"Past data shows no reliable seasonal pattern for {crop}, "
                   if crop in self.seasonal else f"There is not enough price history for {crop} to forecast, ")
                + "so there is no evidence that waiting will pay. Sell when ready and compare prices at nearby mandis."
            )
            if crop in self.seasonal:
                out.caveats.append("A seasonal model exists but did not beat a simple no-change forecast in testing, so it is not shown.")
            return out

        idx = self.seasonal[crop]
        ref_m = as_of.month
        for k in range(1, months + 1):
            y, m = _month_add(as_of.year, ref_m, k)
            exp = price * idx[m] / idx[ref_m]
            out.forecast.append(ForecastPoint(f"{y:04d}-{m:02d}", f"{calendar.month_abbr[m]} {y}",
                                              round(exp, 0), round(100 * (exp / price - 1), 1)))
        best = max(out.forecast, key=lambda f: f.expected_price)
        near = out.forecast[: min(3, len(out.forecast))]
        avg_near = sum(f.change_pct for f in near) / len(near)
        out.trend = "rising" if avg_near > TREND_THRESHOLD_PCT else "falling" if avg_near < -TREND_THRESHOLD_PCT else "stable"

        if best.change_pct < HOLD_THRESHOLD_PCT:
            out.best_month, out.expected_gain_pct = None, max(0.0, best.change_pct)
            out.action = "sell_now"
            out.advice = (f"Prices for {crop} are not expected to rise by more than {HOLD_THRESHOLD_PCT:.0f}% in the next "
                          f"{months} months. Selling now avoids storage loss and risk.")
        elif out.perishable:
            out.best_month, out.expected_gain_pct = best.label, best.change_pct
            out.action = "time_harvest"
            out.advice = (f"{crop.capitalize()} is perishable, so storing is not practical. Prices are usually highest "
                          f"around {best.label} (about {best.change_pct:+.0f}%). Plan sowing so the harvest falls near that month.")
        else:
            out.best_month, out.expected_gain_pct = best.label, best.change_pct
            out.action = "hold"
            out.advice = (f"Prices for {crop} usually rise towards {best.label} (about {best.change_pct:+.0f}% vs now). "
                          f"If you have dry, safe storage, holding until then may pay; otherwise sell now.")
        out.caveats.append("Seasonal pattern learnt from 2014-2016 APMC data; sudden policy or weather shocks are not predicted.")
        return out


@lru_cache
def get_market_forecaster() -> MarketForecaster:
    from app.core.config import get_settings

    path = get_settings().market_data_dir
    logger.info("Loading market data from %s", path or _DEFAULT_DIR)
    return MarketForecaster(path)
