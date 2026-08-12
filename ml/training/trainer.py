"""
ModelTrainer — AIB v1.0 Vol 9.9 (Training Strategy), Vol 9.10
(Hyperparameter Optimisation: Optuna preferred).

Vol 9.9: Train 80% / Validation 10% / Test 10%, fixed random seed,
stratified 5-fold cross-validation.
Vol 9.3: XGBoost only — Random Forest is intentionally excluded.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import numpy as np
import optuna
import xgboost as xgb
from sklearn.model_selection import StratifiedKFold, cross_val_score, train_test_split

logger = logging.getLogger("scas.ml.trainer")
optuna.logging.set_verbosity(optuna.logging.WARNING)  # keep training logs readable

RANDOM_SEED = 42  # Vol 9.9: "Random Seed : Fixed"


@dataclass
class SplitData:
    X_train: np.ndarray
    X_val: np.ndarray
    X_test: np.ndarray
    y_train: np.ndarray
    y_val: np.ndarray
    y_test: np.ndarray


@dataclass
class TrainingResult:
    model: xgb.XGBClassifier
    best_params: dict
    cv_mean_accuracy: float
    cv_std_accuracy: float


class ModelTrainer:
    """Vol 9.16 core component: ModelTrainer."""

    def split(self, X: np.ndarray, y: np.ndarray) -> SplitData:
        # 80 / 10 / 10 stratified split (Vol 9.9).
        X_train, X_temp, y_train, y_temp = train_test_split(
            X, y, test_size=0.20, stratify=y, random_state=RANDOM_SEED
        )
        X_val, X_test, y_val, y_test = train_test_split(
            X_temp, y_temp, test_size=0.50, stratify=y_temp, random_state=RANDOM_SEED
        )
        return SplitData(X_train, X_val, X_test, y_train, y_val, y_test)

    def _objective(self, trial: optuna.Trial, X: np.ndarray, y: np.ndarray, n_classes: int) -> float:
        params = {
            "learning_rate": trial.suggest_float("learning_rate", 0.01, 0.3, log=True),
            "max_depth": trial.suggest_int("max_depth", 3, 10),
            "n_estimators": trial.suggest_int("n_estimators", 50, 300),
            "subsample": trial.suggest_float("subsample", 0.6, 1.0),
            "colsample_bytree": trial.suggest_float("colsample_bytree", 0.6, 1.0),
            "gamma": trial.suggest_float("gamma", 0.0, 5.0),
            "min_child_weight": trial.suggest_int("min_child_weight", 1, 10),
            "objective": "multi:softprob",
            "num_class": n_classes,
            "random_state": RANDOM_SEED,
            "eval_metric": "mlogloss",
        }
        model = xgb.XGBClassifier(**params)
        cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=RANDOM_SEED)
        scores = cross_val_score(model, X, y, cv=cv, scoring="accuracy", n_jobs=-1)
        return float(scores.mean())

    def tune_and_train(
        self, X_train: np.ndarray, y_train: np.ndarray, n_classes: int, n_trials: int = 25
    ) -> TrainingResult:
        """Vol 9.10: Optuna tunes learning_rate, max_depth, n_estimators,
        subsample, colsample_bytree, gamma, min_child_weight."""
        study = optuna.create_study(
            direction="maximize", sampler=optuna.samplers.TPESampler(seed=RANDOM_SEED)
        )
        study.optimize(
            lambda trial: self._objective(trial, X_train, y_train, n_classes),
            n_trials=n_trials,
            show_progress_bar=False,
        )

        best_params = dict(study.best_params)
        best_params.update(
            {
                "objective": "multi:softprob",
                "num_class": n_classes,
                "random_state": RANDOM_SEED,
                "eval_metric": "mlogloss",
            }
        )

        final_model = xgb.XGBClassifier(**best_params)
        cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=RANDOM_SEED)
        cv_scores = cross_val_score(final_model, X_train, y_train, cv=cv, scoring="accuracy", n_jobs=-1)

        final_model.fit(X_train, y_train)

        logger.info(
            "Training complete: best_cv_accuracy=%.4f (+/- %.4f) trials=%d",
            cv_scores.mean(),
            cv_scores.std(),
            n_trials,
        )

        return TrainingResult(
            model=final_model,
            best_params=study.best_params,
            cv_mean_accuracy=float(cv_scores.mean()),
            cv_std_accuracy=float(cv_scores.std()),
        )
