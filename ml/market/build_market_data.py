"""
Build the market-price artefacts used by the backend's market module.

Objective 3 of the project: "market prediction and decision support that
help farmers understand market trends and choose the best time to sell".

Inputs (both Government of India open data, Agmarknet via data.gov.in,
re-usable with attribution under the Government Open Data License - India):

  --history  Monthly APMC prices, Maharashtra, Sep 2014 - Nov 2016
             (Monthly_data_cmo.csv; mirror:
             https://github.com/vibhor98/Analysis-of-agricultural-trends-in-time-series-dataset)
             -> used ONLY for the month-of-year seasonal pattern of each crop.
  --recent   Daily mandi prices, all India, Jul - Sep 2026
             (mandi_prices_snapshot.csv; collector + mirror:
             https://github.com/herrrickshaw/agri-commodity-tracker)
             -> used for the CURRENT price level (Karnataka if enough records,
             otherwise all-India median).

Outputs (small CSV/JSON files committed under datasets/market/):

  seasonal_index.csv   crop, month, index, n_months      (index mean = 1.0)
  current_prices.csv   crop, scope, median_price, p25, p75, n_records, first_date, last_date
  backtest.json        out-of-sample accuracy of the seasonal forecast vs a naive forecast

Usage:
  python -m ml.market.build_market_data --history Monthly_data_cmo.csv \
      --recent mandi_prices_snapshot.csv --out datasets/market
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

# SCAS crop label -> commodity names in (recent Agmarknet feed, Maharashtra CMO history)
CROP_MAP: dict[str, tuple[list[str], list[str]]] = {
    "rice": (["paddy(common)"], ["paddy-unhusked"]),
    "maize": (["maize"], ["maize", "maize(corn.)", "maize (corn.)"]),
    "chickpea": (["bengal gram(gram)(whole)"], ["gram"]),
    "kidneybeans": (["kidney beans(rajma)"], []),
    "pigeonpeas": (["red gram/arhar/tur(whole)"], ["pigeon pea (tur)"]),
    "mothbeans": ([], []),
    "mungbean": (["green gram(moong)(whole)"], ["green gram"]),
    "blackgram": (["black gram(urd beans)(whole)"], ["black gram"]),
    "lentil": (["lentil(masur)(whole)"], ["lentil"]),
    "pomegranate": (["pomegranate"], ["pomegranate"]),
    "banana": (["banana"], ["banana"]),
    "mango": (["mango", "mango(raw-ripe)"], ["mango"]),
    "grapes": (["grapes"], ["grapes"]),
    "watermelon": (["water melon"], ["water melon"]),
    "muskmelon": (["karbuja(musk melon)"], []),
    "apple": (["apple"], ["apple"]),
    "orange": (["orange"], ["orange"]),
    "papaya": (["papaya"], []),
    # Coconut history mixes per-nut and per-quintal quotes (values from 14 to 1,962), so it is not used.
    "coconut": (["coconut"], []),
    "cotton": (["cotton"], ["cotton"]),
    "jute": (["jute"], []),
    "coffee": (["coffee"], []),
}
HOME_STATE = "karnataka"
MIN_STATE_RECORDS = 20
RECENT_WINDOW_DAYS = 30


# ------------------------------------------------------------------ history
def load_history(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    df["commodity"] = df["Commodity"].astype(str).str.strip().str.lower()
    df["date"] = pd.to_datetime(df["date"], format="%Y-%m")
    return df[df["modal_price"] > 0]


def monthly_series(hist: pd.DataFrame, names: list[str]) -> pd.Series:
    """Median modal price across all APMCs for each calendar month."""
    sub = hist[hist["commodity"].isin(names)]
    if sub.empty:
        return pd.Series(dtype=float)
    s = sub.groupby("date")["modal_price"].median().sort_index()
    return s.asfreq("MS")  # keep gaps as NaN


def seasonal_index(series: pd.Series) -> pd.Series | None:
    """Multiplicative month-of-year index: fit a log-linear trend, average the
    residual of each calendar month, exponentiate, normalise to mean 1.
    Returns None unless all 12 months have at least one observation."""
    s = series.dropna()
    if len(s) < 12:
        return None
    t = np.array([(d.year - s.index[0].year) * 12 + d.month - s.index[0].month for d in s.index], float)
    y = np.log(s.values)
    slope, intercept = np.polyfit(t, y, 1)
    resid = pd.Series(y - (intercept + slope * t), index=s.index)
    by_month = resid.groupby(resid.index.month).mean()
    if len(by_month) < 12:
        return None
    idx = np.exp(by_month)
    return idx / idx.mean()


def backtest(series: pd.Series, horizon: int = 6) -> dict | None:
    """Rolling-origin test: fit the index on data up to each origin, forecast
    the next `horizon` months as price_origin * S(target)/S(origin), compare
    with the naive 'price stays the same' forecast."""
    s = series.dropna()
    errs_seasonal, errs_naive = [], []
    for k in range(15, len(s) - 1):
        train, origin_date = s.iloc[: k + 1], s.index[k]
        idx = seasonal_index(train)
        if idx is None:
            continue
        p0 = train.iloc[-1]
        for h in range(1, horizon + 1):
            target = origin_date + pd.DateOffset(months=h)
            if target not in s.index or np.isnan(s[target]):
                continue
            actual = s[target]
            pred = p0 * idx[target.month] / idx[origin_date.month]
            errs_seasonal.append(abs(pred - actual) / actual)
            errs_naive.append(abs(p0 - actual) / actual)
    if not errs_seasonal:
        return None
    return {"n_forecasts": len(errs_seasonal), "mape_seasonal": float(np.mean(errs_seasonal)),
            "mape_naive": float(np.mean(errs_naive))}


# ------------------------------------------------------------------ recent
def load_recent(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path, low_memory=False)
    df["commodity"] = df["commodity"].astype(str).str.strip().str.lower()
    df["state_l"] = df["state"].astype(str).str.strip().str.lower()
    df["date"] = pd.to_datetime(df["arrival_date"], format="%d/%m/%Y", errors="coerce")
    return df[(df["modal_price"] > 0) & df["date"].notna()]


def current_price(recent: pd.DataFrame, names: list[str]) -> dict | None:
    sub = recent[recent["commodity"].isin(names)]
    if sub.empty:
        return None
    sub = sub[sub["date"] > sub["date"].max() - pd.Timedelta(days=RECENT_WINDOW_DAYS)]
    ka = sub[sub["state_l"] == HOME_STATE]
    use, scope = (ka, "Karnataka") if len(ka) >= MIN_STATE_RECORDS else (sub, "India")
    p = use["modal_price"]
    return {"scope": scope, "median_price": round(float(p.median()), 1), "p25": round(float(p.quantile(0.25)), 1),
            "p75": round(float(p.quantile(0.75)), 1), "n_records": int(len(use)),
            "first_date": use["date"].min().date().isoformat(), "last_date": use["date"].max().date().isoformat()}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--history", required=True, type=Path)
    ap.add_argument("--recent", required=True, type=Path)
    ap.add_argument("--out", default=Path("datasets/market"), type=Path)
    a = ap.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)

    hist, recent = load_history(a.history), load_recent(a.recent)
    season_rows, price_rows, bt = [], [], {}
    for crop, (recent_names, hist_names) in CROP_MAP.items():
        series = monthly_series(hist, hist_names)
        idx = seasonal_index(series) if len(series) else None
        if idx is not None:
            counts = series.dropna().groupby(series.dropna().index.month).size()
            season_rows += [{"crop": crop, "month": m, "index": round(float(idx[m]), 4), "n_months": int(counts.get(m, 0))}
                            for m in range(1, 13)]
            r = backtest(series)
            if r:
                bt[crop] = {k: (round(v, 4) if isinstance(v, float) else v) for k, v in r.items()}
        cp = current_price(recent, recent_names)
        if cp:
            price_rows.append({"crop": crop, **cp})

    pd.DataFrame(season_rows).to_csv(a.out / "seasonal_index.csv", index=False)
    pd.DataFrame(price_rows).to_csv(a.out / "current_prices.csv", index=False)
    tot = sum(v["n_forecasts"] for v in bt.values())
    summary = {
        "method": "seasonal-index forecast anchored on the latest price vs naive (no-change) forecast; rolling origins, horizons 1-6 months",
        "pooled_mape_seasonal": round(sum(v["mape_seasonal"] * v["n_forecasts"] for v in bt.values()) / tot, 4),
        "pooled_mape_naive": round(sum(v["mape_naive"] * v["n_forecasts"] for v in bt.values()) / tot, 4),
        # Validation gate: the app only shows a seasonal forecast for crops where it
        # beat the naive forecast out-of-sample. Other crops get current prices only.
        "crops_where_seasonal_beats_naive": sorted(c for c, v in bt.items() if v["mape_seasonal"] < v["mape_naive"]),
        "per_crop": bt,
    }
    (a.out / "backtest.json").write_text(json.dumps(summary, indent=2))
    print(f"seasonal index: {len(season_rows) // 12} crops | current prices: {len(price_rows)} crops")
    print(f"backtest MAPE seasonal={summary['pooled_mape_seasonal']:.3f} naive={summary['pooled_mape_naive']:.3f} "
          f"({len(summary['crops_where_seasonal_beats_naive'])}/{len(bt)} crops better)")


if __name__ == "__main__":
    main()
