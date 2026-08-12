"""
ML model registry.

AIB v1.0 Vol 9.20: "Load model once during application startup."
Vol 9.16 core component: ModelRegistry.

Uses lazy-on-first-use rather than eager app-startup loading, so the
rest of the backend (auth, farms, OCR, weather) keeps working even if
no trained model artifacts are present yet (e.g. before Phase 6's
training script has been run in a fresh environment) — the failure is
deferred to the one endpoint that actually needs the model, with a
clear error, rather than blocking the entire API from starting.
"""

from __future__ import annotations

import logging
from pathlib import Path

from app.core.config import get_settings
from app.ml.inference_engine import InferenceEngine

logger = logging.getLogger("scas.app.ml.registry")

_engine: InferenceEngine | None = None


def get_inference_engine() -> InferenceEngine:
    global _engine
    if _engine is None:
        settings = get_settings()
        artifacts_dir = Path(settings.model_path).parent
        logger.info("Loading ML model artifacts from %s (first use)...", artifacts_dir)
        _engine = InferenceEngine.load(artifacts_dir)
    return _engine


def reset_for_testing() -> None:
    """Test-only hook so each test can control artifact loading explicitly."""
    global _engine
    _engine = None
