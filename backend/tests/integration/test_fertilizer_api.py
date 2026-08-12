"""
Integration tests for /fertilizer/* — builds on a real recommendation
(Phase 7) then generates fertilizer recommendations against the same
soil data, exercising both the KB-sourced path (maize, if it happens to
be predicted) and, more commonly, the fallback path.
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
def fake_weather_for_fertilizer():
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
def recommendation_id_low_npk(client, auth_headers, fake_weather_for_fertilizer) -> str:
    """A recommendation whose underlying soil report has real Karnataka
    SHC-style low N/P/OC values, so the fertilizer engine has genuine
    deficiencies to work with."""
    farm_resp = client.post(
        "/api/v1/farms",
        json={
            "farm_name": "Fertilizer Test Farm",
            "state": "Karnataka",
            "district": "Bagalkote",
            "soil_type": "Black Soil",
            "latitude": 16.1667,
            "longitude": 75.8667,
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

    # Real Karnataka SHC values: low N, low P, medium K, low OC.
    client.put(
        f"/api/v1/soil/{report_id}/correct",
        json={
            "ph": 7.70, "ec": 0.04, "organic_carbon": 0.35,
            "nitrogen": 200.6, "phosphorus": 4.19, "potassium": 122.8,
            "zinc": 0.27, "iron": 0.71, "manganese": 6.41, "copper": 1.65, "boron": 0.63,
        },
        headers=auth_headers,
    )
    client.get("/api/v1/weather/current", params={"farm_id": farm_id}, headers=auth_headers)

    rec_resp = client.post("/api/v1/recommendation", params={"farm_id": farm_id}, headers=auth_headers)
    return rec_resp.json()["data"]["id"]


def test_fertilizer_requires_auth(client, recommendation_id_low_npk):
    resp = client.post(f"/api/v1/fertilizer/{recommendation_id_low_npk}")
    assert resp.status_code == 401


def test_get_before_post_returns_404(client, auth_headers, recommendation_id_low_npk):
    resp = client.get(f"/api/v1/fertilizer/{recommendation_id_low_npk}", headers=auth_headers)
    assert resp.status_code == 404


def test_generate_fertilizer_recommendation(client, auth_headers, recommendation_id_low_npk):
    resp = client.post(f"/api/v1/fertilizer/{recommendation_id_low_npk}", headers=auth_headers)
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]

    assert data["recommendation_id"] == recommendation_id_low_npk
    assert data["crop"]
    assert data["deficiency_profile"]["nitrogen"] == "low"
    assert data["deficiency_profile"]["phosphorus"] == "low"
    assert len(data["fertilizers"]) > 0
    assert data["knowledge_base_coverage"] in ("sourced", "fallback")

    # No entry should ever contain a fabricated bare number-only dosage
    # when the crop is uncovered — either a real sourced kg/ha figure
    # (if the predicted crop happens to be maize) or an explicit
    # "not available" fallback message.
    for f in data["fertilizers"]:
        if data["knowledge_base_coverage"] == "fallback" and f["fertilizer_name"] != "None required":
            assert "not available" in f["dosage"].lower()


def test_generated_recommendation_is_retrievable(client, auth_headers, recommendation_id_low_npk):
    client.post(f"/api/v1/fertilizer/{recommendation_id_low_npk}", headers=auth_headers)
    resp = client.get(f"/api/v1/fertilizer/{recommendation_id_low_npk}", headers=auth_headers)
    assert resp.status_code == 200
    assert len(resp.json()["data"]["fertilizers"]) > 0


def test_regenerating_is_idempotent_not_duplicating(client, auth_headers, recommendation_id_low_npk):
    first = client.post(f"/api/v1/fertilizer/{recommendation_id_low_npk}", headers=auth_headers)
    second = client.post(f"/api/v1/fertilizer/{recommendation_id_low_npk}", headers=auth_headers)
    assert len(first.json()["data"]["fertilizers"]) == len(second.json()["data"]["fertilizers"])


def test_fertilizer_ownership_enforced(client, auth_headers, recommendation_id_low_npk):
    client.post(f"/api/v1/fertilizer/{recommendation_id_low_npk}", headers=auth_headers)

    client.post(
        "/api/v1/auth/register",
        json={
            "full_name": "Other Fert User",
            "email": "otherfert@example.com",
            "phone": "+919666655555",
            "password": "Password123",
        },
    )
    login = client.post(
        "/api/v1/auth/login", json={"identifier": "otherfert@example.com", "password": "Password123"}
    )
    other_headers = {"Authorization": f"Bearer {login.json()['data']['access_token']}"}

    resp = client.get(f"/api/v1/fertilizer/{recommendation_id_low_npk}", headers=other_headers)
    assert resp.status_code == 404
