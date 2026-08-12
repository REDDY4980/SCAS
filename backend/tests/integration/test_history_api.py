"""
Integration tests for /history — builds real recommendations (through
the actual trained model) and fertilizer recommendations, then verifies
the history list/detail views correctly assemble everything.
"""

import io
from datetime import datetime, timezone

import pytest

from app.main import app
from app.weather.client import RawWeatherResponse, WeatherProviderClient


class _FakeWeatherClient(WeatherProviderClient):
    name = "open-meteo"

    def fetch(self, latitude, longitude) -> RawWeatherResponse:
        now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M")
        return RawWeatherResponse(
            provider="open-meteo",
            payload={
                "current": {
                    "time": now_iso, "temperature_2m": 20.9, "relative_humidity_2m": 82.0,
                    "wind_speed_10m": 5.0, "cloud_cover": 60.0, "precipitation": 0.0,
                },
                "daily": {"time": [now_iso[:10]], "rain_sum": [203.0]},
            },
        )


@pytest.fixture
def fake_weather_for_history():
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


def _create_farm_with_recommendation(client, auth_headers, farm_name="History Farm"):
    farm_resp = client.post(
        "/api/v1/farms",
        json={
            "farm_name": farm_name, "state": "Karnataka", "district": "Bagalkote",
            "soil_type": "Black Soil", "latitude": 16.1667, "longitude": 75.8667,
        },
        headers=auth_headers,
    )
    farm_id = farm_resp.json()["data"]["id"]

    upload_resp = client.post(
        "/api/v1/soil/upload",
        params={"farm_id": farm_id},
        files={"file": ("shc.jpg", io.BytesIO(b"\xff\xd8\xff\xe0fake"), "image/jpeg")},
        headers=auth_headers,
    )
    report_id = upload_resp.json()["data"]["report_id"]

    client.put(
        f"/api/v1/soil/{report_id}/correct",
        json={
            "ph": 6.50, "ec": 0.04, "organic_carbon": 0.75,
            "nitrogen": 300.0, "phosphorus": 25.0, "potassium": 200.0,
            "zinc": 0.6, "iron": 5.0, "manganese": 6.41, "copper": 1.65, "boron": 0.63,
        },
        headers=auth_headers,
    )
    client.get("/api/v1/weather/current", params={"farm_id": farm_id}, headers=auth_headers)

    rec_resp = client.post("/api/v1/recommendation", params={"farm_id": farm_id}, headers=auth_headers)
    rec_id = rec_resp.json()["data"]["id"]
    client.post(f"/api/v1/fertilizer/{rec_id}", headers=auth_headers)

    return farm_id, rec_id


def test_history_requires_auth(client):
    resp = client.get("/api/v1/history")
    assert resp.status_code == 401


def test_empty_history_for_new_user(client, auth_headers):
    resp = client.get("/api/v1/history", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["data"] == []


def test_history_lists_completed_analysis(client, auth_headers, fake_weather_for_history):
    farm_id, rec_id = _create_farm_with_recommendation(client, auth_headers)

    resp = client.get("/api/v1/history", headers=auth_headers)
    assert resp.status_code == 200
    entries = resp.json()["data"]
    assert len(entries) == 1
    assert entries[0]["id"] == rec_id
    assert entries[0]["farm_name"] == "History Farm"
    assert entries[0]["recommended_crop"]


def test_history_spans_multiple_farms_ordered_newest_first(client, auth_headers, fake_weather_for_history):
    _, rec1 = _create_farm_with_recommendation(client, auth_headers, "Farm A")
    _, rec2 = _create_farm_with_recommendation(client, auth_headers, "Farm B")

    resp = client.get("/api/v1/history", headers=auth_headers)
    entries = resp.json()["data"]
    assert len(entries) == 2
    assert entries[0]["id"] == rec2  # most recent first
    assert entries[1]["id"] == rec1


def test_history_filter_by_farm(client, auth_headers, fake_weather_for_history):
    farm_a, rec1 = _create_farm_with_recommendation(client, auth_headers, "Farm A")
    farm_b, rec2 = _create_farm_with_recommendation(client, auth_headers, "Farm B")

    resp = client.get("/api/v1/history", params={"farm_id": farm_a}, headers=auth_headers)
    entries = resp.json()["data"]
    assert len(entries) == 1
    assert entries[0]["id"] == rec1


def test_history_detail_combines_soil_weather_fertilizer(client, auth_headers, fake_weather_for_history):
    _, rec_id = _create_farm_with_recommendation(client, auth_headers)

    resp = client.get(f"/api/v1/history/{rec_id}", headers=auth_headers)
    assert resp.status_code == 200
    detail = resp.json()["data"]

    assert detail["soil_parameters"]["ph"] == pytest.approx(6.50)
    assert detail["soil_parameters"]["nitrogen"] == pytest.approx(300.0)
    assert detail["weather"]["temperature"] == pytest.approx(20.9)
    assert len(detail["fertilizer_recommendations"]) > 0
    assert detail["reasoning"]


def test_history_detail_ownership_enforced(client, auth_headers, fake_weather_for_history):
    _, rec_id = _create_farm_with_recommendation(client, auth_headers)

    client.post(
        "/api/v1/auth/register",
        json={
            "full_name": "Other History User", "email": "otherhist@example.com",
            "phone": "+919555544444", "password": "Password123",
        },
    )
    login = client.post(
        "/api/v1/auth/login", json={"identifier": "otherhist@example.com", "password": "Password123"}
    )
    other_headers = {"Authorization": f"Bearer {login.json()['data']['access_token']}"}

    resp = client.get(f"/api/v1/history/{rec_id}", headers=other_headers)
    assert resp.status_code == 404

    list_resp = client.get("/api/v1/history", headers=other_headers)
    assert list_resp.json()["data"] == []  # other user sees nothing


def test_history_filter_by_unowned_farm_404(client, auth_headers, fake_weather_for_history):
    import uuid

    resp = client.get(
        "/api/v1/history", params={"farm_id": str(uuid.uuid4())}, headers=auth_headers
    )
    assert resp.status_code == 404
