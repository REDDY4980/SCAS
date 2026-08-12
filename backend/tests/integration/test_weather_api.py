"""
Integration tests for /weather/* endpoints.

Uses fake WeatherProviderClient implementations (no real network calls —
this sandbox's egress is restricted and api.open-meteo.com isn't on the
allowlist) so the service's cache/retry/fallback orchestration logic is
exercised exactly as production would run it, against realistic
Open-Meteo-shaped payloads.
"""

from datetime import datetime, timezone

import pytest

from app.main import app
from app.weather.client import RawWeatherResponse, WeatherProviderClient, WeatherProviderError


def _karnataka_weather_payload() -> dict:
    """Built fresh per call so `current.time` always reflects real 'now' —
    a hardcoded past timestamp would make cache-freshness assertions
    depend on how much wall-clock time has passed since this file was
    written, which is exactly the kind of test that looks fine until it
    silently starts failing weeks later."""
    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M")
    return {
        "current": {
            "time": now_iso,
            "temperature_2m": 28.4,
            "relative_humidity_2m": 68.0,
            "wind_speed_10m": 11.2,
            "cloud_cover": 55.0,
            "precipitation": 0.2,
        },
        "daily": {"time": [now_iso[:10]], "rain_sum": [4.8]},
    }


class AlwaysSucceedsClient(WeatherProviderClient):
    name = "open-meteo"

    def __init__(self):
        self.calls = 0

    def fetch(self, latitude, longitude) -> RawWeatherResponse:
        self.calls += 1
        return RawWeatherResponse(provider="open-meteo", payload=_karnataka_weather_payload())


class AlwaysFailsClient(WeatherProviderClient):
    name = "broken"

    def __init__(self):
        self.calls = 0

    def fetch(self, latitude, longitude) -> RawWeatherResponse:
        self.calls += 1
        raise WeatherProviderError("simulated provider outage")


@pytest.fixture
def fake_weather_providers():
    """Overrides the weather service dependency with injectable fake
    primary/fallback clients the test can configure per-scenario."""
    from app.api.v1 import weather as weather_module
    from app.core.database import get_db
    from app.repositories.farm_repository import FarmRepository
    from app.repositories.weather_repository import WeatherRepository
    from app.services.weather_service import WeatherService

    state = {"primary": AlwaysSucceedsClient(), "fallback": AlwaysFailsClient()}

    def override(db=None):
        return WeatherService(
            WeatherRepository(db),
            FarmRepository(db),
            primary_client=state["primary"],
            fallback_client=state["fallback"],
        )

    # FastAPI resolves Depends(get_db) itself; wrap so `db` still flows.
    from fastapi import Depends

    def real_override(db=Depends(get_db)):
        return WeatherService(
            WeatherRepository(db),
            FarmRepository(db),
            primary_client=state["primary"],
            fallback_client=state["fallback"],
        )

    app.dependency_overrides[weather_module._service] = real_override
    yield state
    del app.dependency_overrides[weather_module._service]


@pytest.fixture
def farm_id_with_coords(client, auth_headers) -> str:
    resp = client.post(
        "/api/v1/farms",
        json={
            "farm_name": "Weather Test Farm",
            "state": "Karnataka",
            "district": "Bagalkote",
            "latitude": 16.1667,
            "longitude": 75.8667,
        },
        headers=auth_headers,
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["data"]["id"]


def test_current_weather_requires_auth(client, farm_id_with_coords):
    resp = client.get("/api/v1/weather/current", params={"farm_id": farm_id_with_coords})
    assert resp.status_code == 401


def test_farm_without_coordinates_rejected(client, auth_headers, farm_id, fake_weather_providers):
    resp = client.get("/api/v1/weather/current", params={"farm_id": farm_id}, headers=auth_headers)
    assert resp.status_code == 400


def test_first_call_fetches_and_persists(client, auth_headers, farm_id_with_coords, fake_weather_providers):
    resp = client.get(
        "/api/v1/weather/current", params={"farm_id": farm_id_with_coords}, headers=auth_headers
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["cache_hit"] is False
    assert data["temperature"] == pytest.approx(28.4)
    assert data["rainfall"] == pytest.approx(4.8)
    assert data["season"] == "monsoon"
    assert fake_weather_providers["primary"].calls == 1


def test_second_call_within_ttl_uses_cache(client, auth_headers, farm_id_with_coords, fake_weather_providers):
    client.get("/api/v1/weather/current", params={"farm_id": farm_id_with_coords}, headers=auth_headers)
    resp = client.get(
        "/api/v1/weather/current", params={"farm_id": farm_id_with_coords}, headers=auth_headers
    )
    data = resp.json()["data"]
    assert data["cache_hit"] is True
    # Only the first call should have hit the provider.
    assert fake_weather_providers["primary"].calls == 1


def test_refresh_bypasses_cache(client, auth_headers, farm_id_with_coords, fake_weather_providers):
    client.get("/api/v1/weather/current", params={"farm_id": farm_id_with_coords}, headers=auth_headers)
    resp = client.post(
        "/api/v1/weather/refresh", params={"farm_id": farm_id_with_coords}, headers=auth_headers
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["cache_hit"] is False
    assert fake_weather_providers["primary"].calls == 2


def test_primary_failure_falls_back_to_secondary(
    client, auth_headers, farm_id_with_coords, fake_weather_providers
):
    fake_weather_providers["primary"] = AlwaysFailsClient()
    fake_weather_providers["fallback"] = AlwaysSucceedsClient()
    # Re-register with updated clients since the override closure reads `state` live.
    resp = client.get(
        "/api/v1/weather/current", params={"farm_id": farm_id_with_coords}, headers=auth_headers
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["temperature"] == pytest.approx(28.4)


def test_both_providers_fail_serves_stale_cache(
    client, auth_headers, farm_id_with_coords, fake_weather_providers
):
    # Seed a cached snapshot first.
    client.get("/api/v1/weather/current", params={"farm_id": farm_id_with_coords}, headers=auth_headers)

    # Now break both providers and force a refresh.
    fake_weather_providers["primary"] = AlwaysFailsClient()
    fake_weather_providers["fallback"] = AlwaysFailsClient()
    resp = client.post(
        "/api/v1/weather/refresh", params={"farm_id": farm_id_with_coords}, headers=auth_headers
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["cache_hit"] is True  # served stale, not a 503


def test_both_providers_fail_no_cache_returns_503(client, auth_headers, farm_id_with_coords):
    from app.api.v1 import weather as weather_module
    from app.core.database import get_db
    from app.repositories.farm_repository import FarmRepository
    from app.repositories.weather_repository import WeatherRepository
    from app.services.weather_service import WeatherService
    from fastapi import Depends

    def override(db=Depends(get_db)):
        return WeatherService(
            WeatherRepository(db),
            FarmRepository(db),
            primary_client=AlwaysFailsClient(),
            fallback_client=AlwaysFailsClient(),
        )

    app.dependency_overrides[weather_module._service] = override
    try:
        resp = client.get(
            "/api/v1/weather/current", params={"farm_id": farm_id_with_coords}, headers=auth_headers
        )
        assert resp.status_code == 503
    finally:
        del app.dependency_overrides[weather_module._service]


def test_weather_history(client, auth_headers, farm_id_with_coords, fake_weather_providers):
    client.get("/api/v1/weather/current", params={"farm_id": farm_id_with_coords}, headers=auth_headers)
    client.post("/api/v1/weather/refresh", params={"farm_id": farm_id_with_coords}, headers=auth_headers)

    resp = client.get(f"/api/v1/weather/history/{farm_id_with_coords}", headers=auth_headers)
    assert resp.status_code == 200
    history = resp.json()["data"]
    assert len(history) == 2


def test_weather_ownership_enforced(client, auth_headers, farm_id_with_coords, fake_weather_providers):
    client.post(
        "/api/v1/auth/register",
        json={
            "full_name": "Other Weather User",
            "email": "otherweather@example.com",
            "phone": "+919888822222",
            "password": "Password123",
        },
    )
    login = client.post(
        "/api/v1/auth/login",
        json={"identifier": "otherweather@example.com", "password": "Password123"},
    )
    other_headers = {"Authorization": f"Bearer {login.json()['data']['access_token']}"}

    resp = client.get(
        "/api/v1/weather/current", params={"farm_id": farm_id_with_coords}, headers=other_headers
    )
    assert resp.status_code == 404
