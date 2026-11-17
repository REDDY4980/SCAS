"""
Farmer location: GPS from the app must be saved on the farm AND on the
farmer profile, and the app must be able to tell GPS from a geocoded guess.
"""

import httpx
import pytest


def _no_network(*a, **k):
    raise AssertionError("geocoder must not be called when GPS coordinates are supplied")


def _geocoder(lat, lon):
    class R:
        def raise_for_status(self):
            pass

        def json(self):
            return {"results": [{"name": "Bagalkote", "latitude": lat, "longitude": lon, "admin1": "Karnataka"}]}

    return lambda *a, **k: R()


def test_profile_has_no_location_before_detection(client, auth_headers):
    p = client.get("/api/v1/users/profile", headers=auth_headers).json()["data"]
    assert p["latitude"] is None and p["location_source"] is None


def test_farm_created_with_gps_saves_farm_and_profile(client, auth_headers, monkeypatch):
    monkeypatch.setattr(httpx, "get", _no_network)
    r = client.post("/api/v1/farms", json={
        "farm_name": "GPS Farm", "state": "Karnataka", "district": "Bagalkote",
        "latitude": 16.1802, "longitude": 75.6961, "location_accuracy_m": 24.0}, headers=auth_headers)
    assert r.status_code == 201, r.text
    farm = r.json()["data"]
    assert farm["location_source"] == "gps" and farm["location_accuracy_m"] == pytest.approx(24.0)
    p = client.get("/api/v1/users/profile", headers=auth_headers).json()["data"]
    assert p["latitude"] == pytest.approx(16.1802) and p["longitude"] == pytest.approx(75.6961)
    assert p["location_source"] == "gps" and p["location_accuracy_m"] == pytest.approx(24.0)
    assert p["location_updated_at"] is not None


def test_farm_without_gps_is_marked_district_and_profile_untouched(client, auth_headers, monkeypatch):
    monkeypatch.setattr(httpx, "get", _geocoder(16.18, 75.70))
    farm = client.post("/api/v1/farms", json={"farm_name": "Typed Farm", "state": "Karnataka", "district": "Bagalkote"},
                       headers=auth_headers).json()["data"]
    assert farm["location_source"] == "district" and farm["location_accuracy_m"] is None
    assert client.get("/api/v1/users/profile", headers=auth_headers).json()["data"]["latitude"] is None


def test_put_location_saves_profile(client, auth_headers):
    r = client.put("/api/v1/users/location", json={"latitude": 12.9716, "longitude": 77.5946, "accuracy_m": 15},
                   headers=auth_headers)
    assert r.status_code == 200, r.text
    p = r.json()["data"]["profile"]
    assert p["latitude"] == pytest.approx(12.9716) and p["location_source"] == "gps"
    assert r.json()["data"]["farm"] is None
    again = client.get("/api/v1/users/profile", headers=auth_headers).json()["data"]
    assert again["longitude"] == pytest.approx(77.5946)


def test_put_location_can_fix_an_approximate_farm(client, auth_headers, monkeypatch):
    monkeypatch.setattr(httpx, "get", _geocoder(16.18, 75.70))
    fid = client.post("/api/v1/farms", json={"farm_name": "Approx Farm", "state": "Karnataka", "district": "Bagalkote"},
                      headers=auth_headers).json()["data"]["id"]
    r = client.put("/api/v1/users/location", json={"latitude": 16.2001, "longitude": 75.6502, "accuracy_m": 9,
                                                   "apply_to_farm_id": fid}, headers=auth_headers)
    farm = r.json()["data"]["farm"]
    assert farm["location_source"] == "gps" and farm["latitude"] == pytest.approx(16.2001)
    stored = client.get(f"/api/v1/farms/{fid}", headers=auth_headers).json()["data"]
    assert stored["location_source"] == "gps" and stored["location_accuracy_m"] == pytest.approx(9)


def test_editing_district_does_not_overwrite_gps(client, auth_headers, monkeypatch):
    monkeypatch.setattr(httpx, "get", _no_network)
    fid = client.post("/api/v1/farms", json={"farm_name": "GPS Farm", "state": "Karnataka", "district": "Bagalkot",
                                             "latitude": 16.1802, "longitude": 75.6961}, headers=auth_headers).json()["data"]["id"]
    r = client.put(f"/api/v1/farms/{fid}", json={"district": "Bagalkote"}, headers=auth_headers)
    assert r.status_code == 200, r.text
    farm = r.json()["data"]
    assert farm["district"] == "Bagalkote" and farm["location_source"] == "gps"
    assert farm["latitude"] == pytest.approx(16.1802)


@pytest.mark.parametrize("body", [
    {"latitude": 95, "longitude": 75},
    {"latitude": 16, "longitude": 190},
    {"latitude": 0, "longitude": 0},
    {"longitude": 75},
])
def test_put_location_rejects_bad_positions(client, auth_headers, body):
    assert client.put("/api/v1/users/location", json=body, headers=auth_headers).status_code == 422


def test_put_location_requires_auth(client):
    assert client.put("/api/v1/users/location", json={"latitude": 16, "longitude": 75}).status_code == 401


def test_put_location_other_users_farm_is_404(client, auth_headers, monkeypatch):
    monkeypatch.setattr(httpx, "get", _geocoder(16.18, 75.70))
    fid = client.post("/api/v1/farms", json={"farm_name": "Mine", "state": "Karnataka", "district": "Bagalkote"},
                      headers=auth_headers).json()["data"]["id"]
    client.post("/api/v1/auth/register", json={"full_name": "Other User", "email": "other@example.com",
                                               "phone": "+919811111111", "password": "StrongPass123"})
    tok = client.post("/api/v1/auth/login", json={"identifier": "other@example.com", "password": "StrongPass123"}).json()["data"]["access_token"]
    r = client.put("/api/v1/users/location", json={"latitude": 16.2, "longitude": 75.6, "apply_to_farm_id": fid},
                   headers={"Authorization": f"Bearer {tok}"})
    assert r.status_code == 404
    mine = client.get(f"/api/v1/farms/{fid}", headers=auth_headers).json()["data"]
    assert mine["location_source"] == "district"
