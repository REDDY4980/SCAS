"""
Weather provider clients.

AIB v1.0 Vol 8.3: "Primary: Open-Meteo. Fallback: OpenWeatherMap/WeatherAPI."
Vol 8.14: "Never call external weather APIs directly from Flutter. Route
through FastAPI."

Both clients return a common `RawWeatherResponse` so the normalizer
(Vol 8.6) doesn't need to know which provider answered.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

import httpx

from app.core.config import get_settings

_REQUEST_TIMEOUT_SECONDS = 2.0  # Vol 8.12: weather retrieval <=2s target


class WeatherProviderError(Exception):
    """Raised when a provider is unreachable, times out, or returns an error."""


@dataclass
class RawWeatherResponse:
    provider: str
    payload: dict[str, Any]


class WeatherProviderClient(ABC):
    name: str

    @abstractmethod
    def fetch(self, latitude: float, longitude: float) -> RawWeatherResponse:
        """Fetches current + today's weather for a coordinate. Raises
        WeatherProviderError on any failure (network, timeout, HTTP error,
        malformed response)."""


class OpenMeteoClient(WeatherProviderClient):
    """Primary provider (Vol 8.3) — free, no API key required."""

    name = "open-meteo"

    def fetch(self, latitude: float, longitude: float) -> RawWeatherResponse:
        settings = get_settings()
        url = f"{settings.open_meteo_base_url}/forecast"
        params = {
            "latitude": latitude,
            "longitude": longitude,
            "current": "temperature_2m,relative_humidity_2m,wind_speed_10m,cloud_cover,precipitation",
            "daily": "rain_sum",
            "timezone": "auto",
            "forecast_days": 1,
        }
        try:
            response = httpx.get(url, params=params, timeout=_REQUEST_TIMEOUT_SECONDS)
            response.raise_for_status()
            data = response.json()
        except httpx.TimeoutException as exc:
            raise WeatherProviderError(f"Open-Meteo request timed out: {exc}") from exc
        except httpx.HTTPError as exc:
            raise WeatherProviderError(f"Open-Meteo request failed: {exc}") from exc

        if data.get("error"):
            raise WeatherProviderError(f"Open-Meteo returned an error: {data.get('reason')}")

        return RawWeatherResponse(provider=self.name, payload=data)


class OpenWeatherMapClient(WeatherProviderClient):
    """Fallback provider (Vol 8.3) — requires an API key (Vol 16.5 env var)."""

    name = "openweathermap"
    _BASE_URL = "https://api.openweathermap.org/data/2.5/weather"

    def fetch(self, latitude: float, longitude: float) -> RawWeatherResponse:
        settings = get_settings()
        if not settings.openweathermap_api_key:
            raise WeatherProviderError(
                "OpenWeatherMap fallback is not configured (OPENWEATHERMAP_API_KEY unset)."
            )
        params = {
            "lat": latitude,
            "lon": longitude,
            "appid": settings.openweathermap_api_key,
            "units": "metric",
        }
        try:
            response = httpx.get(self._BASE_URL, params=params, timeout=_REQUEST_TIMEOUT_SECONDS)
            response.raise_for_status()
            data = response.json()
        except httpx.TimeoutException as exc:
            raise WeatherProviderError(f"OpenWeatherMap request timed out: {exc}") from exc
        except httpx.HTTPError as exc:
            raise WeatherProviderError(f"OpenWeatherMap request failed: {exc}") from exc

        return RawWeatherResponse(provider=self.name, payload=data)


def fetch_with_retry(client: WeatherProviderClient, latitude: float, longitude: float) -> RawWeatherResponse:
    """Vol 8.11: 'Retry once on timeout.'"""
    try:
        return client.fetch(latitude, longitude)
    except WeatherProviderError:
        return client.fetch(latitude, longitude)  # single retry; second failure propagates
