"""
Integration tests for /recommendation — exercises the FULL Vol 10.3
pipeline against the REAL trained XGBoost model artifacts (Phase 6),
with a real farm/soil/weather setup and only the weather provider faked
(no live network access in this sandbox, as in Phase 5's tests).
"""

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
def fake_weather_for_recommendation():
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


@pytest.fixture
def farm_with_real_karnataka_data(client, auth_headers, fake_weather_for_recommendation) -> str:
    """
    Builds a farm and gives it real, validated soil data (via the manual
    correction endpoint — no OCR needed for this test, per soil_service's
    own correct_parameters() which is a legitimate direct data-entry path)
    plus real weather data (via the faked provider), so the
    recommendation service has everything Vol 10.4 requires.
    """
    farm_resp = client.post(
        "/api/v1/farms",
        json={
            "farm_name": "Recommendation Test Farm",
            "state": "Karnataka",
            "district": "Bagalkote",
            "soil_type": "Black Soil",
            "latitude": 16.1667,
            "longitude": 75.8667,
        },
        headers=auth_headers,
    )
    farm_id = farm_resp.json()["data"]["id"]

    import io

    upload_resp = client.post(
        "/api/v1/soil/upload",
        params={"farm_id": farm_id},
        files={"file": ("shc.jpg", io.BytesIO(b"\xff\xd8\xff\xe0fake_jpeg_bytes"), "image/jpeg")},
        headers=auth_headers,
    )
    report_id = upload_resp.json()["data"]["report_id"]

    # Real Karnataka SHC values (rice-favorable rainfall/temp/humidity
    # come from the weather fixture above, same real card's context).
    client.put(
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

    client.get("/api/v1/weather/current", params={"farm_id": farm_id}, headers=auth_headers)

    return farm_id


@pytest.fixture
def farm_id_with_coords_no_soil(client, auth_headers) -> str:
    resp = client.post(
        "/api/v1/farms",
        json={
            "farm_name": "No Soil Data Farm",
            "state": "Karnataka",
            "district": "Bagalkote",
            "latitude": 16.1667,
            "longitude": 75.8667,
        },
        headers=auth_headers,
    )
    return resp.json()["data"]["id"]


def test_recommendation_requires_auth(client, farm_id):
    resp = client.post("/api/v1/recommendation", params={"farm_id": farm_id})
    assert resp.status_code == 401


def test_recommendation_without_soil_data_rejected(client, auth_headers, farm_id_with_coords_no_soil):
    resp = client.post(
        "/api/v1/recommendation", params={"farm_id": farm_id_with_coords_no_soil}, headers=auth_headers
    )
    assert resp.status_code == 400
    assert "soil" in resp.json()["message"].lower()


def test_recommendation_full_pipeline_real_model(client, auth_headers, farm_with_real_karnataka_data):
    resp = client.post(
        "/api/v1/recommendation", params={"farm_id": farm_with_real_karnataka_data}, headers=auth_headers
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]

    assert data["primary_crop"]
    assert 0.0 <= data["confidence"] <= 1.0
    assert len(data["top_recommendations"]) == 5
    assert data["explanation"]
    assert data["model_version"]

    # Confidences must be sorted descending.
    confidences = [r["confidence"] for r in data["top_recommendations"]]
    assert confidences == sorted(confidences, reverse=True)

    # Given near-ideal rice conditions (pH 6.5, high N/P/K, high
    # rainfall/humidity matching real Karnataka monsoon rice conditions),
    # rice should be a strong candidate somewhere in the Top-5.
    top5_crops = [r["crop"] for r in data["top_recommendations"]]
    assert "rice" in top5_crops


def test_recommendation_is_persisted_and_retrievable(client, auth_headers, farm_with_real_karnataka_data):
    create_resp = client.post(
        "/api/v1/recommendation", params={"farm_id": farm_with_real_karnataka_data}, headers=auth_headers
    )
    rec_id = create_resp.json()["data"]["id"]

    get_resp = client.get(f"/api/v1/recommendation/{rec_id}", headers=auth_headers)
    assert get_resp.status_code == 200
    assert get_resp.json()["data"]["primary_crop"] == create_resp.json()["data"]["primary_crop"]


def test_recommendation_ownership_enforced(client, auth_headers, farm_with_real_karnataka_data):
    create_resp = client.post(
        "/api/v1/recommendation", params={"farm_id": farm_with_real_karnataka_data}, headers=auth_headers
    )
    rec_id = create_resp.json()["data"]["id"]

    client.post(
        "/api/v1/auth/register",
        json={
            "full_name": "Other Rec User",
            "email": "otherrec@example.com",
            "phone": "+919777766666",
            "password": "Password123",
        },
    )
    login = client.post(
        "/api/v1/auth/login", json={"identifier": "otherrec@example.com", "password": "Password123"}
    )
    other_headers = {"Authorization": f"Bearer {login.json()['data']['access_token']}"}

    resp = client.get(f"/api/v1/recommendation/{rec_id}", headers=other_headers)
    assert resp.status_code == 404
