"""Unit tests for the market outlook engine (Objective 3)."""

import json

import pytest

from app.market.forecaster import HOLD_THRESHOLD_PCT, MarketForecaster, UnknownCropError


@pytest.fixture
def toy_dir(tmp_path):
    (tmp_path / "current_prices.csv").write_text(
        "crop,scope,median_price,p25,p75,n_records,first_date,last_date\n"
        "maize,Karnataka,2000,1900,2100,50,2026-08-27,2026-09-24\n"
        "watermelon,India,1000,900,1100,80,2026-08-27,2026-09-24\n"
        "rice,Karnataka,3000,2800,3200,60,2026-08-27,2026-09-24\n"
        "jute,India,12000,11000,13000,5,2026-08-30,2026-09-24\n")
    rows = ["crop,month,index,n_months"]
    for m in range(1, 13):
        rows.append(f"maize,{m},{1.2 if m == 12 else 1.0},2")   # +20% in December
        rows.append(f"watermelon,{m},{1.3 if m == 11 else 1.0},2")
        rows.append(f"rice,{m},1.0,2")
    (tmp_path / "seasonal_index.csv").write_text("\n".join(rows) + "\n")
    (tmp_path / "backtest.json").write_text(json.dumps({
        "crops_where_seasonal_beats_naive": ["maize", "watermelon"],
        "per_crop": {"maize": {"n_forecasts": 10, "mape_seasonal": 0.08, "mape_naive": 0.10},
                     "rice": {"n_forecasts": 10, "mape_seasonal": 0.07, "mape_naive": 0.05}}}))
    return tmp_path


def test_forecast_follows_seasonal_index(toy_dir):
    o = MarketForecaster(toy_dir).outlook("maize", months=6)
    assert [p.month for p in o.forecast] == ["2026-10", "2026-11", "2026-12", "2027-01", "2027-02", "2027-03"]
    dec = o.forecast[2]
    assert dec.expected_price == pytest.approx(2400) and dec.change_pct == pytest.approx(20.0)


def test_storable_crop_with_big_gain_is_hold(toy_dir):
    o = MarketForecaster(toy_dir).outlook("maize")
    assert o.action == "hold" and o.best_month == "Dec 2026" and o.expected_gain_pct == pytest.approx(20.0)


def test_perishable_crop_gets_harvest_timing_not_storage(toy_dir):
    o = MarketForecaster(toy_dir).outlook("watermelon")
    assert o.perishable and o.action == "time_harvest" and o.best_month == "Nov 2026"


def test_unvalidated_crop_shows_no_forecast(toy_dir):
    o = MarketForecaster(toy_dir).outlook("rice")
    assert not o.seasonal_forecast_available and o.forecast == [] and o.action == "sell_when_ready"
    assert any("did not beat" in c for c in o.caveats)


def test_small_gain_means_sell_now(toy_dir):
    o = MarketForecaster(toy_dir).outlook("maize", months=2)   # December not in horizon
    assert o.action == "sell_now" and o.expected_gain_pct < HOLD_THRESHOLD_PCT


def test_low_record_count_is_flagged(toy_dir):
    o = MarketForecaster(toy_dir).outlook("jute")
    assert any("Only 5 price records" in c for c in o.caveats)
    assert any("all-India" in c for c in o.caveats)


def test_unknown_crop_raises(toy_dir):
    with pytest.raises(UnknownCropError):
        MarketForecaster(toy_dir).outlook("mothbeans")


def test_real_artefacts_cover_model_crops():
    f = MarketForecaster()  # datasets/market in the repo
    crops = {c["crop"]: c for c in f.crops()}
    assert sum(c["has_current_price"] for c in crops.values()) >= 20
    assert {c for c, v in crops.items() if v["seasonal_forecast_available"]} <= set(f.validated)
