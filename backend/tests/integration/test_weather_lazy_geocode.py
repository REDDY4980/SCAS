"""A farm saved while geocoding was unavailable gets its location resolved on
its first weather request (instead of 400 until the farmer edits the farm)."""

import httpx
from fastapi import Depends

from app.api.v1 import weather as weather_module
from app.core.database import get_db
from app.main import app
from app.repositories.farm_repository import FarmRepository
from app.repositories.weather_repository import WeatherRepository
from app.services.weather_service import WeatherService
from tests.integration.test_weather_api import AlwaysFailsClient, AlwaysSucceedsClient


def _geocoder_up(monkeypatch):
    class R:
        def raise_for_status(self):
            pass

        def json(self):
            return {"results": [{"name": "Bagalkot", "admin1": "Karnataka", "country_code": "IN",
                                 "latitude": 16.187, "longitude": 75.696, "population": 111933}]}

    monkeypatch.setattr(httpx, "get", lambda *a, **k: R())


def test_farm_without_coordinates_is_geocoded_on_first_weather_request(client, auth_headers, farm_id, monkeypatch):
    # conftest's farm was created with geocoding unreachable -> no coordinates
    farm = client.get(f"/api/v1/farms/{farm_id}", headers=auth_headers).json()["data"]
    assert farm["latitude"] is None

    _geocoder_up(monkeypatch)
    primary = AlwaysSucceedsClient()

    def override(db=Depends(get_db)):
        return WeatherService(WeatherRepository(db), FarmRepository(db),
                              primary_client=primary, fallback_client=AlwaysFailsClient())

    app.dependency_overrides[weather_module._service] = override
    try:
        resp = client.get("/api/v1/weather/current", params={"farm_id": farm_id}, headers=auth_headers)
    finally:
        del app.dependency_overrides[weather_module._service]

    assert resp.status_code == 200, resp.text
    assert primary.calls == 1
    farm = client.get(f"/api/v1/farms/{farm_id}", headers=auth_headers).json()["data"]
    assert farm["latitude"] == 16.187 and farm["location_source"] == "district"


def test_still_unresolvable_farm_gets_clear_400(client, auth_headers, farm_id):
    resp = client.get("/api/v1/weather/current", params={"farm_id": farm_id}, headers=auth_headers)
    assert resp.status_code == 400
    assert "location" in resp.json()["message"]
