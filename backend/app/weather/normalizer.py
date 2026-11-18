"""
Weather normalization.

AIB v1.0 Vol 8.6: "Weather Service retrieves, validates, normalizes,
caches and stores climate data and returns a standardized DTO."
Vol 8.5: Climate Features = Temperature, Humidity, Rainfall, Wind Speed,
Cloud Cover, Season, Timestamp.
Vol 8.14: "Normalize all values before persistence."

Only Open-Meteo is normalized here with full confidence, since it's the
only provider actually exercised (Vol 8.3 primary, no key required).
The OpenWeatherMap normalizer is implemented against its documented
schema for when a real API key is configured, but has not been run
against a live response in this environment.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from app.weather.client import RawWeatherResponse

_MONTH_TO_SEASON = {
    # Indian Meteorological Department convention, since SCAS targets
    # Indian farmers (Vol 1.1) and the fertilizer/agronomic knowledge
    # bases are India-specific (Vol 11, Requirement 2/3 source registers).
    12: "winter", 1: "winter", 2: "winter",
    3: "summer", 4: "summer", 5: "summer",
    6: "monsoon", 7: "monsoon", 8: "monsoon", 9: "monsoon",
    10: "post_monsoon", 11: "post_monsoon",
}


# A 30-day total needs most of its days; otherwise fall back (see below).
_MIN_DAYS_FOR_WINDOW = 25


@dataclass
class NormalizedWeather:
    temperature: float | None
    humidity: float | None
    rainfall: float | None
    wind_speed: float | None
    cloud_cover: float | None
    season: str
    captured_at: datetime
    provider: str


def season_for_month(month: int) -> str:
    return _MONTH_TO_SEASON[month]


def normalize_open_meteo(response: RawWeatherResponse) -> NormalizedWeather:
    payload = response.payload
    current = payload.get("current", {})
    daily = payload.get("daily", {})

    captured_at = datetime.now(timezone.utc)
    time_str = current.get("time")
    if time_str:
        try:
            captured_at = datetime.fromisoformat(time_str).replace(tzinfo=timezone.utc)
        except ValueError:
            pass  # keep the now() fallback; malformed timestamp is not fatal

    # Rainfall for the crop model: total precipitation over the last 30
    # complete days (`past_days=30`, today excluded). The model was trained
    # on rainfall of 20-298 mm (datasets/crop_recommendation), i.e. a
    # monthly-scale amount; today's rain alone is 0 mm on most days, which
    # made every farm look equally dry (measured live: four farms with
    # 25-256 mm over 30 days all sent 0.0). Older/other payloads without
    # the 30-day series keep the previous behaviour (today's rain_sum,
    # then the instant precipitation reading).
    precip_series = daily.get("precipitation_sum") or []
    past_days = [v for v in precip_series[:-1] if v is not None]
    rain_sum_list = daily.get("rain_sum") or []
    if len(precip_series) > 1 and len(past_days) >= _MIN_DAYS_FOR_WINDOW:
        rainfall = round(sum(float(v) for v in past_days), 1)
    elif rain_sum_list:
        rainfall = float(rain_sum_list[-1] if len(rain_sum_list) > 1 else rain_sum_list[0])
    else:
        rainfall = current.get("precipitation")

    return NormalizedWeather(
        temperature=_as_float(current.get("temperature_2m")),
        humidity=_as_float(current.get("relative_humidity_2m")),
        rainfall=_as_float(rainfall),
        wind_speed=_as_float(current.get("wind_speed_10m")),
        cloud_cover=_as_float(current.get("cloud_cover")),
        season=season_for_month(captured_at.month),
        captured_at=captured_at,
        provider=response.provider,
    )


def normalize_openweathermap(response: RawWeatherResponse) -> NormalizedWeather:
    payload = response.payload
    main = payload.get("main", {})
    wind = payload.get("wind", {})
    clouds = payload.get("clouds", {})
    rain = payload.get("rain", {})

    captured_at = datetime.now(timezone.utc)
    dt_epoch = payload.get("dt")
    if dt_epoch:
        captured_at = datetime.fromtimestamp(dt_epoch, tz=timezone.utc)

    # OpenWeatherMap wind speed is m/s by default with units=metric;
    # Open-Meteo's default is km/h. Normalize to km/h for consistency
    # across providers, since both feed the same weather_snapshots column.
    wind_speed_ms = wind.get("speed")
    wind_speed_kmh = wind_speed_ms * 3.6 if wind_speed_ms is not None else None

    return NormalizedWeather(
        temperature=_as_float(main.get("temp")),
        humidity=_as_float(main.get("humidity")),
        rainfall=_as_float(rain.get("1h")) if rain else 0.0,
        wind_speed=_as_float(wind_speed_kmh),
        cloud_cover=_as_float(clouds.get("all")),
        season=season_for_month(captured_at.month),
        captured_at=captured_at,
        provider=response.provider,
    )


def normalize(response: RawWeatherResponse) -> NormalizedWeather:
    if response.provider == "open-meteo":
        return normalize_open_meteo(response)
    if response.provider == "openweathermap":
        return normalize_openweathermap(response)
    raise ValueError(f"No normalizer registered for provider: {response.provider}")


def _as_float(value) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
