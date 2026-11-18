"""
Rainfall fed to the crop model = total of the last 30 complete days.

The model was trained on rainfall of 20-298 mm (monthly scale). Live
Open-Meteo data for four farms showed today's rain = 0.0 mm everywhere
while their 30-day totals were 25-256 mm.
"""

import httpx
import pytest

from app.weather.client import RAINFALL_WINDOW_DAYS, OpenMeteoClient, RawWeatherResponse
from app.weather.normalizer import normalize_open_meteo


def _payload(precip_days, rain_today=0.0):
    return {
        "current": {"time": "2026-11-18T12:00", "temperature_2m": 30.4, "relative_humidity_2m": 51,
                    "wind_speed_10m": 9.0, "cloud_cover": 20, "precipitation": 0.0},
        "daily": {"time": [f"d{i}" for i in range(len(precip_days))],
                  "precipitation_sum": precip_days,
                  "rain_sum": [0.0] * (len(precip_days) - 1) + [rain_today]},
    }


def test_rainfall_is_30_day_total_excluding_today():
    days = [5.0] * 30 + [99.0]  # 30 complete days + today (partial/forecast)
    result = normalize_open_meteo(RawWeatherResponse("open-meteo", _payload(days)))
    assert result.rainfall == pytest.approx(150.0)


def test_dry_today_but_wet_month_is_not_reported_as_zero():
    days = [0.0] * 20 + [25.6] * 10 + [0.0]
    result = normalize_open_meteo(RawWeatherResponse("open-meteo", _payload(days)))
    assert result.rainfall == pytest.approx(256.0)


def test_missing_days_in_window_ignored_but_too_few_falls_back_to_today():
    days = [2.0] * 26 + [None] * 4 + [0.0]
    assert normalize_open_meteo(RawWeatherResponse("open-meteo", _payload(days))).rainfall == pytest.approx(52.0)
    sparse = [2.0] * 10 + [None] * 20 + [0.0]
    assert normalize_open_meteo(RawWeatherResponse("open-meteo", _payload(sparse, rain_today=1.5))).rainfall == pytest.approx(1.5)


def test_client_requests_the_30_day_series(monkeypatch):
    seen = {}

    class R:
        def raise_for_status(self):
            pass

        def json(self):
            return {"current": {}, "daily": {}}

    def fake_get(url, params=None, **kwargs):
        seen.update(params)
        seen["timeout"] = kwargs.get("timeout")
        return R()

    monkeypatch.setattr(httpx, "get", fake_get)
    OpenMeteoClient().fetch(16.18, 75.70)
    assert seen["past_days"] == RAINFALL_WINDOW_DAYS == 30
    assert "precipitation_sum" in seen["daily"]
    assert seen["timeout"] >= 5  # 0.1 CPU host: 2 s was too tight for a fresh TLS connection
