"""
OCR engine abstraction.

AIB v1.0 Vol 7.5:
    Engine: PaddleOCR (PP-OCR models)
    Language: English (expandable)
    Output: detected text, bounding boxes, confidence score
    "Raw OCR output shall be retained for debugging."

The engine is behind an abstract interface (`OCREngine`) so the
downstream pipeline (layout reconstruction, field parsing, validation)
never depends on a specific inference runtime — this satisfies Vol 4.9's
Factory Pattern guidance for ML/OCR loading and lets the pipeline be
unit-tested with fakes.

Two implementations run the SAME bundled PP-OCR model weights
(en_PP-OCRv3_det, en_PP-OCRv4_rec, ch_ppocr_mobile_v2.0_cls) and produce
identical text on the calibration set:

* `OnnxPPOCREngine` (default, OCR_BACKEND=onnx) — ONNX Runtime. Peak
  process memory stays well inside Render's 512 MB free tier.
* `PaddleOCREngine` (OCR_BACKEND=paddle) — PaddleOCR 2.8.1 on
  PaddlePaddle 2.6.2. Needs requirements-paddle.txt; measured at ~1 GB
  peak RSS even with the fixes below, so it is NOT suitable for 512 MB.

Memory/concurrency rules (docs/OCR_MEMORY_REPORT.md):

* Models are loaded lazily, exactly once per process, under a lock — no
  model is loaded at application startup, so auth/farm/weather/market
  endpoints never pay for OCR.
* `ocr_slot()` bounds how many documents are OCR'd at once
  (OCR_MAX_CONCURRENT, default 1). Waiting requests time out with
  `OCRBusyError` rather than piling activations on top of each other.
"""

from __future__ import annotations

import logging
import threading
import time
from abc import ABC, abstractmethod
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from app.core.config import get_settings

logger = logging.getLogger("scas.ocr.engine")


class OCREngineError(RuntimeError):
    """Base class for OCR engine failures (never a document problem)."""


class OCRInitializationError(OCREngineError):
    """The OCR models/runtime could not be loaded."""


class OCRInferenceError(OCREngineError):
    """The OCR runtime failed while processing a page."""


class OCRBusyError(OCREngineError):
    """No OCR slot became free within OCR_QUEUE_TIMEOUT_SECONDS."""


@dataclass
class OCRLine:
    text: str
    confidence: float
    bounding_box: list[tuple[float, float]] | None = None


@dataclass
class OCRPageResult:
    lines: list[OCRLine]

    @property
    def average_confidence(self) -> float:
        if not self.lines:
            return 0.0
        return sum(line.confidence for line in self.lines) / len(self.lines)

    @property
    def raw_lines(self) -> list[str]:
        return [line.text for line in self.lines]


class OCREngine(ABC):
    @abstractmethod
    def extract(self, image: np.ndarray) -> OCRPageResult:
        """Runs OCR on a single pre-processed image and returns detected lines."""

    def warm_up(self) -> None:
        """Optional: force any lazy model load to happen now. No-op by
        default (e.g. test doubles have nothing to warm up)."""


def _rss_mb() -> float | None:
    """Current resident memory of this process in MB (Linux only)."""
    try:
        with open("/proc/self/status") as status:
            for line in status:
                if line.startswith("VmRSS:"):
                    return int(line.split()[1]) / 1024
    except OSError:
        pass
    return None


def resolve_model_dir() -> Path:
    """OCR_MODEL_DIR, else ml/paddleocr_models/onnx next to the code (repo
    checkout: <repo>/ml/...; Docker image: /app/ml/...)."""
    settings = get_settings()
    if settings.ocr_model_dir:
        return Path(settings.ocr_model_dir)
    here = Path(__file__).resolve()
    candidates = [parent / "ml" / "paddleocr_models" / "onnx" for parent in here.parents]
    for candidate in candidates:
        if candidate.is_dir():
            return candidate
    return candidates[2]


class OnnxPPOCREngine(OCREngine):
    """Production OCR engine: PP-OCR models on ONNX Runtime (see ppocr_onnx.py)."""

    def __init__(
        self,
        model_dir: str | Path | None = None,
        use_angle_cls: bool | None = None,
        num_threads: int | None = None,
        auto_rotate: bool | None = None,
    ):
        settings = get_settings()
        self.model_dir = Path(model_dir) if model_dir else resolve_model_dir()
        self.use_angle_cls = settings.ocr_use_angle_cls if use_angle_cls is None else use_angle_cls
        self.num_threads = settings.ocr_num_threads if num_threads is None else num_threads
        self.auto_rotate = settings.ocr_auto_rotate if auto_rotate is None else auto_rotate
        self._system = None
        self._init_lock = threading.Lock()

    def _verify_model_files(self) -> None:
        from app.ocr.ppocr_onnx import REQUIRED_MODEL_FILES

        missing = [name for name in REQUIRED_MODEL_FILES if not (self.model_dir / name).is_file()]
        if missing:
            raise OCRInitializationError(
                f"OCR model files missing from {self.model_dir}: {', '.join(missing)}. "
                "They are bundled in ml/paddleocr_models/onnx/ (see its README.md)."
            )

    def _get_system(self):
        if self._system is not None:
            return self._system
        with self._init_lock:
            if self._system is None:
                self._verify_model_files()
                before = _rss_mb()
                started = time.monotonic()
                try:
                    from app.ocr.ppocr_onnx import PPOCRConfig, PPOCRSystem

                    self._system = PPOCRSystem(
                        self.model_dir,
                        PPOCRConfig(
                            use_angle_cls=self.use_angle_cls,
                            num_threads=self.num_threads,
                            auto_rotate=self.auto_rotate,
                        ),
                    )
                except Exception as exc:
                    raise OCRInitializationError(f"Could not load OCR models: {exc}") from exc
                logger.info(
                    "OCR models loaded (onnx) | dir=%s angle_cls=%s auto_rotate=%s threads=%d | %.1fs | rss %s -> %s MB",
                    self.model_dir,
                    self.use_angle_cls,
                    self.auto_rotate,
                    self.num_threads,
                    time.monotonic() - started,
                    f"{before:.0f}" if before else "?",
                    f"{_rss_mb():.0f}" if before else "?",
                )
        return self._system

    def warm_up(self) -> None:
        self._get_system()

    def extract(self, image: np.ndarray) -> OCRPageResult:
        system = self._get_system()
        try:
            detections = system(image)
        except Exception as exc:
            raise OCRInferenceError(f"OCR inference failed: {exc}") from exc
        return OCRPageResult(
            lines=[
                OCRLine(
                    text=text,
                    confidence=float(confidence),
                    bounding_box=[tuple(point) for point in box],
                )
                for box, text, confidence in detections
            ]
        )


class PaddleOCREngine(OCREngine):
    """
    Optional engine: PaddleOCR 2.8.1 on PaddlePaddle (OCR_BACKEND=paddle,
    `pip install -r requirements-paddle.txt`). Kept for parity checks and
    environments with more memory. Two measured memory defects are fixed
    here, which alone cut peak RSS from ~2.8 GB to ~1 GB:

    1. PaddlePaddle 2.6 enables oneDNN on CPU by default, and PaddleOCR's
       `enable_mkldnn=False` never disables it; oneDNN then caches per input
       shape without bound. We call `Config.disable_mkldnn()`.
    2. Only the classifier calls `try_shrink_memory()`; detection and
       recognition keep every batch's buffers. We release them before each
       new input and after each page.
    """

    def __init__(self, lang: str = "en", use_angle_cls: bool | None = None):
        self.lang = lang
        settings = get_settings()
        self.use_angle_cls = settings.ocr_use_angle_cls if use_angle_cls is None else use_angle_cls
        self._ocr = None
        self._init_lock = threading.Lock()

    @staticmethod
    def _disable_onednn() -> None:
        import paddle.inference as paddle_inference

        config_cls = paddle_inference.Config
        if getattr(config_cls, "_scas_onednn_disabled", False):
            return
        original_disable_gpu = config_cls.disable_gpu

        def disable_gpu_and_onednn(self, *args, **kwargs):
            original_disable_gpu(self, *args, **kwargs)
            self.disable_mkldnn()

        config_cls.disable_gpu = disable_gpu_and_onednn
        config_cls._scas_onednn_disabled = True

    @staticmethod
    def _components(ocr):
        return [
            getattr(ocr, name)
            for name in ("text_detector", "text_recognizer", "text_classifier")
            if getattr(ocr, name, None) is not None
        ]

    def _get_ocr(self):
        if self._ocr is not None:
            return self._ocr
        with self._init_lock:
            if self._ocr is None:
                try:
                    self._disable_onednn()
                    from paddleocr import PaddleOCR
                except ImportError as exc:
                    raise OCRInitializationError(
                        "OCR_BACKEND=paddle but PaddleOCR is not installed. Install "
                        "backend/requirements-paddle.txt, or use OCR_BACKEND=onnx."
                    ) from exc
                logger.info("Loading PaddleOCR model (lang=%s)...", self.lang)
                try:
                    ocr = PaddleOCR(use_angle_cls=self.use_angle_cls, lang=self.lang, show_log=False)
                except Exception as exc:
                    raise OCRInitializationError(f"Could not load PaddleOCR: {exc}") from exc

                class _ShrinkBeforeInput:
                    def __init__(self, handle, predictor):
                        self._handle = handle
                        self._predictor = predictor

                    def __getattr__(self, name):
                        return getattr(self._handle, name)

                    def copy_from_cpu(self, array):
                        self._predictor.try_shrink_memory()
                        return self._handle.copy_from_cpu(array)

                for component in self._components(ocr):
                    component.input_tensor = _ShrinkBeforeInput(
                        component.input_tensor, component.predictor
                    )
                self._ocr = ocr
                logger.info("PaddleOCR model loaded.")
        return self._ocr

    def warm_up(self) -> None:
        self._get_ocr()

    def extract(self, image: np.ndarray) -> OCRPageResult:
        ocr = self._get_ocr()
        try:
            raw_result = ocr.ocr(image, cls=self.use_angle_cls)
        except Exception as exc:
            raise OCRInferenceError(f"OCR inference failed: {exc}") from exc
        finally:
            for component in self._components(ocr):
                component.predictor.try_shrink_memory()

        lines: list[OCRLine] = []
        # PaddleOCR returns [[ [box, (text, confidence)], ... ]] per image.
        for page in raw_result or []:
            for detection in page or []:
                box, (text, confidence) = detection
                lines.append(
                    OCRLine(
                        text=text,
                        confidence=float(confidence),
                        bounding_box=[tuple(point) for point in box],
                    )
                )
        return OCRPageResult(lines=lines)


_engine: OCREngine | None = None
_engine_lock = threading.Lock()
_slot_lock = threading.Lock()
_slots: threading.BoundedSemaphore | None = None


def get_ocr_engine() -> OCREngine:
    """Factory (Vol 4.9) — the single place that decides which engine
    implementation to use. Thread-safe; constructs at most one engine per
    process (models themselves load lazily on first extract())."""
    global _engine
    if _engine is None:
        with _engine_lock:
            if _engine is None:
                backend = get_settings().ocr_backend
                _engine = PaddleOCREngine() if backend == "paddle" else OnnxPPOCREngine()
                logger.info("OCR engine selected: %s", type(_engine).__name__)
    return _engine


def _get_slots() -> threading.BoundedSemaphore:
    global _slots
    if _slots is None:
        with _slot_lock:
            if _slots is None:
                _slots = threading.BoundedSemaphore(get_settings().ocr_max_concurrent)
    return _slots


@contextmanager
def ocr_slot(timeout: float | None = None):
    """Holds one of OCR_MAX_CONCURRENT document-processing slots."""
    settings = get_settings()
    wait = settings.ocr_queue_timeout_seconds if timeout is None else timeout
    slots = _get_slots()
    if not slots.acquire(timeout=wait):
        raise OCRBusyError("All OCR slots are busy.")
    try:
        yield
    finally:
        slots.release()


def reset_for_testing() -> None:
    """Test-only: drop the cached engine and slot semaphore."""
    global _engine, _slots
    with _engine_lock:
        _engine = None
    with _slot_lock:
        _slots = None
