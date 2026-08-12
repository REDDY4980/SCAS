"""
Training orchestration script.

AIB v1.0 Vol 9.14 Model Serialization: stores model.joblib,
label_encoder.joblib, feature_schema.json, model_metadata.json.
Vol 9.15 keeps training code separate from inference code (Vol 9.20).

Usage:
    python -m ml.training.run_training [--trials N] [--data PATH] [--out DIR]
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

import joblib

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # repo root, for `ml.*` imports

from ml.datasets.dataset_loader import DatasetLoader
from ml.evaluation.evaluator import ModelEvaluator
from ml.feature_engineering.feature_engineer import FEATURE_ORDER, FeatureEngineer
from ml.training.trainer import ModelTrainer, RANDOM_SEED

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger("scas.ml.run_training")


def main() -> None:
    parser = argparse.ArgumentParser(description="Train the SCAS XGBoost crop recommendation model.")
    parser.add_argument(
        "--data",
        default=str(Path(__file__).resolve().parents[2] / "datasets" / "crop_recommendation" / "Crop_recommendation.csv"),
    )
    parser.add_argument("--out", default=str(Path(__file__).resolve().parents[1] / "artifacts"))
    parser.add_argument("--trials", type=int, default=25, help="Optuna trial budget (Vol 9.10)")
    args = parser.parse_args()

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    logger.info("Loading and validating dataset: %s", args.data)
    loader = DatasetLoader()
    df, validation_report = loader.load_and_validate(args.data)
    logger.info(
        "Dataset validated: %d rows, %d classes, sha256=%s",
        validation_report.rows,
        validation_report.classes,
        validation_report.sha256,
    )
    for w in validation_report.warnings:
        logger.warning(w)

    logger.info("Preparing features (order: %s)", FEATURE_ORDER)
    engineer = FeatureEngineer()
    prepared = engineer.prepare(df)

    trainer = ModelTrainer()
    split = trainer.split(prepared.X, prepared.y)
    logger.info(
        "Split: train=%d val=%d test=%d",
        len(split.X_train),
        len(split.X_val),
        len(split.X_test),
    )

    n_classes = len(prepared.label_encoder.classes_)
    logger.info("Tuning hyperparameters with Optuna (%d trials)...", args.trials)
    result = trainer.tune_and_train(split.X_train, split.y_train, n_classes, n_trials=args.trials)
    logger.info("Best params: %s", result.best_params)
    logger.info(
        "Cross-val accuracy on training folds: %.4f (+/- %.4f)",
        result.cv_mean_accuracy,
        result.cv_std_accuracy,
    )

    evaluator = ModelEvaluator()
    val_report = evaluator.evaluate(result.model, split.X_val, split.y_val, FEATURE_ORDER)
    test_report = evaluator.evaluate(result.model, split.X_test, split.y_test, FEATURE_ORDER)
    logger.info(
        "Validation: accuracy=%.4f f1_macro=%.4f | Test: accuracy=%.4f f1_macro=%.4f",
        val_report.accuracy,
        val_report.f1_macro,
        test_report.accuracy,
        test_report.f1_macro,
    )
    logger.info("Test-set per-sample inference latency: %.3fms", test_report.inference_latency_ms)

    # --- Serialize (Vol 9.14) ---
    model_path = out_dir / "model.joblib"
    encoder_path = out_dir / "label_encoder.joblib"
    schema_path = out_dir / "feature_schema.json"
    metadata_path = out_dir / "model_metadata.json"

    joblib.dump(result.model, model_path)
    joblib.dump(prepared.label_encoder, encoder_path)

    schema_path.write_text(
        json.dumps({"feature_order": FEATURE_ORDER, "n_features": len(FEATURE_ORDER)}, indent=2)
    )

    metadata = {
        "model_version": datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S"),
        "trained_at": datetime.now(timezone.utc).isoformat(),
        "algorithm": "XGBoost (multi:softprob)",
        "random_seed": RANDOM_SEED,
        "dataset": {
            "source": "Kaggle Crop Recommendation Dataset (Requirement 1 starter dataset)",
            "sha256": validation_report.sha256,
            "rows": validation_report.rows,
            "classes": validation_report.classes,
            "class_names": sorted(prepared.label_encoder.classes_.tolist()),
        },
        "hyperparameters": result.best_params,
        "optuna_trials": args.trials,
        "metrics": {
            "cv_train_accuracy_mean": result.cv_mean_accuracy,
            "cv_train_accuracy_std": result.cv_std_accuracy,
            "validation_accuracy": val_report.accuracy,
            "validation_precision_macro": val_report.precision_macro,
            "validation_recall_macro": val_report.recall_macro,
            "validation_f1_macro": val_report.f1_macro,
            "test_accuracy": test_report.accuracy,
            "test_precision_macro": test_report.precision_macro,
            "test_recall_macro": test_report.recall_macro,
            "test_f1_macro": test_report.f1_macro,
            "test_inference_latency_ms_per_sample": test_report.inference_latency_ms,
        },
        "feature_importance": test_report.feature_importance,
        "feature_order": FEATURE_ORDER,
        "warning": (
            "This model is trained on Requirement 1's public starter dataset, "
            "not proprietary field-collected data. See "
            "datasets/crop_recommendation/ README for details. Do not present "
            "these metrics as validated against real Indian farm conditions."
        ),
    }
    metadata_path.write_text(json.dumps(metadata, indent=2))

    logger.info("Artifacts written to %s:", out_dir)
    for p in (model_path, encoder_path, schema_path, metadata_path):
        logger.info("  %s", p.name)


if __name__ == "__main__":
    main()
