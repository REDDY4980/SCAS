"""
OCR engine abstraction.

AIB v1.0 Vol 7.5:
    Engine: PaddleOCR
    Language: English (expandable)
    Output: detected text, bounding boxes, confidence score
    "Raw OCR output shall be retained for debugging."

The engine is behind an abstract interface (`OCREngine`) so the
downstream pipeline (layout reconstruction, field parsing, validation)
never depends on PaddleOCR directly — this satisfies Vol 4.9's
Factory Pattern guidance for ML/OCR loading and lets the pipeline be
unit-tested without the (heavy, GPU-friendly-but-slow-to-cold-start)
PaddleOCR runtime installed.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass

import numpy as np

logger = logging.getLogger("scas.ocr.engine")


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


class PaddleOCREngine(OCREngine):
    """
    Production OCR engine (Vol 7.5). PaddleOCR is loaded lazily and once
    per process (Vol 9.20 "load model once during application startup"
    applies equally well here) — the first `extract()` call pays the
    model-load cost; subsequent calls reuse the loaded model.
    """

    _shared_instance = None  # class-level singleton, set on first use

    def __init__(self, lang: str = "en"):
        self.lang = lang
        self._ocr = None

    def _get_ocr(self):
        if self._ocr is None:
            try:
                from paddleocr import PaddleOCR
            except ImportError as exc:  # pragma: no cover - exercised only without the dep
                raise RuntimeError(
                    "PaddleOCR is not installed. Install it via "
                    "`pip install -r requirements.txt` (paddleocr + paddlepaddle) "
                    "to run real OCR. See app/ocr/engine.py."
                ) from exc
            logger.info("Loading PaddleOCR model (lang=%s)...", self.lang)
            self._ocr = PaddleOCR(use_angle_cls=True, lang=self.lang, show_log=False)
            logger.info("PaddleOCR model loaded.")
        return self._ocr

    def extract(self, image: np.ndarray) -> OCRPageResult:
        ocr = self._get_ocr()
        raw_result = ocr.ocr(image, cls=True)

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

    def warm_up(self) -> None:
        """
        Forces the lazy PaddleOCR load to happen now rather than on the
        first real request. Must be called from within the actual
        server process (e.g. FastAPI's lifespan startup) — instantiating
        PaddleOCR in a separate short-lived `python3 -c "..."` process
        (a Dockerfile RUN step, or a standalone entrypoint.sh warm-up
        step) reliably crashes here ("free(): invalid pointer" /
        "munmap_chunk(): invalid pointer"), reproduced repeatedly
        against this exact image, while the identical call succeeds
        every time inside the long-lived uvicorn worker process. The
        cause wasn't pinned down further than that process-identity
        difference, but the fix is simple: only ever warm this up from
        inside the process that will actually serve requests.
        """
        self._get_ocr()

    @classmethod
    def shared(cls) -> "PaddleOCREngine":
        if cls._shared_instance is None:
            cls._shared_instance = cls()
        return cls._shared_instance


def get_ocr_engine() -> OCREngine:
    """Factory (Vol 4.9) — the single place that decides which engine implementation to use."""
    return PaddleOCREngine.shared()
