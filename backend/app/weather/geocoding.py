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
import re
import time
import unicodedata
from dataclasses import dataclass

import httpx

from app.core.config import get_settings

logger = logging.getLogger("scas.weather.geocoding")

# Generous on purpose: on Render's free tier (0.1 CPU) building the TLS
# context and handshake alone can take a large part of a second, and the
# farmer's farm save must not fail on a slow-but-working network.
_REQUEST_TIMEOUT_SECONDS = 6.0

# Open-Meteo's free geocoding tier doesn't return 429 when a client
# exceeds its request quota — it returns a normal 200 whose body omits
# the "results" key entirely (as opposed to a genuine no-match, which
# includes "results": []). That's the one distinguishable signature of
# throttling, so it gets a single short-backoff retry instead of being
# treated as "this place doesn't exist."
#
# Measured against the live API (docs/OCR_MEMORY_REPORT.md, §Weather &
# location): an ordinary no-match ALSO comes back without "results", so the
# retry is kept but its delay is short — every miss pays it.
_THROTTLE_RETRY_DELAY_SECONDS = 0.5

# Official Indian revenue-district names routinely carry these suffixes
# (Bengaluru Urban/Rural, North 24 Parganas district records use similar
# patterns) — they identify an administrative division, not a place a
# general-purpose gazetteer like Open-Meteo's geocoder indexes by name.
# The bare name usually resolves fine, so it's a cheap, high-value retry
# rather than leaving the farm with no coordinates over a suffix.
_STRIPPABLE_SUFFIXES = (" urban", " rural", " (urban)", " (rural)")

# Open-Meteo indexes towns/cities, not Indian state names ("Karnataka",
# "West Bengal" return nothing — verified live), so the state-level
# fallback uses each state's/UT's capital, resolved once against the live
# gazetteer and stored here. Coarse, but a real place in the right state.
_STATE_CAPITALS: dict[str, tuple[str, float, float]] = {
    "andhra pradesh": ("Amaravati", 16.514, 80.516),
    "arunachal pradesh": ("Itanagar", 27.0869, 93.6099),
    "assam": ("Dispur", 26.1356, 91.8007),
    "bihar": ("Patna", 25.5941, 85.1356),
    "chhattisgarh": ("Raipur", 21.2333, 81.6333),
    "goa": ("Panaji", 15.4957, 73.8262),
    "gujarat": ("Gandhinagar", 23.2167, 72.6833),
    "haryana": ("Chandigarh", 30.7363, 76.7884),
    "himachal pradesh": ("Shimla", 31.1044, 77.1666),
    "jharkhand": ("Ranchi", 23.3432, 85.3094),
    "karnataka": ("Bengaluru", 12.9719, 77.5937),
    "kerala": ("Thiruvananthapuram", 8.4855, 76.9492),
    "madhya pradesh": ("Bhopal", 23.2547, 77.4029),
    "maharashtra": ("Mumbai", 19.0728, 72.8826),
    "manipur": ("Imphal", 24.8081, 93.9442),
    "meghalaya": ("Shillong", 25.5689, 91.8831),
    "mizoram": ("Aizawl", 23.7289, 92.7179),
    "nagaland": ("Kohima", 25.6747, 94.111),
    "odisha": ("Bhubaneswar", 20.2724, 85.8338),
    "punjab": ("Chandigarh", 30.7363, 76.7884),
    "rajasthan": ("Jaipur", 26.9196, 75.7878),
    "sikkim": ("Gangtok", 27.3257, 88.6122),
    "tamil nadu": ("Chennai", 13.0878, 80.2785),
    "telangana": ("Hyderabad", 17.384, 78.4564),
    "tripura": ("Agartala", 23.8361, 91.2794),
    "uttar pradesh": ("Lucknow", 26.8393, 80.9231),
    "uttarakhand": ("Dehradun", 30.3244, 78.0339),
    "west bengal": ("Kolkata", 22.5626, 88.363),
    "andaman and nicobar islands": ("Port Blair", 11.6661, 92.7464),
    "chandigarh": ("Chandigarh", 30.7363, 76.7884),
    "dadra and nagar haveli and daman and diu": ("Daman", 20.4143, 72.8324),
    "delhi": ("New Delhi", 28.6214, 77.2148),
    "jammu and kashmir": ("Srinagar", 34.0857, 74.8055),
    "ladakh": ("Leh", 34.165, 77.584),
    "lakshadweep": ("Kavaratti", 10.5669, 72.642),
    "puducherry": ("Puducherry", 11.9338, 79.8298),
}

# Spellings farmers (and older records) use -> canonical state key, plus
# the gazetteer's own admin1 spellings that differ from the canonical one.
_STATE_ALIASES: dict[str, str] = {
    "orissa": "odisha",
    "pondicherry": "puducherry",
    "uttaranchal": "uttarakhand",
    "tamilnadu": "tamil nadu",
    "telengana": "telangana",
    "chattisgarh": "chhattisgarh",
    "chhatisgarh": "chhattisgarh",
    "new delhi": "delhi",
    "nct of delhi": "delhi",
    "national capital territory of delhi": "delhi",
    "andaman and nicobar": "andaman and nicobar islands",
    "dadra and nagar haveli": "dadra and nagar haveli and daman and diu",
    "daman and diu": "dadra and nagar haveli and daman and diu",
}

# District names as farmers/official records write them -> the name the
# gazetteer indexes (current official city names, or the district
# headquarters for districts with no town of that name). Every entry was
# verified against the live API to resolve inside the right state.
_DISTRICT_ALIASES: dict[str, str] = {
    "gulbarga": "Kalaburagi",
    "belgaum": "Belagavi",
    "bellary": "Ballari",
    "shimoga": "Shivamogga",
    "tumkur": "Tumakuru",
    "mysore": "Mysuru",
    "chikmagalur": "Chikkamagaluru",
    "bangalore": "Bengaluru",
    "bagalkote": "Bagalkot",
    "vijayapura": "Bijapur",
    "mangalore": "Mangaluru",
    "dakshina kannada": "Mangaluru",
    "uttara kannada": "Karwar",
    "kodagu": "Madikeri",
    "vijayanagara": "Hosapete",
    "hospet": "Hosapete",
    "east godavari": "Kakinada",
    "west godavari": "Eluru",
    "krishna": "Machilipatnam",
    "prakasam": "Ongole",
    "sri potti sriramulu nellore": "Nellore",
    "spsr nellore": "Nellore",
    "ysr kadapa": "Kadapa",
    "ysr": "Kadapa",
    "north 24 parganas": "Barasat",
    "south 24 parganas": "Alipore",
    "purba bardhaman": "Bardhaman",
    "paschim bardhaman": "Asansol",
    "paschim medinipur": "Midnapore",
    "purba medinipur": "Tamluk",
    "dakshin dinajpur": "Balurghat",
    "uttar dinajpur": "Raiganj",
    "gurgaon": "Gurugram",
    "allahabad": "Prayagraj",
    "faizabad": "Ayodhya",
    "chhatrapati sambhajinagar": "Aurangabad",
    "dharashiv": "Osmanabad",
    "ahmednagar": "Ahilyanagar",
    "ranga reddy": "Hyderabad",
}


def _norm(text: str) -> str:
    """Case/diacritic/punctuation-insensitive form ("Bārāsat" == "barasat")."""
    decomposed = unicodedata.normalize("NFKD", text or "")
    ascii_only = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    ascii_only = ascii_only.casefold().replace("&", " and ")
    return re.sub(r"[^a-z0-9]+", " ", ascii_only).strip()


def _canonical_state(state: str | None) -> str | None:
    """Canonical Indian state/UT key, or None if not recognised."""
    if not state:
        return None
    key = _norm(state)
    key = _STATE_ALIASES.get(key, key)
    return key if key in _STATE_CAPITALS else None


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
        # NB: Open-Meteo's parameter is `countryCode`; an unknown `country`
        # parameter is silently ignored and the search becomes worldwide
        # (verified live: "Daman" -> Damanhur, Egypt; "Leh" -> Le Havre).
        "countryCode": country_code,
    }
    # One retry on connection-level failures (TLS handshake/connect
    # timeouts, resets): each call opens a fresh connection, and a single
    # transient failure must not leave a farm without a location.
    for attempt in (1, 2):
        try:
            response = httpx.get(
                settings.geocoding_base_url, params=params, timeout=_REQUEST_TIMEOUT_SECONDS
            )
            response.raise_for_status()
            return response.json()
        except httpx.TransportError as exc:
            if attempt == 1:
                logger.info("Geocoding transport error (%s) — retrying once", type(exc).__name__)
                continue
            if isinstance(exc, httpx.TimeoutException):
                raise GeocodingError(f"Geocoding request timed out: {exc}") from exc
            raise GeocodingError(f"Geocoding request failed: {exc}") from exc
        except httpx.HTTPError as exc:
            raise GeocodingError(f"Geocoding request failed: {exc}") from exc
        except ValueError as exc:  # body is not JSON (e.g. an HTML error page)
            raise GeocodingError(f"Geocoding response was not JSON: {exc}") from exc
    raise GeocodingError("Geocoding request failed")  # pragma: no cover


def _pick(results: list[dict], name: str, state: str | None, country_code: str) -> dict | None:
    """Chooses the candidate for `name` in `state`.

    * only candidates in the requested country (the API filter is also set,
      this is a second guard);
    * for a recognised Indian state, ONLY candidates in that state — a
      same-named place in another state would put the farm (and its
      weather) hundreds of kilometres away;
    * among those, an exact name match wins (largest population first),
      otherwise the provider's top-ranked candidate.
    """
    pool = [
        r for r in results
        if (r.get("country_code") or country_code).upper() == country_code.upper()
    ]
    if not pool:
        return None
    canonical = _canonical_state(state)
    if canonical:
        pool = [r for r in pool if _canonical_state(r.get("admin1")) == canonical]
        if not pool:
            return None
    elif state:
        # Unrecognised state text: previous behaviour — prefer a literal
        # admin1 match, else the top-ranked candidate.
        wanted = state.strip().casefold()
        literal = [r for r in pool if (r.get("admin1") or "").strip().casefold() == wanted]
        pool = literal or pool
    exact = [r for r in pool if _norm(r.get("name", "")) == _norm(name)]
    if exact:
        return max(exact, key=lambda r: r.get("population") or 0)
    return pool[0]


def _to_location(candidate: dict, name: str) -> GeocodedLocation:
    try:
        return GeocodedLocation(
            latitude=float(candidate["latitude"]),
            longitude=float(candidate["longitude"]),
            resolved_name=candidate.get("name", name),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise GeocodingError(f"Geocoding response was malformed: {exc}") from exc


def _query(
    name: str, *, state: str | None, country_code: str, retry_on_missing: bool = True
) -> GeocodedLocation | None:
    data = _fetch(name, country_code=country_code)
    if "results" not in data and retry_on_missing:
        logger.info("Geocoding response for %r omitted 'results' (no match or throttled) — retrying once", name)
        time.sleep(_THROTTLE_RETRY_DELAY_SECONDS)
        data = _fetch(name, country_code=country_code)

    candidate = _pick(data.get("results") or [], name, state, country_code)
    if candidate is None:
        return None
    return _to_location(candidate, name)


def _query_prefix(name: str, *, state: str, country_code: str) -> GeocodedLocation | None:
    """Spelling-variant fallback ("Bagalkote" -> gazetteer "Bagalkot"): search
    by the name minus its last one or two letters and accept only an in-state
    place whose name is that prefix plus at most three letters."""
    cleaned = name.strip()
    if len(cleaned) < 6 or _canonical_state(state) is None:
        return None
    for cut in (1, 2):
        prefix = cleaned[:-cut]
        data = _fetch(prefix, country_code=country_code)
        results = [
            r for r in (data.get("results") or [])
            if _norm(r.get("name", "")).startswith(_norm(prefix))
            and len(_norm(r.get("name", ""))) <= len(_norm(prefix)) + 3
        ]
        candidate = _pick(results, prefix, state, country_code)
        if candidate is not None:
            return _to_location(candidate, name)
    return None


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

    Order of attempts (each only if the previous found nothing): a known
    renamed/HQ alias (_DISTRICT_ALIASES); the name; the name without an
    Urban/Rural suffix; the state as a place name; a one/two-letter
    spelling variant; finally the state capital (_STATE_CAPITALS). Every
    district-level match must lie in the farmer's state when that state is
    recognised, and in India — never a same-named place elsewhere.
    """
    lowered = _norm(name)
    # A known renamed/old district name is tried as its verified current
    # name FIRST: the raw old name can match a different, smaller place in
    # the same state (live: "Vijayapura" -> a village 450 km from the
    # district; "Bellary" -> a road in Bengaluru).
    alias = _DISTRICT_ALIASES.get(lowered)
    if alias and _norm(alias) != lowered:
        result = _query(alias, state=state, country_code=country_code, retry_on_missing=False)
        if result is not None:
            return result

    result = _query(name, state=state, country_code=country_code)
    if result is not None:
        return result

    for suffix in _STRIPPABLE_SUFFIXES:
        if name.strip().casefold().endswith(suffix):
            stripped = name.strip()[: -len(suffix)].strip()
            if stripped:
                result = _query(stripped, state=state, country_code=country_code)
                if result is not None:
                    return result
            break

    if state:
        state_result = _query(state, state=state, country_code=country_code, retry_on_missing=False)
        if state_result is not None:
            state_result.is_approximate = True
            return state_result

        result = _query_prefix(name, state=state, country_code=country_code)
        if result is not None:
            return result

        canonical = _canonical_state(state)
        if canonical and country_code.upper() == "IN":
            capital, lat, lon = _STATE_CAPITALS[canonical]
            logger.info("Geocoding: using %s's capital (%s) as approximate location", state, capital)
            return GeocodedLocation(
                latitude=lat, longitude=lon, resolved_name=capital, is_approximate=True
            )

    return None
