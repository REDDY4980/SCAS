"""ModelEvaluator — AIB v1.0 Vol 9.11 Model Evaluation metrics."""

from __future__ import annotations

import time
from dataclasses import dataclass

import numpy as np
import xgboost as xgb
from sklearn.metrics import (
    accuracy_score,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
)


@dataclass
class EvaluationReport:
    accuracy: float
    precision_macro: float
    recall_macro: float
    f1_macro: float
    confusion_matrix: list[list[int]]
    feature_importance: dict[str, float]
    inference_latency_ms: float


class ModelEvaluator:
    """Vol 9.16 core component: ModelEvaluator."""

    def evaluate(
        self,
        model: xgb.XGBClassifier,
        X_test: np.ndarray,
        y_test: np.ndarray,
        feature_order: list[str],
    ) -> EvaluationReport:
        start = time.perf_counter()
        y_pred = model.predict(X_test)
        # Vol 9.11 "Inference Latency" — measured per-sample over the test set.
        latency_ms = ((time.perf_counter() - start) / max(len(X_test), 1)) * 1000

        importances = model.feature_importances_
        feature_importance = {
            feature_order[i]: float(importances[i]) for i in range(len(feature_order))
        }

        return EvaluationReport(
            accuracy=float(accuracy_score(y_test, y_pred)),
            precision_macro=float(precision_score(y_test, y_pred, average="macro", zero_division=0)),
            recall_macro=float(recall_score(y_test, y_pred, average="macro", zero_division=0)),
            f1_macro=float(f1_score(y_test, y_pred, average="macro", zero_division=0)),
            confusion_matrix=confusion_matrix(y_test, y_pred).tolist(),
            feature_importance=feature_importance,
            inference_latency_ms=latency_ms,
        )
