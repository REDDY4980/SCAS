"""
/soil/{id}/ocr reliability: error mapping, status lifecycle, retry,
duplicate/concurrent requests, sequential page processing.

Fake engines here inject failures and record call patterns only; real OCR
accuracy and memory are covered by test_ocr_engine_real.py and
docs/OCR_MEMORY_REPORT.md, never by these fakes.
"""

import io
import threading
import time

import pypdfium2 as pdfium
import pytest
from fastapi import Depends

from app.api.v1 import soil as soil_module
from app.core.config import get_settings
from app.core.database import get_db
from app.main import app
from app.ocr import engine as engine_module
from app.ocr import preprocessing
from app.ocr.engine import OCREngine, OCRInferenceError, OCRInitializationError, OCRLine, OCRPageResult
from app.repositories.farm_repository import FarmRepository
from app.repositories.soil_repository import SoilRepository
from app.services import soil_service as soil_service_module
from app.services.soil_service import SoilService
from tests.conftest import KARNATAKA_SHC_PDF_PATH
from tests.fixtures.real_shc_samples import KARNATAKA_SHC_LINES


class ScriptedEngine(OCREngine):
    def __init__(self, behaviour="ok", lines=None, delay=0.0):
        self.behaviour = behaviour
        self.lines = lines if lines is not None else KARNATAKA_SHC_LINES
        self.delay = delay
        self.calls = 0
        self.active = 0
        self.max_active = 0
        self.rendered_at_call: list[int] = []
        self._lock = threading.Lock()

    def extract(self, image):
        with self._lock:
            self.calls += 1
            call_no = self.calls
            self.active += 1
            self.max_active = max(self.max_active, self.active)
        try:
            if self.delay:
                time.sleep(self.delay)
            if self.behaviour == "init_error":
                raise OCRInitializationError("models missing")
            if self.behaviour == "inference_error":
                raise OCRInferenceError("runtime failure")
            if call_no == 1 or not self.lines:
                return OCRPageResult([OCRLine(t, 0.93) for t in self.lines])
            return OCRPageResult([OCRLine("Department of Agriculture, Karnataka Government", 0.9)])
        finally:
            with self._lock:
                self.active -= 1


@pytest.fixture
def use_engine():
    def _install(engine):
        def override(db=Depends(get_db)):
            return SoilService(SoilRepository(db), FarmRepository(db), ocr_engine=engine)

        app.dependency_overrides[soil_module._service] = override
        return engine

    engine_module.reset_for_testing()
    yield _install
    app.dependency_overrides.pop(soil_module._service, None)
    engine_module.reset_for_testing()


def _upload(client, headers, farm_id, data=None, name="shc.pdf", ctype="application/pdf"):
    data = KARNATAKA_SHC_PDF_PATH.read_bytes() if data is None else data
    resp = client.post(
        "/api/v1/soil/upload",
        params={"farm_id": farm_id},
        files={"file": (name, io.BytesIO(data), ctype)},
        headers=headers,
    )
    assert resp.status_code == 202, resp.text
    return resp.json()["data"]["report_id"]


def _status(client, headers, rid):
    return client.get(f"/api/v1/soil/{rid}", headers=headers).json()["data"]["ocr_status"]


def _pdf_bytes(pages):
    pdf = pdfium.PdfDocument.new()
    for _ in range(pages):
        pdf.new_page(595, 842)
    buf = io.BytesIO()
    pdf.save(buf)
    pdf.close()
    return buf.getvalue()


def test_inference_failure_marks_failed_then_retry_succeeds(client, auth_headers, farm_id, use_engine):
    rid = _upload(client, auth_headers, farm_id)
    use_engine(ScriptedEngine("inference_error"))
    resp = client.post(f"/api/v1/soil/{rid}/ocr", headers=auth_headers)
    assert resp.status_code == 422
    assert "re-upload" in resp.json()["message"]
    assert _status(client, auth_headers, rid) == "failed"

    use_engine(ScriptedEngine("ok"))
    retry = client.post(f"/api/v1/soil/{rid}/ocr", headers=auth_headers)
    assert retry.status_code == 200, retry.text
    assert retry.json()["data"]["report_id"] == rid  # same report, no duplicate
    assert _status(client, auth_headers, rid) == "success"


def test_initialization_failure_returns_503_and_marks_failed(client, auth_headers, farm_id, use_engine):
    rid = _upload(client, auth_headers, farm_id)
    use_engine(ScriptedEngine("init_error"))
    resp = client.post(f"/api/v1/soil/{rid}/ocr", headers=auth_headers)
    assert resp.status_code == 503
    assert "manually" in resp.json()["message"]
    assert _status(client, auth_headers, rid) == "failed"


def test_corrupted_pdf_upload_is_rejected_at_ocr_with_clear_message(client, auth_headers, farm_id, use_engine):
    engine = use_engine(ScriptedEngine("ok"))
    rid = _upload(client, auth_headers, farm_id, data=b"%PDF-1.4 definitely broken")
    resp = client.post(f"/api/v1/soil/{rid}/ocr", headers=auth_headers)
    assert resp.status_code == 422
    assert "damaged" in resp.json()["message"]
    assert engine.calls == 0
    assert _status(client, auth_headers, rid) == "failed"


def test_pdf_over_page_limit_rejected_without_ocr(client, auth_headers, farm_id, use_engine):
    engine = use_engine(ScriptedEngine("ok"))
    rid = _upload(client, auth_headers, farm_id, data=_pdf_bytes(6))
    resp = client.post(f"/api/v1/soil/{rid}/ocr", headers=auth_headers)
    assert resp.status_code == 422
    assert "6 pages" in resp.json()["message"]
    assert engine.calls == 0


def test_blank_report_needs_review_with_nothing_invented(client, auth_headers, farm_id, use_engine):
    use_engine(ScriptedEngine("ok", lines=[]))
    rid = _upload(client, auth_headers, farm_id, data=_pdf_bytes(1))
    data = client.post(f"/api/v1/soil/{rid}/ocr", headers=auth_headers).json()["data"]
    assert data["ocr_status"] == "needs_review"
    assert data["soil_parameters"] is None
    assert set(data["missing_fields"]) == {"ph", "ec", "organic_carbon", "nitrogen", "phosphorus", "potassium"}


def test_invalid_ph_is_failed_not_accepted(client, auth_headers, farm_id, use_engine):
    lines = [line.replace("pH 7.70", "pH 17.70") for line in KARNATAKA_SHC_LINES]
    use_engine(ScriptedEngine("ok", lines=lines))
    rid = _upload(client, auth_headers, farm_id)
    data = client.post(f"/api/v1/soil/{rid}/ocr", headers=auth_headers).json()["data"]
    assert data["ocr_status"] == "failed"


def test_missing_mandatory_and_micronutrients(client, auth_headers, farm_id, use_engine):
    lines = [l for l in KARNATAKA_SHC_LINES if "Potassium" not in l and "Zinc" not in l]
    use_engine(ScriptedEngine("ok", lines=lines))
    rid = _upload(client, auth_headers, farm_id)
    data = client.post(f"/api/v1/soil/{rid}/ocr", headers=auth_headers).json()["data"]
    assert data["ocr_status"] == "needs_review"
    assert data["missing_fields"] == ["potassium"]
    assert any("zinc" in w for w in data["warnings"])
    assert data["soil_parameters"]["potassium"] is None  # never invented


def test_conflicting_readings_go_to_review(client, auth_headers, farm_id, use_engine):
    lines = ["1 Zinc (Zn) Zinc sulphate (15 -) 0.5%"] + KARNATAKA_SHC_LINES
    use_engine(ScriptedEngine("ok", lines=lines))
    rid = _upload(client, auth_headers, farm_id)
    data = client.post(f"/api/v1/soil/{rid}/ocr", headers=auth_headers).json()["data"]
    assert data["ocr_status"] == "needs_review"
    assert any("different values" in w for w in data["warnings"])


def test_duplicate_request_for_report_in_progress_gets_409(client, auth_headers, farm_id, use_engine):
    use_engine(ScriptedEngine("ok"))
    rid = _upload(client, auth_headers, farm_id)
    import uuid

    soil_service_module._in_flight.add(uuid.UUID(rid))
    try:
        resp = client.post(f"/api/v1/soil/{rid}/ocr", headers=auth_headers)
        assert resp.status_code == 409
    finally:
        soil_service_module._in_flight.discard(uuid.UUID(rid))
    assert client.post(f"/api/v1/soil/{rid}/ocr", headers=auth_headers).status_code == 200


def test_busy_slots_return_503_without_touching_report(client, auth_headers, farm_id, use_engine, monkeypatch):
    use_engine(ScriptedEngine("ok"))
    rid = _upload(client, auth_headers, farm_id)
    monkeypatch.setattr(get_settings(), "ocr_queue_timeout_seconds", 0.05)
    with engine_module.ocr_slot():
        resp = client.post(f"/api/v1/soil/{rid}/ocr", headers=auth_headers)
    assert resp.status_code == 503
    assert "busy" in resp.json()["message"]
    assert _status(client, auth_headers, rid) == "pending"


def test_concurrent_requests_never_run_ocr_simultaneously(client, auth_headers, farm_id, use_engine):
    engine = use_engine(ScriptedEngine("ok", delay=0.2))
    rids = [_upload(client, auth_headers, farm_id) for _ in range(3)]
    results = {}

    def run(rid):
        results[rid] = client.post(f"/api/v1/soil/{rid}/ocr", headers=auth_headers).status_code

    threads = [threading.Thread(target=run, args=(rid,)) for rid in rids]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert all(code == 200 for code in results.values()), results
    assert engine.max_active == 1


def test_pages_are_ocrd_as_they_are_rendered(client, auth_headers, farm_id, use_engine, monkeypatch):
    """Sequential processing: when page N is OCR'd, exactly N pages have
    been pre-processed — never the whole document up front."""
    produced = []
    original = preprocessing.iter_preprocessed_pages

    def tracking(path):
        for page in original(path):
            produced.append(1)
            yield page

    monkeypatch.setattr(preprocessing, "iter_preprocessed_pages", tracking)

    class Recording(ScriptedEngine):
        def extract(self, image):
            self.rendered_at_call.append(len(produced))
            return super().extract(image)

    engine = use_engine(Recording("ok"))
    rid = _upload(client, auth_headers, farm_id)
    assert client.post(f"/api/v1/soil/{rid}/ocr", headers=auth_headers).status_code == 200
    assert engine.rendered_at_call == [1, 2, 3, 4]


def test_history_and_correction_after_ocr(client, auth_headers, farm_id, use_engine):
    use_engine(ScriptedEngine("ok"))
    rid = _upload(client, auth_headers, farm_id)
    client.post(f"/api/v1/soil/{rid}/ocr", headers=auth_headers)
    fixed = client.put(f"/api/v1/soil/{rid}/correct", json={"zinc": 0.3}, headers=auth_headers)
    assert fixed.status_code == 200
    report = client.get(f"/api/v1/soil/{rid}", headers=auth_headers).json()["data"]
    assert report["soil_parameters"]["zinc"] == pytest.approx(0.3)
    assert report["soil_parameters"]["ph"] == pytest.approx(7.70)
    assert client.get("/api/v1/history", headers=auth_headers).status_code == 200


def test_correction_leaving_mandatory_value_missing_is_not_success(client, auth_headers, farm_id, use_engine):
    lines = [l for l in KARNATAKA_SHC_LINES if " pH " not in f" {l} "]
    use_engine(ScriptedEngine("ok", lines=lines))
    rid = _upload(client, auth_headers, farm_id)
    assert client.post(f"/api/v1/soil/{rid}/ocr", headers=auth_headers).json()["data"]["ocr_status"] == "needs_review"

    partial = client.put(f"/api/v1/soil/{rid}/correct", json={"zinc": 0.27}, headers=auth_headers)
    assert partial.status_code == 200
    assert partial.json()["data"]["ocr_status"] == "needs_review"  # pH still missing

    complete = client.put(f"/api/v1/soil/{rid}/correct", json={"ph": 7.7}, headers=auth_headers)
    assert complete.json()["data"]["ocr_status"] == "success"
