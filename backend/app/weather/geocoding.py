"""
Geocoding client — resolves approximate farm coordinates from a
district/state name instead of requiring a human to type latitude and
longitude. Uses Open-Meteo's free Geocoding API, the same provider
already used for weather (app/weather/client.py) — no new API key.

This intentionally mirrors OpenMeteoClient's error-handling shape:
- GeocodingError means the provider itself failed (network, timeout,
  malformed response) — a real failure the caller should log.
- A `None` return means the provider answered fine but found no match
  for the given name — an expected, common-enough outcome (village/
  district spelling variance) that callers must treat as "leave
  coordinates blank," not as an error.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass

import httpx

from app.core.config import get_settings

logger = logging.getLogger("scas.weather.geocoding")

_REQUEST_TIMEOUT_SECONDS = 3.0

# Open-Meteo's free geocoding tier doesn't return 429 when a client
# exceeds its request quota — it returns a normal 200 whose body omits
# the "results" key entirely (as opposed to a genuine no-match, which
# includes "results": []). That's the one distinguishable signature of
# throttling, so it gets a single short-backoff retry instead of being
# treated as "this place doesn't exist."
_THROTTLE_RETRY_DELAY_SECONDS = 1.5

# Official Indian revenue-district names routinely carry these suffixes
# (Bengaluru Urban/Rural, North 24 Parganas district records use similar
# patterns) — they identify an administrative division, not a place a
# general-purpose gazetteer like Open-Meteo's geocoder indexes by name.
# The bare name usually resolves fine, so it's a cheap, high-value retry
# rather than leaving the farm with no coordinates over a suffix.
_STRIPPABLE_SUFFIXES = (" urban", " rural", " (urban)", " (rural)")


class GeocodingError(Exception):
    """Raised when the geocoding provider is unreachable, times out, or errors."""


@dataclass
class GeocodedLocation:
    latitude: float
    longitude: float
    resolved_name: str
    is_approximate: bool = False


def _fetch(name: str, *, country_code: str) -> dict:
    settings = get_settings()
    params = {
        "name": name,
        "count": 8,
        "language": "en",
        "format": "json",
        "country": country_code,
    }
    try:
        response = httpx.get(
            settings.geocoding_base_url, params=params, timeout=_REQUEST_TIMEOUT_SECONDS
        )
        response.raise_for_status()
        return response.json()
    except httpx.TimeoutException as exc:
        raise GeocodingError(f"Geocoding request timed out: {exc}") from exc
    except httpx.HTTPError as exc:
        raise GeocodingError(f"Geocoding request failed: {exc}") from exc


def _query(name: str, *, state: str | None, country_code: str) -> GeocodedLocation | None:
    data = _fetch(name, country_code=country_code)
    if "results" not in data:
        logger.info("Geocoding response for %r omitted 'results' (likely throttled) — retrying once", name)
        time.sleep(_THROTTLE_RETRY_DELAY_SECONDS)
        data = _fetch(name, country_code=country_code)

    results = data.get("results") or []
    if not results:
        return None

    top = results[0]
    if state:
        state_normalized = state.strip().casefold()
        for candidate in results:
            admin1 = (candidate.get("admin1") or "").strip().casefold()
            if admin1 == state_normalized:
                top = candidate
                break

    try:
        return GeocodedLocation(
            latitude=float(top["latitude"]),
            longitude=float(top["longitude"]),
            resolved_name=top.get("name", name),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise GeocodingError(f"Geocoding response was malformed: {exc}") from exc


def geocode_place(name: str, *, state: str | None = None, country_code: str = "IN") -> GeocodedLocation | None:
    """
    Resolves approximate coordinates for a place name (typically a farm's
    district). Requests a handful of candidates rather than just the top
    one: district names are not unique within a country (e.g. more than
    one Indian state has a "Bijapur"/"Balrampur"), so when `state` is
    given we prefer whichever candidate's `admin1` (state/province)
    matches it, falling back to the top-ranked candidate otherwise.

    If the exact name has no match, retries once with a trailing
    "Urban"/"Rural" administrative suffix stripped (see
    _STRIPPABLE_SUFFIXES) before giving up.

    India has redrawn district boundaries repeatedly in recent years
    (e.g. Sri Sathya Sai split from Anantapur in 2022) — a district that
    a farmer correctly names may simply not exist yet in Open-Meteo's
    gazetteer, and spelling of transliterated names varies (Satya vs.
    Sathya). Rather than leave the farm with no location at all (no
    weather, ever, until a farmer happens to re-save with different
    text), a district-level miss falls back to geocoding the state
    itself: coarser than the farm's real position, but still real and
    in the right region, and far better than nothing.
    """
    result = _query(name, state=state, country_code=country_code)
    if result is not None:
        return result

    lowered = name.strip().casefold()
    for suffix in _STRIPPABLE_SUFFIXES:
        if lowered.endswith(suffix):
            stripped = name.strip()[: -len(suffix)].strip()
            if stripped:
                result = _query(stripped, state=state, country_code=country_code)
                if result is not None:
                    return result
            break

    if state:
        state_result = _query(state, state=None, country_code=country_code)
        if state_result is not None:
            state_result.is_approximate = True
            return state_result

    return None
