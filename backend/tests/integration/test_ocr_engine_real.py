"""
REAL OCR — no fakes. Runs the production ONNX engine on the bundled
calibration documents (datasets/ocr_calibration) and checks:

* parity: the ONNX port reproduces PaddleOCR 2.8.1 + PaddlePaddle 2.6.2
  text exactly (reference captured from the original engine);
* accuracy against hand-verified ground truth (tests/fixtures/real_shc_samples.py);
* the full upload -> OCR -> persist API path with the real engine;
* image inputs, a 180-degree-rotated photo and a degraded scan never
  produce a wrong value that is auto-accepted.
"""

import io
import json
import os
from pathlib import Path

import cv2
import numpy as np
import pypdfium2 as pdfium
import pytest
from fastapi import Depends

from app.api.v1 import soil as soil_module
from app.core.database import get_db
from app.main import app
from app.ocr import field_parser, layout, preprocessing, validation
from app.ocr.engine import OnnxPPOCREngine
from app.repositories.farm_repository import FarmRepository
from app.repositories.soil_repository import SoilRepository
from app.services.soil_service import SoilService
from tests.conftest import KARNATAKA_SHC_PDF_PATH
from tests.fixtures.real_shc_samples import KARNATAKA_SHC_EXPECTED, TASAR_SHC_PAGES_EXPECTED

TASAR_PDF_PATH = KARNATAKA_SHC_PDF_PATH.parent / "02_Central_Tasar_SHCs_redacted_2017.pdf"
REFERENCE = json.loads(
    (Path(__file__).resolve().parents[1] / "fixtures" / "paddleocr_2_8_1_reference.json").read_text()
)
_THREADS = max(1, min(4, os.cpu_count() or 1))
_PERSISTED = ("ph", "ec", "organic_carbon", "nitrogen", "phosphorus", "potassium",
              "zinc", "iron", "manganese", "copper", "boron")


@pytest.fixture(scope="module")
def engine():
    return OnnxPPOCREngine(num_threads=_THREADS, auto_rotate=True)


def _analyse(engine, image):
    result = engine.extract(image)
    parsed = field_parser.parse_lines(layout.reconstruct_rows(result))
    values = {k: v for k, v in parsed.values.items() if k in _PERSISTED}
    status = validation.validate_soil_values(values, result.average_confidence, parsed.conflicts).status
    return parsed, status


@pytest.mark.parametrize("pdf", sorted(REFERENCE["documents"]))
def test_onnx_port_reproduces_paddleocr_text_exactly(pdf):
    faithful = OnnxPPOCREngine(num_threads=_THREADS, auto_rotate=False)
    pages = list(preprocessing.iter_preprocessed_pages(KARNATAKA_SHC_PDF_PATH.parent / pdf))
    for page, expected in zip(pages, REFERENCE["documents"][pdf], strict=True):
        got = faithful.extract(page).lines
        assert [line.text for line in got] == [text for text, _ in expected]
        for line, (_, conf) in zip(got, expected):
            assert line.confidence == pytest.approx(conf, abs=5e-4)


def test_tasar_cards_every_value_exact(engine):
    """4 farmer cards printed sideways: 48 hand-verified values."""
    for page_no, (image, expected) in enumerate(
        zip(preprocessing.iter_preprocessed_pages(TASAR_PDF_PATH), TASAR_SHC_PAGES_EXPECTED, strict=True), 1
    ):
        parsed, status = _analyse(engine, image)
        for name, value in expected.items():
            assert parsed.values.get(name) == pytest.approx(value), f"card {page_no} {name}"
        assert status == "success", f"card {page_no}"


def test_karnataka_document_values_and_no_false_acceptance(engine):
    """The textbook excerpt mentions zinc/iron before the real table: the
    real values must be found, and the disagreement must force review."""
    rows, confidences = [], []
    for image in preprocessing.iter_preprocessed_pages(KARNATAKA_SHC_PDF_PATH):
        result = engine.extract(image)
        confidences.append(result.average_confidence)
        rows.extend(layout.reconstruct_rows(result))
    parsed = field_parser.parse_lines(rows)
    for name in ("ph", "ec", "organic_carbon", "nitrogen", "phosphorus", "potassium",
                 "boron", "manganese", "copper"):
        assert parsed.values[name] == pytest.approx(KARNATAKA_SHC_EXPECTED[name]), name
    assert KARNATAKA_SHC_EXPECTED["zinc"] in parsed.conflicts["zinc"]
    assert KARNATAKA_SHC_EXPECTED["iron"] in parsed.conflicts["iron"]
    values = {k: v for k, v in parsed.values.items() if k in _PERSISTED}
    status = validation.validate_soil_values(values, float(np.mean(confidences)), parsed.conflicts).status
    assert status == "needs_review"


def _tasar_page(index: int, dpi: int = 200) -> np.ndarray:
    return list(preprocessing.iter_pdf_pages(TASAR_PDF_PATH, dpi=dpi))[index]


@pytest.mark.parametrize("suffix", [".png", ".jpg"])
def test_photo_inputs_end_to_end(engine, tmp_path, suffix):
    path = tmp_path / f"card{suffix}"
    cv2.imwrite(str(path), _tasar_page(3))
    image = next(preprocessing.iter_preprocessed_pages(path))
    parsed, status = _analyse(engine, image)
    assert status == "success"
    for name in ("ph", "nitrogen", "phosphorus", "potassium"):
        assert parsed.values[name] == pytest.approx(TASAR_SHC_PAGES_EXPECTED[3][name])


@pytest.mark.parametrize("rotation", [cv2.ROTATE_180, cv2.ROTATE_90_CLOCKWISE])
def test_rotated_photo_never_yields_accepted_wrong_values(engine, tmp_path, rotation):
    path = tmp_path / "rotated.png"
    cv2.imwrite(str(path), cv2.rotate(_tasar_page(0), rotation))
    image = next(preprocessing.iter_preprocessed_pages(path))
    parsed, status = _analyse(engine, image)
    expected = TASAR_SHC_PAGES_EXPECTED[0]
    wrong = [k for k, v in parsed.values.items() if k in expected and v != pytest.approx(expected[k])]
    assert status != "success" or not wrong, wrong


def test_low_quality_scan_never_yields_accepted_wrong_values(engine, tmp_path):
    page = _tasar_page(1, dpi=100)
    page = cv2.GaussianBlur(page, (3, 3), 0)
    path = tmp_path / "low.jpg"
    cv2.imwrite(str(path), page, [cv2.IMWRITE_JPEG_QUALITY, 35])
    image = next(preprocessing.iter_preprocessed_pages(path))
    parsed, status = _analyse(engine, image)
    expected = TASAR_SHC_PAGES_EXPECTED[1]
    wrong = [k for k, v in parsed.values.items() if k in expected and v != pytest.approx(expected[k])]
    assert status != "success" or not wrong, wrong


def test_full_api_pipeline_with_real_engine(client, auth_headers, farm_id, engine):
    """Upload a single-page PDF (Tasar card 4) and OCR it through the API
    with the real engine; values must be persisted exactly."""
    src = pdfium.PdfDocument(str(TASAR_PDF_PATH))
    single = pdfium.PdfDocument.new()
    single.import_pages(src, [3])
    buf = io.BytesIO()
    single.save(buf)
    single.close()
    src.close()

    def override(db=Depends(get_db)):
        return SoilService(SoilRepository(db), FarmRepository(db), ocr_engine=engine)

    app.dependency_overrides[soil_module._service] = override
    try:
        rid = client.post(
            "/api/v1/soil/upload",
            params={"farm_id": farm_id},
            files={"file": ("card4.pdf", io.BytesIO(buf.getvalue()), "application/pdf")},
            headers=auth_headers,
        ).json()["data"]["report_id"]
        resp = client.post(f"/api/v1/soil/{rid}/ocr", headers=auth_headers)
    finally:
        app.dependency_overrides.pop(soil_module._service, None)
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["ocr_status"] == "success"
    persisted = client.get(f"/api/v1/soil/{rid}", headers=auth_headers).json()["data"]["soil_parameters"]
    for name in _PERSISTED:
        assert persisted[name] == pytest.approx(TASAR_SHC_PAGES_EXPECTED[3][name]), name
