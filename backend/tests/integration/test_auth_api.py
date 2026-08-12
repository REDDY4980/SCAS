"""
Integration tests for /auth/* and /users/profile — AIB v1.0 Vol 6.14
acceptance criteria, Vol 15.6 API Testing.
"""

from fastapi.testclient import TestClient


def test_register_success(client: TestClient):
    resp = client.post(
        "/api/v1/auth/register",
        json={
            "full_name": "Ravi Kumar",
            "email": "ravi@example.com",
            "phone": "+919812345678",
            "password": "Password123",
        },
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["success"] is True
    assert body["data"]["email"] == "ravi@example.com"
    assert "password" not in body["data"]
    assert "password_hash" not in body["data"]


def test_register_duplicate_email_rejected(client: TestClient, registered_user: dict):
    resp = client.post(
        "/api/v1/auth/register",
        json={
            "full_name": "Another Person",
            "email": registered_user["email"],  # duplicate
            "phone": "+919000000001",
            "password": "Password123",
        },
    )
    assert resp.status_code == 409


def test_register_duplicate_phone_rejected(client: TestClient, registered_user: dict):
    resp = client.post(
        "/api/v1/auth/register",
        json={
            "full_name": "Another Person",
            "email": "someoneelse@example.com",
            "phone": registered_user["phone"],  # duplicate
            "password": "Password123",
        },
    )
    assert resp.status_code == 409


def test_register_weak_password_rejected(client: TestClient):
    resp = client.post(
        "/api/v1/auth/register",
        json={
            "full_name": "Weak Password",
            "email": "weak@example.com",
            "phone": "+919000000002",
            "password": "onlyletters",  # no digit -> AIB Vol 6.6 rejects
        },
    )
    assert resp.status_code == 422


def test_login_success_returns_jwt(client: TestClient, registered_user: dict):
    resp = client.post(
        "/api/v1/auth/login",
        json={"identifier": registered_user["email"], "password": registered_user["password"]},
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["access_token"]
    assert data["token_type"] == "bearer"


def test_login_with_phone_identifier_also_works(client: TestClient, registered_user: dict):
    resp = client.post(
        "/api/v1/auth/login",
        json={"identifier": registered_user["phone"], "password": registered_user["password"]},
    )
    assert resp.status_code == 200


def test_login_wrong_password_rejected(client: TestClient, registered_user: dict):
    resp = client.post(
        "/api/v1/auth/login",
        json={"identifier": registered_user["email"], "password": "WrongPassword1"},
    )
    assert resp.status_code == 401


def test_login_unknown_identifier_rejected(client: TestClient):
    resp = client.post(
        "/api/v1/auth/login",
        json={"identifier": "nobody@example.com", "password": "Whatever123"},
    )
    assert resp.status_code == 401


def test_me_requires_auth(client: TestClient):
    resp = client.get("/api/v1/auth/me")
    assert resp.status_code == 401


def test_me_with_valid_token(client: TestClient, auth_headers: dict, registered_user: dict):
    resp = client.get("/api/v1/auth/me", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["data"]["email"] == registered_user["email"]


def test_me_rejects_garbage_token(client: TestClient):
    resp = client.get("/api/v1/auth/me", headers={"Authorization": "Bearer not.a.real.token"})
    assert resp.status_code == 401


def test_update_profile(client: TestClient, auth_headers: dict):
    resp = client.put(
        "/api/v1/users/profile",
        json={"full_name": "Updated Name", "language": "kn", "theme": "dark"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["full_name"] == "Updated Name"


def test_update_profile_requires_auth(client: TestClient):
    resp = client.put("/api/v1/users/profile", json={"full_name": "X"})
    assert resp.status_code == 401
