"""OCR engine factory, initialisation errors, inference errors and slots."""

import threading

import numpy as np
import pytest

from app.core.config import get_settings
from app.ocr import engine as engine_module
from app.ocr.engine import (
    OCRBusyError,
    OCRInferenceError,
    OCRInitializationError,
    OnnxPPOCREngine,
    get_ocr_engine,
    ocr_slot,
)


@pytest.fixture(autouse=True)
def _reset_engine():
    engine_module.reset_for_testing()
    yield
    engine_module.reset_for_testing()


def test_default_backend_is_onnx_and_singleton_is_thread_safe():
    barrier = threading.Barrier(8)
    seen = []

    def worker():
        barrier.wait()
        seen.append(get_ocr_engine())

    threads = [threading.Thread(target=worker) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert len({id(e) for e in seen}) == 1
    assert isinstance(seen[0], OnnxPPOCREngine)


def test_engine_creation_does_not_load_models():
    eng = get_ocr_engine()
    assert eng._system is None  # lazy: nothing loaded until first extract()


def test_bundled_model_files_are_found():
    eng = OnnxPPOCREngine()
    eng._verify_model_files()  # raises if anything is missing


def test_missing_model_files_raise_initialization_error(tmp_path):
    eng = OnnxPPOCREngine(model_dir=tmp_path)
    with pytest.raises(OCRInitializationError, match="missing"):
        eng.extract(np.zeros((64, 64, 3), np.uint8))


def test_inference_failure_is_wrapped(monkeypatch):
    eng = OnnxPPOCREngine()

    class Exploding:
        def __call__(self, image):
            raise RuntimeError("onnxruntime blew up")

    eng._system = Exploding()
    with pytest.raises(OCRInferenceError):
        eng.extract(np.zeros((64, 64, 3), np.uint8))


def test_paddle_backend_without_paddle_installed_fails_cleanly(monkeypatch):
    pytest.importorskip("app.ocr.engine")
    try:
        import paddleocr  # noqa: F401

        pytest.skip("paddleocr is installed in this environment")
    except ImportError:
        pass
    monkeypatch.setattr(get_settings(), "ocr_backend", "paddle")
    eng = get_ocr_engine()
    with pytest.raises(OCRInitializationError, match="not installed"):
        eng.extract(np.zeros((64, 64, 3), np.uint8))


def test_ocr_slot_limits_concurrency(monkeypatch):
    monkeypatch.setattr(get_settings(), "ocr_max_concurrent", 1)
    with ocr_slot():
        with pytest.raises(OCRBusyError):
            with ocr_slot(timeout=0.05):
                pass
    with ocr_slot(timeout=0.05):  # released again
        pass


def test_blank_page_yields_no_lines():
    eng = OnnxPPOCREngine(num_threads=1)
    result = eng.extract(np.full((800, 600, 3), 255, np.uint8))
    assert result.lines == []
    assert result.average_confidence == 0.0
