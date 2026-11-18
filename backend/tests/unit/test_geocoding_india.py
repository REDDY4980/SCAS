"""
Geocoding behaviour verified against the LIVE Open-Meteo API (see
docs/OCR_MEMORY_REPORT.md, "Weather and location") and pinned here with
fakes so the suite stays offline:

* the country filter parameter is `countryCode` (`country` is ignored and
  the search silently becomes worldwide);
* a recognised Indian state is a hard constraint — never a same-named
  place in another state or country;
* renamed / district-only names resolve through a verified alias table,
  tried before the raw name;
* state names are not in the gazetteer, so the last resort is the state
  capital (approximate);
* one transient transport failure is retried.
"""

import httpx
import pytest

from app.weather import geocoding
from app.weather.geocoding import GeocodingError, geocode_place


class _Resp:
    def __init__(self, body):
        self._body = body

    def raise_for_status(self):
        pass

    def json(self):
        if isinstance(self._body, Exception):
            raise self._body
        return self._body


def _place(name, admin1, lat, lon, country="IN", population=None):
    return {"name": name, "admin1": admin1, "latitude": lat, "longitude": lon,
            "country_code": country, "population": population}


def _route(monkeypatch, table, calls=None):
    """httpx.get fake: `table` maps query name -> list of places (missing = no match)."""
    seen = calls if calls is not None else []

    def fake_get(url, params=None, **kwargs):
        seen.append(dict(params))
        if params["name"] in table:
            return _Resp({"results": table[params["name"]]})
        return _Resp({})  # live API: no match -> no "results" key

    monkeypatch.setattr(httpx, "get", fake_get)
    monkeypatch.setattr(geocoding.time, "sleep", lambda _s: None)
    return seen


def test_country_filter_uses_countrycode_parameter(monkeypatch):
    calls = _route(monkeypatch, {"Pune": [_place("Pune", "Maharashtra", 18.52, 73.85)]})
    geocode_place("Pune", state="Maharashtra")
    assert calls[0]["countryCode"] == "IN"
    assert "country" not in calls[0]


def test_foreign_results_are_never_used(monkeypatch):
    _route(monkeypatch, {"Leh": [_place("Le Havre", "Normandy", 49.49, 0.11, country="FR"),
                                 _place("Leh", "Ladakh", 34.165, 77.584)]})
    loc = geocode_place("Leh", state="Ladakh")
    assert (loc.latitude, loc.longitude) == (34.165, 77.584)


def test_same_name_in_another_state_is_rejected(monkeypatch):
    """Only an out-of-state 'Somapura' exists: the farm must get its own
    state's (approximate) location, not a point in another state."""
    _route(monkeypatch, {"Somapura": [_place("Somapura", "Andhra Pradesh", 12.9, 78.3)]})
    loc = geocode_place("Somapura", state="Karnataka")
    assert loc.is_approximate is True
    assert loc.resolved_name == "Bengaluru"  # Karnataka's capital


def test_exact_name_and_larger_population_preferred_in_state(monkeypatch):
    _route(monkeypatch, {"Mangaluru": [
        _place("Mangalūru", "Karnataka", 14.47, 74.95),
        _place("Mangaluru", "Karnataka", 16.83, 76.64),
        _place("Mangaluru", "Karnataka", 12.917, 74.856, population=499487),
    ]})
    loc = geocode_place("Mangaluru", state="Karnataka")
    assert (loc.latitude, loc.longitude) == (12.917, 74.856)


def test_renamed_district_alias_is_tried_first(monkeypatch):
    """Live: 'Bellary' matches a road in Bengaluru; the city is indexed as 'Ballari'."""
    calls = _route(monkeypatch, {
        "Ballari": [_place("Ballari", "Karnataka", 15.142, 76.924, population=410445)],
        "Bellary": [_place("Bellary Rd", "Karnataka", 13.047, 77.591)],
    })
    loc = geocode_place("Bellary", state="Karnataka")
    assert (loc.latitude, loc.longitude) == (15.142, 76.924)
    assert calls[0]["name"] == "Ballari"


@pytest.mark.parametrize("district,state,query,lat", [
    ("Gulbarga", "Karnataka", "Kalaburagi", 17.336),
    ("East Godavari", "Andhra Pradesh", "Kakinada", 16.96),
    ("North 24 Parganas", "West Bengal", "Barasat", 22.722),
    ("Chhatrapati Sambhajinagar", "Maharashtra", "Aurangabad", 19.878),
])
def test_district_aliases(monkeypatch, district, state, query, lat):
    _route(monkeypatch, {query: [_place(query, state, lat, 80.0)]})
    assert geocode_place(district, state=state).latitude == lat


def test_spelling_variant_by_prefix(monkeypatch):
    _route(monkeypatch, {"Chitradurg": [_place("Chitradurga", "Karnataka", 14.23, 76.40)]})
    loc = geocode_place("Chitradurgaa", state="Karnataka")
    assert loc.latitude == 14.23 and loc.is_approximate is False


def test_state_capital_is_last_resort_and_state_spellings_are_understood(monkeypatch):
    _route(monkeypatch, {})
    loc = geocode_place("Unknownpur", state="Orissa")
    assert loc.is_approximate is True and loc.resolved_name == "Bhubaneswar"
    loc = geocode_place("Unknownpur", state="Tamilnadu")
    assert loc.resolved_name == "Chennai"


def test_unrecognised_state_and_no_match_still_returns_none(monkeypatch):
    _route(monkeypatch, {})
    assert geocode_place("Nowhereville", state="Nowhereistan") is None


def test_transient_transport_error_is_retried_once(monkeypatch):
    attempts = {"n": 0}

    def flaky(url, params=None, **kwargs):
        attempts["n"] += 1
        if attempts["n"] == 1:
            raise httpx.ConnectTimeout("handshake timed out")
        return _Resp({"results": [_place("Ranchi", "Jharkhand", 23.34, 85.31)]})

    monkeypatch.setattr(httpx, "get", flaky)
    loc = geocode_place("Ranchi", state="Jharkhand")
    assert loc.latitude == 23.34 and attempts["n"] == 2


def test_non_json_body_is_a_geocoding_error(monkeypatch):
    monkeypatch.setattr(httpx, "get", lambda *a, **k: _Resp(ValueError("not json")))
    with pytest.raises(GeocodingError):
        geocode_place("Ranchi", state="Jharkhand")
