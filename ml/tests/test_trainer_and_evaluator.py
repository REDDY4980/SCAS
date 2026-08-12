"""
ModelTrainer / ModelEvaluator smoke tests.

Uses a small synthetic dataset (not the real 2200-row Requirement 1
data) purely to exercise the training/evaluation code paths fast in
CI — the real training run against the actual dataset (98.64% test
accuracy) was performed manually and is documented in
docs/PHASE_6_COMPLETION.md. This test's job is to catch structural
regressions in ModelTrainer/ModelEvaluator, not to re-validate model
quality.
"""

import numpy as np
import pytest

from ml.evaluation.evaluator import ModelEvaluator
from ml.feature_engineering.feature_engineer import FEATURE_ORDER
from ml.training.trainer import ModelTrainer


@pytest.fixture
def synthetic_data():
    rng = np.random.default_rng(42)
    n_per_class = 30
    classes = [0, 1, 2]
    X_parts, y_parts = [], []
    for c in classes:
        # Each class clusters around a different mean so the model can
        # actually learn something above chance — a pure-noise dataset
        # would make "does training even work" indistinguishable from
        # "is accuracy() computed correctly."
        X_parts.append(rng.normal(loc=c * 5, scale=1.0, size=(n_per_class, 7)))
        y_parts.append(np.full(n_per_class, c))
    X = np.vstack(X_parts)
    y = np.concatenate(y_parts)
    return X, y


def test_split_produces_correct_proportions(synthetic_data):
    X, y = synthetic_data
    trainer = ModelTrainer()
    split = trainer.split(X, y)

    total = len(X)
    assert len(split.X_train) == pytest.approx(total * 0.8, abs=2)
    assert len(split.X_val) == pytest.approx(total * 0.1, abs=2)
    assert len(split.X_test) == pytest.approx(total * 0.1, abs=2)
    assert len(split.X_train) + len(split.X_val) + len(split.X_test) == total


def test_split_is_deterministic(synthetic_data):
    X, y = synthetic_data
    trainer = ModelTrainer()
    split1 = trainer.split(X, y)
    split2 = trainer.split(X, y)
    assert np.array_equal(split1.X_train, split2.X_train)


def test_tune_and_train_produces_working_model(synthetic_data):
    X, y = synthetic_data
    trainer = ModelTrainer()
    split = trainer.split(X, y)

    result = trainer.tune_and_train(split.X_train, split.y_train, n_classes=3, n_trials=2)

    assert result.model is not None
    assert 0.0 <= result.cv_mean_accuracy <= 1.0
    # Well-separated synthetic clusters should be easy to learn.
    assert result.cv_mean_accuracy > 0.8

    predictions = result.model.predict(split.X_test)
    assert len(predictions) == len(split.X_test)


def test_evaluator_produces_correct_shapes(synthetic_data):
    X, y = synthetic_data
    trainer = ModelTrainer()
    split = trainer.split(X, y)
    result = trainer.tune_and_train(split.X_train, split.y_train, n_classes=3, n_trials=2)

    evaluator = ModelEvaluator()
    report = evaluator.evaluate(result.model, split.X_test, split.y_test, FEATURE_ORDER)

    assert 0.0 <= report.accuracy <= 1.0
    assert 0.0 <= report.precision_macro <= 1.0
    assert 0.0 <= report.recall_macro <= 1.0
    assert 0.0 <= report.f1_macro <= 1.0
    assert len(report.confusion_matrix) == 3  # 3 classes
    assert len(report.confusion_matrix[0]) == 3
    assert set(report.feature_importance.keys()) == set(FEATURE_ORDER)
    assert report.inference_latency_ms >= 0
