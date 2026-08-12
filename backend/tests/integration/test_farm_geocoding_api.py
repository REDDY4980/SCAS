"""
Integration tests for automatic farm geocoding — farmers never type
latitude/longitude; the backend resolves approximate coordinates from
district/state (or accepts silent GPS coordinates from the client) via
Open-Meteo's geocoding API.
"""

from datetime import datetime, timezone

import httpx
import pytest

from app.main import app
from app.weather.client import RawWeatherResponse, WeatherProviderClient


def _fake_geocoding_response(latitude: float, longitude: float, admin1: str = "Karnataka"):
    class FakeResponse:
        def raise_for_status(self):
            pass

        def json(self):
            return {
                "results": [
                    {"name": "Bagalkote", "latitude": latitude, "longitude": longitude, "admin1": admin1}
                ]
            }

    return FakeResponse()


def _fake_geocoding_not_found_response():
    class FakeResponse:
        def raise_for_status(self):
            pass

        def json(self):
            return {"results": []}

    return FakeResponse()


def test_create_farm_without_coordinates_auto_geocodes(client, auth_headers, monkeypatch):
    monkeypatch.setattr(httpx, "get", lambda *a, **k: _fake_geocoding_response(16.1667, 75.8667))

    resp = client.post(
        "/api/v1/farms",
        json={"farm_name": "Auto Geocoded Farm", "state": "Karnataka", "district": "Bagalkote"},
        headers=auth_headers,
    )
    assert resp.status_code == 201, resp.text
    farm = resp.json()["data"]
    assert farm["latitude"] == pytest.approx(16.1667)
    assert farm["longitude"] == pytest.approx(75.8667)


def test_create_farm_geocoding_not_found_leaves_coordinates_null(client, auth_headers, monkeypatch):
    monkeypatch.setattr(httpx, "get", lambda *a, **k: _fake_geocoding_not_found_response())

    resp = client.post(
        "/api/v1/farms",
        json={"farm_name": "Unresolvable Farm", "state": "Nowhereistan", "district": "Nowhereville"},
        headers=auth_headers,
    )
    # A geocoding miss must never fail farm creation.
    assert resp.status_code == 201, resp.text
    farm = resp.json()["data"]
    assert farm["latitude"] is None
    assert farm["longitude"] is None


def test_create_farm_geocoding_provider_error_leaves_coordinates_null_not_500(
    client, auth_headers, monkeypatch
):
    def fake_get(*args, **kwargs):
        raise httpx.ConnectError("simulated network outage")

    monkeypatch.setattr(httpx, "get", fake_get)

    resp = client.post(
        "/api/v1/farms",
        json={"farm_name": "Geocoding Outage Farm", "state": "Karnataka", "district": "Bagalkote"},
        headers=auth_headers,
    )
    # A geocoding provider failure must degrade gracefully, never crash
    # farm creation (Vol 18.6-style: never surface an internal failure
    # for a best-effort enrichment step).
    assert resp.status_code == 201, resp.text
    farm = resp.json()["data"]
    assert farm["latitude"] is None
    assert farm["longitude"] is None


def test_explicit_coordinates_bypass_geocoding(client, auth_headers, monkeypatch):
    calls = {"count": 0}

    def fake_get(*args, **kwargs):
        calls["count"] += 1
        raise AssertionError("geocoding should not be called when explicit coordinates are given")

    monkeypatch.setattr(httpx, "get", fake_get)

    resp = client.post(
        "/api/v1/farms",
        json={
            "farm_name": "GPS Farm",
            "state": "Karnataka",
            "district": "Bagalkote",
            "latitude": 16.5,
            "longitude": 75.5,
        },
        headers=auth_headers,
    )
    assert resp.status_code == 201, resp.text
    farm = resp.json()["data"]
    assert farm["latitude"] == pytest.approx(16.5)
    assert farm["longitude"] == pytest.approx(75.5)
    assert calls["count"] == 0


def test_update_district_without_coords_regeocodes(client, auth_headers, monkeypatch):
    monkeypatch.setattr(httpx, "get", lambda *a, **k: _fake_geocoding_response(16.1667, 75.8667))
    create_resp = client.post(
        "/api/v1/farms",
        json={"farm_name": "Relocatable Farm", "state": "Karnataka", "district": "Bagalkote"},
        headers=auth_headers,
    )
    farm_id = create_resp.json()["data"]["id"]
    assert create_resp.json()["data"]["latitude"] == pytest.approx(16.1667)

    # Farmer edits the district (e.g. correcting a typo) without ever
    # touching coordinates — the farm should silently re-resolve.
    monkeypatch.setattr(httpx, "get", lambda *a, **k: _fake_geocoding_response(12.9716, 77.5946))
    update_resp = client.put(
        f"/api/v1/farms/{farm_id}", json={"district": "Bengaluru Urban"}, headers=auth_headers
    )
    assert update_resp.status_code == 200, update_resp.text
    updated = update_resp.json()["data"]
    assert updated["latitude"] == pytest.approx(12.9716)
    assert updated["longitude"] == pytest.approx(77.5946)


def test_update_unrelated_field_does_not_regeocode(client, auth_headers, monkeypatch):
    monkeypatch.setattr(httpx, "get", lambda *a, **k: _fake_geocoding_response(16.1667, 75.8667))
    create_resp = client.post(
        "/api/v1/farms",
        json={"farm_name": "Stable Farm", "state": "Karnataka", "district": "Bagalkote"},
        headers=auth_headers,
    )
    farm_id = create_resp.json()["data"]["id"]

    def fail_if_called(*args, **kwargs):
        raise AssertionError("geocoding should not run when district/state are untouched")

    monkeypatch.setattr(httpx, "get", fail_if_called)
    update_resp = client.put(
        f"/api/v1/farms/{farm_id}", json={"soil_type": "Red Soil"}, headers=auth_headers
    )
    assert update_resp.status_code == 200, update_resp.text
    updated = update_resp.json()["data"]
    assert updated["latitude"] == pytest.approx(16.1667)
    assert updated["longitude"] == pytest.approx(75.8667)


# --- End-to-end: the full soil-report-to-recommendation pipeline must
# work using ONLY auto-resolved coordinates, with zero coordinate input
# from the "farmer" anywhere in the flow. ---


class _FakeWeatherClient(WeatherProviderClient):
    name = "open-meteo"

    def fetch(self, latitude, longitude) -> RawWeatherResponse:
        now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M")
        return RawWeatherResponse(
            provider="open-meteo",
            payload={
                "current": {
                    "time": now_iso,
                    "temperature_2m": 20.9,
                    "relative_humidity_2m": 82.0,
                    "wind_speed_10m": 5.0,
                    "cloud_cover": 60.0,
                    "precipitation": 0.0,
                },
                "daily": {"time": [now_iso[:10]], "rain_sum": [203.0]},
            },
        )


@pytest.fixture
def fake_weather_for_geocoded_farm():
    from fastapi import Depends

    from app.api.v1 import weather as weather_module
    from app.core.database import get_db
    from app.repositories.farm_repository import FarmRepository
    from app.repositories.weather_repository import WeatherRepository
    from app.services.weather_service import WeatherService

    def override(db=Depends(get_db)):
        return WeatherService(
            WeatherRepository(db), FarmRepository(db), primary_client=_FakeWeatherClient()
        )

    app.dependency_overrides[weather_module._service] = override
    yield
    del app.dependency_overrides[weather_module._service]


def test_full_pipeline_works_end_to_end_with_auto_resolved_coordinates(
    client, auth_headers, monkeypatch, fake_weather_for_geocoded_farm
):
    # 1. Create a farm exactly as the redesigned frontend now does: no
    #    coordinates in the request at all, only the plain-text fields
    #    a farmer actually fills in.
    monkeypatch.setattr(httpx, "get", lambda *a, **k: _fake_geocoding_response(16.1667, 75.8667))
    farm_resp = client.post(
        "/api/v1/farms",
        json={
            "farm_name": "End To End Farm",
            "state": "Karnataka",
            "district": "Bagalkote",
            "soil_type": "Black Soil",
        },
        headers=auth_headers,
    )
    assert farm_resp.status_code == 201, farm_resp.text
    farm = farm_resp.json()["data"]
    assert farm["latitude"] is not None and farm["longitude"] is not None
    farm_id = farm["id"]

    # 2. Weather must succeed using ONLY the auto-resolved coordinates —
    #    this is the exact 400 ("no GPS coordinates on file") the old
    #    coordinate-less-farm flow used to hit.
    weather_resp = client.get(
        "/api/v1/weather/current", params={"farm_id": farm_id}, headers=auth_headers
    )
    assert weather_resp.status_code == 200, weather_resp.text

    # 3. Soil data via manual correction (equivalent to a completed OCR
    #    pass — see test_recommendation_api.py for why this substitution
    #    is legitimate in this sandbox).
    import io

    upload_resp = client.post(
        "/api/v1/soil/upload",
        params={"farm_id": farm_id},
        files={"file": ("shc.jpg", io.BytesIO(b"\xff\xd8\xff\xe0fake_jpeg_bytes"), "image/jpeg")},
        headers=auth_headers,
    )
    report_id = upload_resp.json()["data"]["report_id"]
    correct_resp = client.put(
        f"/api/v1/soil/{report_id}/correct",
        json={
            "ph": 6.50,
            "ec": 0.04,
            "organic_carbon": 0.75,
            "nitrogen": 300.0,
            "phosphorus": 25.0,
            "potassium": 200.0,
            "zinc": 0.6,
            "iron": 5.0,
            "manganese": 6.41,
            "copper": 1.65,
            "boron": 0.63,
        },
        headers=auth_headers,
    )
    assert correct_resp.status_code == 200, correct_resp.text

    # 4. Crop recommendation — the real hybrid ML+rules pipeline.
    rec_resp = client.post(
        "/api/v1/recommendation", params={"farm_id": farm_id}, headers=auth_headers
    )
    assert rec_resp.status_code == 200, rec_resp.text
    rec_data = rec_resp.json()["data"]
    assert rec_data["primary_crop"]
    assert len(rec_data["top_recommendations"]) == 5

    # 5. Nowhere in this response tree does a coordinate-related error
    #    or field leak into a place a farmer-facing client would surface
    #    it as a blocker — the recommendation simply succeeded.
    assert "latitude" not in rec_resp.json()["message"].lower()
    assert "longitude" not in rec_resp.json()["message"].lower()
