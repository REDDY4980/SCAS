"""
Backend-side ML inference loader.

This is deliberately a self-contained duplicate of
`ml/inference/inference_engine.py`'s loading/prediction logic, NOT an
import of the top-level `ml` package. Rationale: the Docker deployment
(Vol 16.4/16.6) only ships the *serialized artifacts* into the backend
container via the `scas_ml_artifacts` volume — the training pipeline
code (ml/training/*, which pulls in Optuna and sklearn's training-only
utilities) is a separate research/training concern (Vol 9.15) that has
no business being imported by the production API process. This mirrors
a common real-world pattern: a training repo produces model artifacts;
a serving process has its own lightweight loader decoupled from the
training codebase (Vol 9.20 "Separate training code from inference
code" — enforced here at the *deployment* boundary, not just the
module boundary).

AIB v1.0 Vol 9.12 (Inference Pipeline), Vol 9.20 (load model once,
never alter feature order).
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path

import joblib
import numpy as np

logger = logging.getLogger("scas.app.ml")


class ModelNotLoadedError(Exception):
    pass


class FeatureValidationError(Exception):
    pass


@dataclass
class CropPrediction:
    crop: str
    confidence: float


@dataclass
class InferenceResult:
    predictions: list[CropPrediction]
    model_version: str
    feature_order: list[str]
    feature_importance: dict[str, float]


class InferenceEngine:
    def __init__(
        self,
        model,
        label_encoder,
        feature_order: list[str],
        model_version: str,
        feature_importance: dict[str, float],
    ):
        self._model = model
        self._label_encoder = label_encoder
        self._feature_order = feature_order
        self._model_version = model_version
        self._feature_importance = feature_importance

    @classmethod
    def load(cls, artifacts_dir: str | Path) -> "InferenceEngine":
        artifacts_dir = Path(artifacts_dir)
        model_path = artifacts_dir / "model.joblib"
        encoder_path = artifacts_dir / "label_encoder.joblib"
        schema_path = artifacts_dir / "feature_schema.json"
        metadata_path = artifacts_dir / "model_metadata.json"

        for path in (model_path, encoder_path, schema_path):
            if not path.exists():
                raise ModelNotLoadedError(
                    f"Missing required ML artifact: {path}. Run "
                    f"`python -m ml.training.run_training` and ensure MODEL_PATH "
                    f"points at the output directory."
                )

        model = joblib.load(model_path)
        label_encoder = joblib.load(encoder_path)
        schema = json.loads(schema_path.read_text())
        feature_order = schema["feature_order"]

        model_version = "unknown"
        feature_importance: dict[str, float] = {}
        if metadata_path.exists():
            metadata = json.loads(metadata_path.read_text())
            model_version = metadata.get("model_version", "unknown")
            feature_importance = metadata.get("feature_importance", {})

        logger.info("InferenceEngine loaded: version=%s features=%s", model_version, feature_order)
        return cls(model, label_encoder, feature_order, model_version, feature_importance)

    @property
    def feature_order(self) -> list[str]:
        return list(self._feature_order)

    @property
    def feature_importance(self) -> dict[str, float]:
        return dict(self._feature_importance)

    def predict_top5(self, features: dict[str, float]) -> InferenceResult:
        missing = [f for f in self._feature_order if f not in features or features[f] is None]
        if missing:
            raise FeatureValidationError(f"Missing required features for inference: {missing}")

        row = [float(features[f]) for f in self._feature_order]
        X = np.array([row], dtype=float)

        probabilities = self._model.predict_proba(X)[0]
        top5_indices = np.argsort(probabilities)[::-1][:5]
        crop_names = self._label_encoder.inverse_transform(top5_indices)

        predictions = [
            CropPrediction(crop=str(crop), confidence=float(probabilities[idx]))
            for crop, idx in zip(crop_names, top5_indices)
        ]
        return InferenceResult(
            predictions=predictions,
            model_version=self._model_version,
            feature_order=self.feature_order,
            feature_importance=self.feature_importance,
        )
