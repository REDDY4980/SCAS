"""Feature engineering tests — AIB v1.0 Vol 9.6/9.8."""

import pandas as pd
import pytest

from ml.feature_engineering.feature_engineer import FEATURE_ORDER, FeatureEngineer


def test_feature_order_is_fixed():
    assert FEATURE_ORDER == ["N", "P", "K", "temperature", "humidity", "ph", "rainfall"]


def test_prepare_builds_correct_shapes():
    df = pd.DataFrame(
        {
            "N": [90, 20], "P": [42, 60], "K": [43, 40],
            "temperature": [20.0, 30.0], "humidity": [80.0, 50.0],
            "ph": [6.5, 7.0], "rainfall": [200.0, 100.0],
            "label": ["rice", "maize"],
        }
    )
    engineer = FeatureEngineer()
    prepared = engineer.prepare(df)
    assert prepared.X.shape == (2, 7)
    assert prepared.y.shape == (2,)
    assert set(prepared.label_encoder.classes_) == {"rice", "maize"}


def test_prepare_missing_column_raises():
    df = pd.DataFrame({"N": [1], "label": ["rice"]})
    engineer = FeatureEngineer()
    with pytest.raises(ValueError, match="missing required feature columns"):
        engineer.prepare(df)


def test_build_feature_vector_preserves_order():
    engineer = FeatureEngineer()
    # Deliberately unordered dict — output must still follow FEATURE_ORDER.
    values = {"rainfall": 200.0, "N": 90, "ph": 6.5, "K": 43, "P": 42, "humidity": 80.0, "temperature": 20.0}
    vector = engineer.build_feature_vector(values)
    assert vector.shape == (1, 7)
    assert list(vector[0]) == [90, 42, 43, 20.0, 80.0, 6.5, 200.0]


def test_build_feature_vector_missing_field_raises():
    engineer = FeatureEngineer()
    values = {"N": 90, "P": 42, "K": 43, "temperature": 20.0, "humidity": 80.0, "ph": 6.5}  # no rainfall
    with pytest.raises(ValueError, match="missing"):
        engineer.build_feature_vector(values)
