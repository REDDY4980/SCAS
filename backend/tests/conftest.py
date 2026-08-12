"""
Shared pytest fixtures.

AIB v1.0 Vol 15.4 (Unit Testing) / Vol 15.6 (API Testing).

Tests run against an in-memory SQLite database via FastAPI dependency
overrides. Production always uses PostgreSQL (AIB Vol 5.2) — SQLite here
is a test-only substitution for the repository layer, never the
application's real persistence target.
"""

import os
from pathlib import Path

# Must be set before app.core.config.get_settings() is first called by
# any import below — settings validation is fail-fast (AIB Vol 16.12).
os.environ.setdefault("JWT_SECRET", "test_only_secret_do_not_use_in_prod_0123456789")
os.environ.setdefault(
    "DATABASE_URL", "postgresql://scas_user:pw@localhost:5432/scas_db"
)
os.environ.setdefault("UPLOAD_DIRECTORY", "/tmp/scas_test_uploads")
os.environ.setdefault(
    "MODEL_PATH",
    str(Path(__file__).resolve().parents[2] / "ml" / "artifacts" / "model.joblib"),
)

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import get_db
from app.main import app
from app.models import Base

_REPO_ROOT = Path(__file__).resolve().parents[2]
KARNATAKA_SHC_PDF_PATH = (
    _REPO_ROOT / "datasets" / "ocr_calibration" / "01_Karnataka_SHC_redacted_2017.pdf"
)

_test_engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
_TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=_test_engine)


@pytest.fixture(autouse=True)
def _fresh_schema():
    """Recreate all tables before every test for isolation."""
    Base.metadata.create_all(bind=_test_engine)
    yield
    Base.metadata.drop_all(bind=_test_engine)


def _override_get_db():
    db = _TestSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = _override_get_db


@pytest.fixture
def client() -> TestClient:
    # No `with` context manager: this deliberately skips FastAPI's
    # startup/shutdown lifespan events (including the Postgres
    # reachability check in main.py), which is correct for tests that
    # exercise routes against the overridden SQLite session directly.
    return TestClient(app)


@pytest.fixture
def registered_user(client: TestClient) -> dict:
    payload = {
        "full_name": "Asha Farmer",
        "email": "asha@example.com",
        "phone": "+919876543210",
        "password": "StrongPass123",
    }
    resp = client.post("/api/v1/auth/register", json=payload)
    assert resp.status_code == 201, resp.text
    return payload


@pytest.fixture
def auth_headers(client: TestClient, registered_user: dict) -> dict:
    resp = client.post(
        "/api/v1/auth/login",
        json={"identifier": registered_user["email"], "password": registered_user["password"]},
    )
    assert resp.status_code == 200, resp.text
    token = resp.json()["data"]["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def farm_id(client: TestClient, auth_headers: dict) -> str:
    # No coordinates on purpose: test_weather_api.py's
    # test_farm_without_coordinates_rejected relies on this fixture
    # representing a coordinate-less farm. FarmService.create_farm now
    # attempts real-network geocoding whenever coordinates are missing —
    # in this sandbox's restricted-egress environment that attempt fails
    # and correctly falls back to null coordinates (see
    # test_farm_geocoding_api.py for the mocked/fast version of that same
    # behavior), so this fixture's semantics are preserved; it's just a
    # bit slower per use than a fully offline fixture would be.
    resp = client.post(
        "/api/v1/farms",
        json={
            "farm_name": "Test Farm",
            "state": "Karnataka",
            "district": "Bagalkote",
        },
        headers=auth_headers,
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["data"]["id"]
