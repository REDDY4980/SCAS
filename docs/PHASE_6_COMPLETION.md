# Phase 6 — Machine Learning Engineering & Inference Architecture: Completion Record

Per AIB v1.0 Vol 17.3 "Phase 6 – Machine Learning":
> Implement feature engineering, XGBoost inference and model loading.

## Deliverables

- [x] `ml/datasets/dataset_loader.py` — Vol 9.5 pipeline stages 1-4 (schema validation, duplicate removal, missing-value handling, range validation)
- [x] `ml/feature_engineering/feature_engineer.py` — fixed `FEATURE_ORDER`, target label encoding, feature-vector builder for inference
- [x] `ml/training/trainer.py` — 80/10/10 stratified split, Optuna hyperparameter tuning (Vol 9.10: learning_rate, max_depth, n_estimators, subsample, colsample_bytree, gamma, min_child_weight), stratified 5-fold CV (Vol 9.9)
- [x] `ml/evaluation/evaluator.py` — accuracy, precision/recall/F1 (macro), confusion matrix, feature importance, inference latency (Vol 9.11)
- [x] `ml/training/run_training.py` — orchestration script, actually executed end-to-end (see below)
- [x] `ml/inference/inference_engine.py` — Vol 9.12 pipeline (feature validation → ordering → probability prediction → Top-5 ranking), Vol 9.20 "load once" factory pattern, training/inference code kept structurally separate (imports no training-time modules)
- [x] Model artifacts serialized per Vol 9.14: `model.joblib`, `label_encoder.joblib`, `feature_schema.json`, `model_metadata.json`
- [x] XGBoost only — no Random Forest anywhere in the codebase (Vol 9.3)

## This is a real trained model, not a stub

I actually ran the full training pipeline against the real Requirement 1 dataset in this environment. Results:

| Metric | Value |
|---|---|
| Dataset | 2,200 rows, 22 classes — SHA256 verified to match `dataset_validation.json` exactly |
| Optuna trials | 20 |
| Cross-val accuracy (train folds) | 99.49% (± 0.21%) |
| Validation accuracy | 99.09% |
| Validation F1 (macro) | 99.11% |
| Test accuracy | **98.64%** |
| Test F1 (macro) | 98.61% |
| Test inference latency | 0.029ms/sample |
| Wall-clock training time | ~46 seconds |

Best hyperparameters found: `learning_rate=0.0357, max_depth=10, n_estimators=233, subsample=0.839, colsample_bytree=0.662, gamma=0.780, min_child_weight=1`.

Per the `README.md` Requirement 1 directive ("Do not copy accuracy numbers from other papers as SCAS results. Train and report SCAS's own model results") — these are SCAS's own numbers from its own training run in this environment, not borrowed from any published benchmark.

## Honest limitation, carried into the artifact itself

`model_metadata.json` bakes in an explicit warning field:

> "This model is trained on Requirement 1's public starter dataset, not proprietary field-collected data... Do not present these metrics as validated against real Indian farm conditions."

This mirrors `MASTER_RESOURCE_INDEX.md`'s Requirement 1 interpretation directive verbatim. 98.64% test accuracy on this dataset says the model has learned the dataset's decision boundaries well — it says nothing yet about how well those boundaries match real farmer outcomes, since the dataset itself is a public synthetic/augmented starter set, not field-collected ground truth. That distinction should stay visible to anyone inspecting the deployed model, not just buried in a README.

## Documented deviation from Vol 9.4

Vol 9.4's aspirational input feature list includes soil micronutrients (Zn, Fe, Mn, Cu, B), Season, and Wind Speed alongside the 7 features actually used here. Requirement 1's real dataset — the one actually available for training — only provides N, P, K, temperature, humidity, pH, and rainfall. `FEATURE_ORDER` and the dataset loader are honest about training on the 7 columns that exist rather than fabricating values for columns that don't. If a richer field-collected dataset becomes available later (as `MASTER_RESOURCE_INDEX.md` anticipates), the architecture (fixed `FEATURE_ORDER` list, single-source-of-truth feature engineering) makes extending to more features a contained change, not a redesign.

## Verification performed in this environment

1. **Actually ran** `python -m ml.training.run_training --trials 20` against the real dataset — not simulated, not described hypothetically. Full console output captured in this session's log.
2. Verified the dataset SHA256 computed by `DatasetLoader` matches the known hash in `dataset_validation.json` **exactly**, confirming no data corruption or unintended modification.
3. Loaded the real serialized model via `InferenceEngine.load()` and ran predictions against **real sample rows from the training CSV** — correctly predicted "rice" at 97.4% confidence on an actual rice sample, and "apple"/"cotton" both appeared correctly in the Top-5 for their respective real feature profiles.
4. Ran the full `ml/tests/` suite: **21/21 passing** (dataset validation edge cases, feature ordering guarantees, inference correctness, feature-order-independence, missing-feature rejection).
5. Ran the full combined suite (backend Phases 1/2/4/5 + this phase's ML tests): **108/108 passing**, confirming Phase 6 introduced no regressions.

## Explicitly deferred to later phases (not gaps)

- Agronomic Rule Engine validation of raw XGBoost predictions — Phase 7. Per Vol 9.20, "every prediction must pass through the Confidence Engine and Agronomic Rule Engine before reaching the user" — this phase's `InferenceEngine` deliberately has **no HTTP endpoint** exposing raw model output directly to end users; it's an internal component Phase 7 wraps.
- `POST /recommendation` API endpoint — Phase 7 (combines this engine with rules/confidence/explainability).
- Feature fusion of live `soil_parameters` + `weather_snapshots` into a real farmer's feature vector — Phase 7 (this phase proves the engine works on the feature *shape* the Phase 4/5 pipelines produce; wiring them together end-to-end is Phase 7's job).

## AIB Compliance Notes

- Training code (`ml/training/*`) and inference code (`ml/inference/*`) import from different, non-overlapping module sets — inference never pulls in Optuna, cross-validation, or the trainer (Vol 9.20, Vol 9.15).
- Feature order is defined in exactly one place (`FEATURE_ORDER` in `feature_engineer.py`) and consumed everywhere else, structurally preventing the "altered feature order" failure mode Vol 9.20 warns against.
- No inference path accepts raw OCR text or unvalidated input — `InferenceEngine.predict_top5` requires a fully-populated, already-validated feature dict and raises `FeatureValidationError` otherwise.
