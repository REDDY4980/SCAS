"""
Integration tests for /farms — AIB v1.0 Vol 6.10 (farm ownership),
Vol 6.14 acceptance criteria ("one user can manage multiple farms").
"""

import uuid

from fastapi.testclient import TestClient

FARM_PAYLOAD = {
    "farm_name": "Green Valley Farm",
    "state": "Karnataka",
    "district": "Bagalkote",
    "village": "Hunagund",
    "latitude": 16.1667,
    "longitude": 75.8667,
    "soil_type": "black",
    "area_acres": 2.5,
}


def test_create_farm_requires_auth(client: TestClient):
    resp = client.post("/api/v1/farms", json=FARM_PAYLOAD)
    assert resp.status_code == 401


def test_create_and_list_farm(client: TestClient, auth_headers: dict):
    create_resp = client.post("/api/v1/farms", json=FARM_PAYLOAD, headers=auth_headers)
    assert create_resp.status_code == 201
    farm = create_resp.json()["data"]
    assert farm["farm_name"] == "Green Valley Farm"

    list_resp = client.get("/api/v1/farms", headers=auth_headers)
    assert list_resp.status_code == 200
    farms = list_resp.json()["data"]
    assert len(farms) == 1
    assert farms[0]["id"] == farm["id"]


def test_user_can_manage_multiple_farms(client: TestClient, auth_headers: dict):
    client.post("/api/v1/farms", json=FARM_PAYLOAD, headers=auth_headers)
    second = {**FARM_PAYLOAD, "farm_name": "Second Farm", "district": "Mysuru"}
    client.post("/api/v1/farms", json=second, headers=auth_headers)

    list_resp = client.get("/api/v1/farms", headers=auth_headers)
    names = {f["farm_name"] for f in list_resp.json()["data"]}
    assert names == {"Green Valley Farm", "Second Farm"}


def test_update_farm(client: TestClient, auth_headers: dict):
    create_resp = client.post("/api/v1/farms", json=FARM_PAYLOAD, headers=auth_headers)
    farm_id = create_resp.json()["data"]["id"]

    update_resp = client.put(
        f"/api/v1/farms/{farm_id}",
        json={"farm_name": "Renamed Farm"},
        headers=auth_headers,
    )
    assert update_resp.status_code == 200
    assert update_resp.json()["data"]["farm_name"] == "Renamed Farm"


def test_delete_farm(client: TestClient, auth_headers: dict):
    create_resp = client.post("/api/v1/farms", json=FARM_PAYLOAD, headers=auth_headers)
    farm_id = create_resp.json()["data"]["id"]

    delete_resp = client.delete(f"/api/v1/farms/{farm_id}", headers=auth_headers)
    assert delete_resp.status_code == 200

    list_resp = client.get("/api/v1/farms", headers=auth_headers)
    assert list_resp.json()["data"] == []


def test_get_nonexistent_farm_404(client: TestClient, auth_headers: dict):
    resp = client.get(f"/api/v1/farms/{uuid.uuid4()}", headers=auth_headers)
    assert resp.status_code == 404


def test_cannot_access_another_users_farm(client: TestClient, auth_headers: dict):
    # Owner creates a farm.
    create_resp = client.post("/api/v1/farms", json=FARM_PAYLOAD, headers=auth_headers)
    farm_id = create_resp.json()["data"]["id"]

    # A second, different user registers and logs in.
    client.post(
        "/api/v1/auth/register",
        json={
            "full_name": "Other Farmer",
            "email": "other@example.com",
            "phone": "+919999999999",
            "password": "Password123",
        },
    )
    login_resp = client.post(
        "/api/v1/auth/login",
        json={"identifier": "other@example.com", "password": "Password123"},
    )
    other_headers = {"Authorization": f"Bearer {login_resp.json()['data']['access_token']}"}

    # AIB Vol 6.10: recommendations/farm access only for owned farms.
    get_resp = client.get(f"/api/v1/farms/{farm_id}", headers=other_headers)
    assert get_resp.status_code == 404

    update_resp = client.put(
        f"/api/v1/farms/{farm_id}", json={"farm_name": "Hijacked"}, headers=other_headers
    )
    assert update_resp.status_code == 404

    delete_resp = client.delete(f"/api/v1/farms/{farm_id}", headers=other_headers)
    assert delete_resp.status_code == 404
