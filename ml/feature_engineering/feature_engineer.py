"""
FeatureEngineer — AIB v1.0 Vol 9.6/9.8.

Vol 9.8 Preprocessing Strategy: "Preserve feature ordering... Reject
invalid records before inference."

FEATURE_ORDER is the single source of truth for column order everywhere
in the ML pipeline (training, serialization, inference) — Vol 9.20's
"Never alter feature order" directive is enforced structurally by having
exactly one place this order is defined.

Deviation from Vol 9.4's aspirational full feature list (documented in
dataset_loader.py): Requirement 1's actual dataset provides 7 numeric
soil/climate inputs, not the full micronutrient + Season + Wind Speed
set Vol 9.4 describes. FEATURE_ORDER reflects what the model is actually
trained on.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from sklearn.preprocessing import LabelEncoder

FEATURE_ORDER: list[str] = ["N", "P", "K", "temperature", "humidity", "ph", "rainfall"]


@dataclass
class PreparedDataset:
    X: np.ndarray
    y: np.ndarray
    label_encoder: LabelEncoder
    feature_order: list[str]


class FeatureEngineer:
    """Vol 9.16 core component: FeatureEngineer."""

    def prepare(self, df: pd.DataFrame) -> PreparedDataset:
        missing = [c for c in FEATURE_ORDER if c not in df.columns]
        if missing:
            raise ValueError(f"DataFrame is missing required feature columns: {missing}")

        X = df[FEATURE_ORDER].to_numpy(dtype=float)

        encoder = LabelEncoder()
        y = encoder.fit_transform(df["label"].to_numpy())

        return PreparedDataset(X=X, y=y, label_encoder=encoder, feature_order=list(FEATURE_ORDER))

    def build_feature_vector(self, values: dict[str, float]) -> np.ndarray:
        """
        Builds a single ordered feature row for inference from a
        dict of validated soil+climate values (Vol 9.7 Feature Fusion).
        Raises if any required feature is missing — Vol 9.8 "Reject
        invalid records before inference."
        """
        missing = [f for f in FEATURE_ORDER if f not in values or values[f] is None]
        if missing:
            raise ValueError(f"Cannot build feature vector, missing: {missing}")
        return np.array([[values[f] for f in FEATURE_ORDER]], dtype=float)
