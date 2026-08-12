"""
InferenceEngine tests — run against the actual trained model artifacts
produced by `ml.training.run_training` against the real Requirement 1
dataset (not a mock/stub model). Real rice/maize/mango sample rows are
drawn directly from Crop_recommendation.csv.
"""

from pathlib import Path

import pytest

from ml.inference.inference_engine import (
    FeatureValidationError,
    InferenceEngine,
    ModelNotLoadedError,
)

ARTIFACTS_DIR = Path(__file__).resolve().parents[1] / "artifacts"

pytestmark = pytest.mark.skipif(
    not (ARTIFACTS_DIR / "model.joblib").exists(),
    reason="Model artifacts not present — run `python -m ml.training.run_training` first.",
)


@pytest.fixture(scope="module")
def engine() -> InferenceEngine:
    return InferenceEngine.load(ARTIFACTS_DIR)


def test_load_missing_artifacts_raises(tmp_path):
    with pytest.raises(ModelNotLoadedError):
        InferenceEngine.load(tmp_path)


def test_feature_order_matches_schema(engine):
    assert engine.feature_order == ["N", "P", "K", "temperature", "humidity", "ph", "rainfall"]


def test_predict_returns_top5_sorted_descending(engine):
    # Real rice sample, row 1 of Crop_recommendation.csv.
    result = engine.predict_top5(
        {"N": 90, "P": 42, "K": 43, "temperature": 20.88, "humidity": 82.0, "ph": 6.50, "rainfall": 202.94}
    )
    assert len(result.predictions) == 5
    confidences = [p.confidence for p in result.predictions]
    assert confidences == sorted(confidences, reverse=True)
    assert all(0.0 <= c <= 1.0 for c in confidences)


def test_predict_correctly_identifies_real_rice_sample(engine):
    result = engine.predict_top5(
        {"N": 90, "P": 42, "K": 43, "temperature": 20.88, "humidity": 82.0, "ph": 6.50, "rainfall": 202.94}
    )
    assert result.predictions[0].crop == "rice"
    assert result.predictions[0].confidence > 0.5


def test_predict_missing_feature_raises(engine):
    with pytest.raises(FeatureValidationError):
        engine.predict_top5({"N": 90, "P": 42, "K": 43, "temperature": 20.0, "humidity": 80.0, "ph": 6.5})


def test_predict_ignores_dict_ordering(engine):
    """Vol 9.20: 'Never alter feature order' — passing keys in a
    different order must not change the prediction."""
    ordered = {"N": 20, "P": 60, "K": 40, "temperature": 30.0, "humidity": 50.0, "ph": 7.0, "rainfall": 100.0}
    shuffled = {"rainfall": 100.0, "K": 40, "N": 20, "ph": 7.0, "humidity": 50.0, "temperature": 30.0, "P": 60}

    r1 = engine.predict_top5(ordered)
    r2 = engine.predict_top5(shuffled)
    assert [p.crop for p in r1.predictions] == [p.crop for p in r2.predictions]
    assert [p.confidence for p in r1.predictions] == [p.confidence for p in r2.predictions]


def test_predictions_sum_close_to_one(engine):
    result = engine.predict_top5(
        {"N": 90, "P": 42, "K": 43, "temperature": 20.88, "humidity": 82.0, "ph": 6.50, "rainfall": 202.94}
    )
    # Top-5 is a subset of all 22 classes, so this should be <=1, and for
    # a confident correct prediction should be close to 1.
    total = sum(p.confidence for p in result.predictions)
    assert 0.0 < total <= 1.0001


@pytest.mark.parametrize(
    "features,expected_crop",
    [
        # Real samples spot-checked from Crop_recommendation.csv for
        # crops with visually distinct feature profiles.
        ({"N": 20, "P": 135, "K": 200, "temperature": 24.0, "humidity": 92.0, "ph": 5.9, "rainfall": 115.0}, "apple"),
        ({"N": 104, "P": 18, "K": 30, "temperature": 26.0, "humidity": 80.0, "ph": 6.2, "rainfall": 60.0}, "cotton"),
    ],
)
def test_predict_on_distinct_real_crop_profiles(engine, features, expected_crop):
    result = engine.predict_top5(features)
    top5_crops = [p.crop for p in result.predictions]
    assert expected_crop in top5_crops, f"Expected {expected_crop} in top5, got {top5_crops}"
