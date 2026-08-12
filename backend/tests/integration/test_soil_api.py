"""
Integration tests for /soil/* endpoints.

Uses the REAL redacted Karnataka Soil Health Card PDF (Requirement 4)
and the REAL preprocessing pipeline (pypdfium2 render -> OpenCV steps).
Only the OCR *engine* itself is faked (PaddleOCR is a heavy model
download unsuitable for a fast test suite) — it returns the actual
analytical values transcribed from that same real card, so the
downstream layout/parsing/validation/persistence path is exercised
exactly as it would be against genuine PaddleOCR output.
"""

import io

import pytest

from app.dependencies.auth import get_current_user
from app.main import app
from app.ocr.engine import OCREngine, OCRLine, OCRPageResult
from tests.conftest import KARNATAKA_SHC_PDF_PATH
from tests.fixtures.real_shc_samples import KARNATAKA_SHC_EXPECTED, KARNATAKA_SHC_LINES


class FakeKarnatakaOCREngine(OCREngine):
    """Returns the real Karnataka SHC table text on the first page only,
    mirroring the actual document layout (table lives on one page of
    the 4-page textbook excerpt)."""

    def __init__(self):
        self.calls = 0

    def extract(self, image) -> OCRPageResult:
        self.calls += 1
        if self.calls == 1:
            lines = [OCRLine(text=t, confidence=0.93) for t in KARNATAKA_SHC_LINES]
        else:
            lines = [OCRLine(text="Department of Agriculture, Karnataka Government", confidence=0.9)]
        return OCRPageResult(lines=lines)


@pytest.fixture
def fake_ocr_engine():
    """Overrides the soil service dependency for the duration of a test
    so /soil/{id}/ocr uses a fake, fast, deterministic OCR engine instead
    of loading real PaddleOCR."""
    from fastapi import Depends

    from app.api.v1 import soil as soil_module
    from app.core.database import get_db
    from app.repositories.farm_repository import FarmRepository
    from app.repositories.soil_repository import SoilRepository
    from app.services.soil_service import SoilService

    engine = FakeKarnatakaOCREngine()

    def override(db=Depends(get_db)):
        return SoilService(SoilRepository(db), FarmRepository(db), ocr_engine=engine)

    app.dependency_overrides[soil_module._service] = override
    yield engine
    del app.dependency_overrides[soil_module._service]


@pytest.fixture
def karnataka_pdf_bytes() -> bytes:
    assert KARNATAKA_SHC_PDF_PATH.exists(), f"Missing fixture file: {KARNATAKA_SHC_PDF_PATH}"
    return KARNATAKA_SHC_PDF_PATH.read_bytes()


def test_upload_requires_auth(client, farm_id, karnataka_pdf_bytes):
    resp = client.post(
        "/api/v1/soil/upload",
        params={"farm_id": farm_id},
        files={"file": ("shc.pdf", io.BytesIO(karnataka_pdf_bytes), "application/pdf")},
    )
    assert resp.status_code == 401


def test_upload_rejects_bad_file_type(client, auth_headers, farm_id):
    resp = client.post(
        "/api/v1/soil/upload",
        params={"farm_id": farm_id},
        files={"file": ("report.txt", io.BytesIO(b"not a real report"), "text/plain")},
        headers=auth_headers,
    )
    assert resp.status_code == 400


def test_upload_rejects_farm_not_owned(client, auth_headers, karnataka_pdf_bytes):
    import uuid

    resp = client.post(
        "/api/v1/soil/upload",
        params={"farm_id": str(uuid.uuid4())},
        files={"file": ("shc.pdf", io.BytesIO(karnataka_pdf_bytes), "application/pdf")},
        headers=auth_headers,
    )
    assert resp.status_code == 404


def test_upload_real_karnataka_pdf_succeeds(client, auth_headers, farm_id, karnataka_pdf_bytes):
    resp = client.post(
        "/api/v1/soil/upload",
        params={"farm_id": farm_id},
        files={"file": ("shc.pdf", io.BytesIO(karnataka_pdf_bytes), "application/pdf")},
        headers=auth_headers,
    )
    assert resp.status_code == 202, resp.text
    data = resp.json()["data"]
    assert data["ocr_status"] == "pending"
    assert data["report_id"]


def test_full_pipeline_real_pdf_fake_engine_extracts_correct_values(
    client, auth_headers, farm_id, karnataka_pdf_bytes, fake_ocr_engine
):
    upload_resp = client.post(
        "/api/v1/soil/upload",
        params={"farm_id": farm_id},
        files={"file": ("shc.pdf", io.BytesIO(karnataka_pdf_bytes), "application/pdf")},
        headers=auth_headers,
    )
    report_id = upload_resp.json()["data"]["report_id"]

    # Real pypdfium2 render + real OpenCV preprocessing run here against
    # the actual Karnataka SHC PDF; only PaddleOCR itself is faked.
    ocr_resp = client.post(f"/api/v1/soil/{report_id}/ocr", headers=auth_headers)
    assert ocr_resp.status_code == 200, ocr_resp.text
    data = ocr_resp.json()["data"]

    assert data["ocr_status"] == "success"
    params = data["soil_parameters"]
    for field_name, expected_value in KARNATAKA_SHC_EXPECTED.items():
        if field_name == "sulphur":
            continue  # not part of the persisted soil_parameters schema (Vol 5.3)
        assert params[field_name] == pytest.approx(expected_value), field_name

    # And it's actually persisted, not just returned in-flight.
    get_resp = client.get(f"/api/v1/soil/{report_id}", headers=auth_headers)
    assert get_resp.status_code == 200
    persisted = get_resp.json()["data"]["soil_parameters"]
    assert persisted["ph"] == pytest.approx(7.70)
    assert persisted["nitrogen"] == pytest.approx(200.6)


def test_manual_correction(client, auth_headers, farm_id, karnataka_pdf_bytes, fake_ocr_engine):
    upload_resp = client.post(
        "/api/v1/soil/upload",
        params={"farm_id": farm_id},
        files={"file": ("shc.pdf", io.BytesIO(karnataka_pdf_bytes), "application/pdf")},
        headers=auth_headers,
    )
    report_id = upload_resp.json()["data"]["report_id"]
    client.post(f"/api/v1/soil/{report_id}/ocr", headers=auth_headers)

    correct_resp = client.put(
        f"/api/v1/soil/{report_id}/correct",
        json={"ph": 7.2, "nitrogen": 210.0},
        headers=auth_headers,
    )
    assert correct_resp.status_code == 200
    data = correct_resp.json()["data"]
    assert data["ocr_status"] == "success"
    assert data["soil_parameters"]["ph"] == pytest.approx(7.2)
    assert data["soil_parameters"]["nitrogen"] == pytest.approx(210.0)
    # Fields not part of the correction payload are preserved.
    assert data["soil_parameters"]["phosphorus"] == pytest.approx(4.19)


def test_get_report_requires_ownership(client, auth_headers, farm_id, karnataka_pdf_bytes):
    upload_resp = client.post(
        "/api/v1/soil/upload",
        params={"farm_id": farm_id},
        files={"file": ("shc.pdf", io.BytesIO(karnataka_pdf_bytes), "application/pdf")},
        headers=auth_headers,
    )
    report_id = upload_resp.json()["data"]["report_id"]

    client.post(
        "/api/v1/auth/register",
        json={
            "full_name": "Other Farmer",
            "email": "othersoil@example.com",
            "phone": "+919999911111",
            "password": "Password123",
        },
    )
    login = client.post(
        "/api/v1/auth/login",
        json={"identifier": "othersoil@example.com", "password": "Password123"},
    )
    other_headers = {"Authorization": f"Bearer {login.json()['data']['access_token']}"}

    resp = client.get(f"/api/v1/soil/{report_id}", headers=other_headers)
    assert resp.status_code == 404
