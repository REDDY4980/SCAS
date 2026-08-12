"""
InferenceEngine — AIB v1.0 Vol 9.12 Inference Pipeline (up to, but not
including, the Agronomic Rule Engine and Explainability Engine, which
Phase 7 adds on top of this).

Vol 9.20 directives enforced here:
    "Load model once during application startup."
    "Never alter feature order."
    "Never perform inference on raw OCR text."
    "Separate training code from inference code."

This module only imports joblib/numpy — never xgboost's training-time
tuning code (ml.training.*), keeping training and inference genuinely
independent per Vol 9.15's folder separation.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path

import joblib
import numpy as np

logger = logging.getLogger("scas.ml.inference")


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
    predictions: list[CropPrediction]  # Top-5, Vol 9.12
    model_version: str
    feature_order: list[str]


class InferenceEngine:
    """Vol 9.16 core component: InferenceEngine. Vol 4.9 Factory Pattern
    for ML loading — construct once via `InferenceEngine.load(...)` and
    reuse; never re-instantiate per-request."""

    def __init__(self, model, label_encoder, feature_order: list[str], model_version: str):
        self._model = model
        self._label_encoder = label_encoder
        self._feature_order = feature_order
        self._model_version = model_version

    @classmethod
    def load(cls, artifacts_dir: str | Path) -> "InferenceEngine":
        artifacts_dir = Path(artifacts_dir)
        model_path = artifacts_dir / "model.joblib"
        encoder_path = artifacts_dir / "label_encoder.joblib"
        schema_path = artifacts_dir / "feature_schema.json"
        metadata_path = artifacts_dir / "model_metadata.json"

        for path in (model_path, encoder_path, schema_path):
            if not path.exists():
                raise ModelNotLoadedError(f"Missing required ML artifact: {path}")

        model = joblib.load(model_path)
        label_encoder = joblib.load(encoder_path)
        schema = json.loads(schema_path.read_text())
        feature_order = schema["feature_order"]

        model_version = "unknown"
        if metadata_path.exists():
            metadata = json.loads(metadata_path.read_text())
            model_version = metadata.get("model_version", "unknown")

        logger.info(
            "InferenceEngine loaded: version=%s features=%s classes=%d",
            model_version,
            feature_order,
            len(label_encoder.classes_),
        )
        return cls(model, label_encoder, feature_order, model_version)

    @property
    def feature_order(self) -> list[str]:
        return list(self._feature_order)

    def _validate_and_order(self, features: dict[str, float]) -> np.ndarray:
        missing = [f for f in self._feature_order if f not in features or features[f] is None]
        if missing:
            raise FeatureValidationError(f"Missing required features for inference: {missing}")
        # Vol 9.20: "Never alter feature order" — always build the row
        # from self._feature_order, never from dict iteration order.
        row = [float(features[f]) for f in self._feature_order]
        return np.array([row], dtype=float)

    def predict_top5(self, features: dict[str, float]) -> InferenceResult:
        """Vol 9.12: Feature Validation -> Encoding -> Feature Ordering
        -> Probability Prediction -> Top-5 Crop Ranking."""
        X = self._validate_and_order(features)
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
        )
