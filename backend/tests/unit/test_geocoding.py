"""Geocoding client tests — resolving farm coordinates from district/state
so farmers never type latitude/longitude directly."""

import httpx
import pytest

from app.weather.geocoding import GeocodingError, geocode_place


def test_geocode_place_success(monkeypatch):
    class FakeResponse:
        def raise_for_status(self):
            pass

        def json(self):
            return {
                "results": [
                    {
                        "name": "Bagalkote",
                        "latitude": 16.1667,
                        "longitude": 75.8667,
                        "admin1": "Karnataka",
                    }
                ]
            }

    monkeypatch.setattr(httpx, "get", lambda *a, **k: FakeResponse())
    location = geocode_place("Bagalkote", state="Karnataka")
    assert location is not None
    assert location.latitude == 16.1667
    assert location.longitude == 75.8667
    assert location.resolved_name == "Bagalkote"


def test_geocode_place_prefers_matching_state_among_candidates(monkeypatch):
    """District names collide across Indian states — the candidate whose
    admin1 matches the farm's own state must win over the top-ranked one."""

    class FakeResponse:
        def raise_for_status(self):
            pass

        def json(self):
            return {
                "results": [
                    {"name": "Bijapur", "latitude": 19.0, "longitude": 81.0, "admin1": "Chhattisgarh"},
                    {"name": "Bijapur", "latitude": 16.83, "longitude": 75.71, "admin1": "Karnataka"},
                ]
            }

    monkeypatch.setattr(httpx, "get", lambda *a, **k: FakeResponse())
    location = geocode_place("Bijapur", state="Karnataka")
    assert location is not None
    assert location.latitude == 16.83
    assert location.longitude == 75.71


def test_geocode_place_retries_with_urban_suffix_stripped(monkeypatch):
    """Real Indian revenue-district records commonly say 'Bengaluru
    Urban', which Open-Meteo's gazetteer doesn't index as a place name —
    the bare 'Bengaluru' does, so a no-match on the full name must retry
    with the suffix stripped rather than giving up."""
    calls = []

    def fake_get(url, params=None, **kwargs):
        calls.append(params["name"])

        class FakeResponse:
            def raise_for_status(self):
                pass

            def json(self):
                if params["name"] == "Bengaluru":
                    return {
                        "results": [
                            {
                                "name": "Bengaluru",
                                "latitude": 12.97194,
                                "longitude": 77.59369,
                                "admin1": "Karnataka",
                            }
                        ]
                    }
                return {"results": []}

        return FakeResponse()

    monkeypatch.setattr(httpx, "get", fake_get)
    location = geocode_place("Bengaluru Urban", state="Karnataka")
    assert location is not None
    assert location.latitude == pytest.approx(12.97194)
    assert calls == ["Bengaluru Urban", "Bengaluru"]


def test_geocode_place_falls_back_to_state_when_district_unmatched(monkeypatch):
    """A district Open-Meteo doesn't index (e.g. a newly carved-out
    Indian district) must still resolve to *something* real rather than
    leaving the farm with no location at all — the state centroid is a
    coarser but still-correct fallback."""
    calls = []

    def fake_get(url, params=None, **kwargs):
        calls.append(params["name"])

        class FakeResponse:
            def raise_for_status(self):
                pass

            def json(self):
                if params["name"] == "Andhra Pradesh":
                    return {
                        "results": [
                            {
                                "name": "Andhra Pradesh",
                                "latitude": 15.9129,
                                "longitude": 79.7400,
                                "admin1": "Andhra Pradesh",
                            }
                        ]
                    }
                return {"results": []}

        return FakeResponse()

    monkeypatch.setattr(httpx, "get", fake_get)
    location = geocode_place("Sri Satya Sai", state="Andhra Pradesh")
    assert location is not None
    assert location.latitude == pytest.approx(15.9129)
    assert location.is_approximate is True
    assert calls == ["Sri Satya Sai", "Andhra Pradesh"]


def test_geocode_place_no_state_given_and_district_unmatched_returns_none(monkeypatch):
    """With no state to fall back to, an unmatched district still yields
    None rather than crashing."""
    monkeypatch.setattr(httpx, "get", lambda *a, **k: type("R", (), {
        "raise_for_status": lambda self: None,
        "json": lambda self: {"results": []},
    })())
    assert geocode_place("Nonexistentplacename12345") is None


def test_geocode_place_state_fallback_also_unmatched_returns_none(monkeypatch):
    monkeypatch.setattr(httpx, "get", lambda *a, **k: type("R", (), {
        "raise_for_status": lambda self: None,
        "json": lambda self: {"results": []},
    })())
    assert geocode_place("Nonexistentplacename12345", state="Nonexistentstate") is None


def test_geocode_place_no_results_returns_none(monkeypatch):
    class FakeResponse:
        def raise_for_status(self):
            pass

        def json(self):
            return {"results": []}

    monkeypatch.setattr(httpx, "get", lambda *a, **k: FakeResponse())
    assert geocode_place("Nonexistentplacename12345") is None


def test_geocode_place_missing_results_key_retries_then_returns_none(monkeypatch):
    """Open-Meteo's free tier signals throttling with a 200 whose body
    omits 'results' entirely, rather than a 429 — this must be retried
    once, not mistaken for 'no such place'."""
    import app.weather.geocoding as geocoding_module

    monkeypatch.setattr(geocoding_module.time, "sleep", lambda _seconds: None)
    calls = []

    class FakeResponse:
        def raise_for_status(self):
            pass

        def json(self):
            calls.append(1)
            return {}

    monkeypatch.setattr(httpx, "get", lambda *a, **k: FakeResponse())
    assert geocode_place("Somewhere") is None
    assert len(calls) == 2  # original attempt + one throttle retry


def test_geocode_place_recovers_after_one_throttled_response(monkeypatch):
    """The retry actually gets used when the second attempt succeeds."""
    import app.weather.geocoding as geocoding_module

    monkeypatch.setattr(geocoding_module.time, "sleep", lambda _seconds: None)
    attempt = {"count": 0}

    class FakeResponse:
        def raise_for_status(self):
            pass

        def json(self):
            attempt["count"] += 1
            if attempt["count"] == 1:
                return {}  # throttled: no "results" key at all
            return {
                "results": [
                    {"name": "Bagalkote", "latitude": 16.1667, "longitude": 75.8667, "admin1": "Karnataka"}
                ]
            }

    monkeypatch.setattr(httpx, "get", lambda *a, **k: FakeResponse())
    location = geocode_place("Bagalkote", state="Karnataka")
    assert location is not None
    assert location.latitude == pytest.approx(16.1667)
    assert attempt["count"] == 2


def test_geocode_place_wraps_timeout(monkeypatch):
    def fake_get(*args, **kwargs):
        raise httpx.TimeoutException("simulated timeout")

    monkeypatch.setattr(httpx, "get", fake_get)
    with pytest.raises(GeocodingError, match="timed out"):
        geocode_place("Bagalkote")


def test_geocode_place_wraps_http_error(monkeypatch):
    def fake_get(*args, **kwargs):
        raise httpx.ConnectError("simulated connection error")

    monkeypatch.setattr(httpx, "get", fake_get)
    with pytest.raises(GeocodingError, match="failed"):
        geocode_place("Bagalkote")


def test_geocode_place_malformed_result_raises(monkeypatch):
    class FakeResponse:
        def raise_for_status(self):
            pass

        def json(self):
            return {"results": [{"name": "Bagalkote"}]}  # missing latitude/longitude

    monkeypatch.setattr(httpx, "get", lambda *a, **k: FakeResponse())
    with pytest.raises(GeocodingError, match="malformed"):
        geocode_place("Bagalkote")
