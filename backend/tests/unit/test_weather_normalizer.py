"""
Normalizer tests — the fixture payload shape is taken directly from
Open-Meteo's documented JSON Return Object (open-meteo.com/en/docs),
with plausible values for a Karnataka coordinate substituted in.
"""

from datetime import datetime

import pytest

from app.weather.client import RawWeatherResponse
from app.weather.normalizer import normalize_open_meteo, normalize_openweathermap, season_for_month

OPEN_METEO_SAMPLE_PAYLOAD = {
    "latitude": 16.17,
    "longitude": 75.87,
    "elevation": 561.0,
    "generationtime_ms": 0.12,
    "utc_offset_seconds": 19800,
    "timezone": "Asia/Kolkata",
    "timezone_abbreviation": "IST",
    "current": {
        "time": "2026-08-09T14:00",
        "interval": 900,
        "temperature_2m": 28.4,
        "relative_humidity_2m": 68.0,
        "wind_speed_10m": 11.2,
        "cloud_cover": 55.0,
        "precipitation": 0.2,
    },
    "daily": {
        "time": ["2026-08-09"],
        "rain_sum": [4.8],
    },
}


def test_normalize_open_meteo_maps_all_fields():
    response = RawWeatherResponse(provider="open-meteo", payload=OPEN_METEO_SAMPLE_PAYLOAD)
    result = normalize_open_meteo(response)

    assert result.temperature == pytest.approx(28.4)
    assert result.humidity == pytest.approx(68.0)
    assert result.wind_speed == pytest.approx(11.2)
    assert result.cloud_cover == pytest.approx(55.0)
    assert result.provider == "open-meteo"


def test_normalize_open_meteo_prefers_daily_rain_sum_over_instant_precipitation():
    # daily.rain_sum (today's accumulated rainfall) is a more meaningful
    # agronomic signal than the instant 15-minute precipitation reading.
    response = RawWeatherResponse(provider="open-meteo", payload=OPEN_METEO_SAMPLE_PAYLOAD)
    result = normalize_open_meteo(response)
    assert result.rainfall == pytest.approx(4.8)


def test_normalize_open_meteo_falls_back_to_instant_precipitation_when_no_daily_data():
    payload = dict(OPEN_METEO_SAMPLE_PAYLOAD)
    payload["daily"] = {}
    response = RawWeatherResponse(provider="open-meteo", payload=payload)
    result = normalize_open_meteo(response)
    assert result.rainfall == pytest.approx(0.2)


def test_normalize_open_meteo_parses_local_time_for_season():
    response = RawWeatherResponse(provider="open-meteo", payload=OPEN_METEO_SAMPLE_PAYLOAD)
    result = normalize_open_meteo(response)
    assert isinstance(result.captured_at, datetime)
    assert result.season == "monsoon"  # August -> monsoon (Vol 8 season derivation)


def test_normalize_open_meteo_missing_current_block_does_not_crash():
    response = RawWeatherResponse(provider="open-meteo", payload={})
    result = normalize_open_meteo(response)
    assert result.temperature is None
    assert result.humidity is None


@pytest.mark.parametrize(
    "month,expected_season",
    [(12, "winter"), (1, "winter"), (2, "winter"), (3, "summer"), (5, "summer"),
     (6, "monsoon"), (9, "monsoon"), (10, "post_monsoon"), (11, "post_monsoon")],
)
def test_season_for_month(month, expected_season):
    assert season_for_month(month) == expected_season


def test_normalize_openweathermap_converts_wind_speed_ms_to_kmh():
    payload = {
        "main": {"temp": 27.5, "humidity": 70},
        "wind": {"speed": 3.0},  # m/s
        "clouds": {"all": 40},
        "rain": {"1h": 1.2},
        "dt": 1754745600,  # some fixed epoch
    }
    response = RawWeatherResponse(provider="openweathermap", payload=payload)
    result = normalize_openweathermap(response)
    assert result.wind_speed == pytest.approx(3.0 * 3.6)
    assert result.temperature == pytest.approx(27.5)
    assert result.rainfall == pytest.approx(1.2)
