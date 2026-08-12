# Phase 7 — Hybrid Crop Recommendation Engine: Completion Record

Per AIB v1.0 Vol 17.3 "Phase 7 – Hybrid Recommendation":
> Implement rule engine, confidence engine, ranking and explainability.

## Deliverables

- [x] `app/rules/agronomic_rules.py` — evaluates the **real** Requirement 3 rule set (`agronomic_rules_v1.json`, 11 rules) against candidate crops; soil-status classification (N/P/K/OC), rice pH suitability, Karnataka soil-context flagging
- [x] `app/rules/confidence_engine.py` — Vol 10.7 confidence adjustment (model score + rule bonuses/penalties, clamped to [0,1])
- [x] `app/rules/crop_ranker.py` — Vol 10.8 re-ranking by adjusted confidence, Top-5, primary selection
- [x] `app/rules/explanation_engine.py` — Vol 10.9 human-readable explanations combining feature importance, soil/climate context, and rule notes
- [x] `app/ml/inference_engine.py` + `app/ml/registry.py` — backend-side model loader (Vol 9.20 "load once"), deliberately decoupled from the top-level training package (see Design Decisions below)
- [x] `app/services/recommendation_service.py` — full Vol 10.3 orchestration: farm → latest validated soil → latest weather → feature fusion → inference → rules → confidence → ranking → explanation → persistence
- [x] `POST /recommendation`, `GET /recommendation/{id}` — both Vol 14.2 endpoints, farm ownership enforced throughout

## The rule engine only claims what it can back up

This was the main design tension in this phase: the real `agronomic_rules_v1.json` only has **one** crop-specific `crop_suitability` rule (rice pH) out of 22 ML-supported crops, plus soil-status classification rules and two Karnataka-specific regional rules that need a `agroclimatic_zone` field the `farms` table doesn't have.

Rather than quietly fabricating thresholds for the other 21 crops or guessing at zone membership from state alone, the engine:
- Applies the rice pH rule only to rice, exactly as authored (bonus in-range, soft penalty out-of-range — **never** a hard rejection, matching the rule set's own `unknown_rule_policy`).
- Applies a small, clearly-labeled "unknown rule" transparency penalty (−0.01) to every other crop, with an explanation string saying exactly that: agronomic validation is limited for this crop, add a reviewed rule to improve calibration.
- Evaluates the Karnataka red/black soil rule using **substring matching** against real farm data — this caught a real bug (see below).
- For Karnataka Zone-5 crops (ragi, groundnut, etc.), explicitly reports "regional zone data not available" rather than approximating a match from `state` alone — a partial match dressed up as a full one would misrepresent the evidence behind the score.

## A real bug found and fixed

**Soil-type substring matching**: the Karnataka SHC red/black-soil rule initially required an *exact* match against `"red"` or `"black"`. Real data — including the actual Karnataka SHC sample used throughout this project — reports `"Soil Type: Black Soil"`, two words, not the bare `"black"` the rule condition names. The exact-match version would have silently never fired against any genuine farm record. Caught by a unit test using the real farm-context string, fixed with substring containment matching, verified passing.

## Verification performed in this environment

1. Unit-tested the rule engine against **real Karnataka SHC values** (pH 7.70, N 200.6, P 4.19, OC 0.35 — same values validated in Phase 4): confirmed pH 7.70 correctly triggers the rice out-of-range penalty (not a rejection), and N/P/OC correctly flag as low per the SHC national reference classes while K (122.8, just above the 120 threshold) correctly does not — this K discrepancy vs. the SHC's own farm-specific "Low" rating is expected and documented (national reference classes vs. crop/region-specific ratings are different things; STCR-based crop-specific thresholds are a documented future addition, not implemented here).
2. Unit-tested confidence adjustment (bonus/penalty application, clamping at 0 and 1) and ranking (descending sort, Top-5 cap) — 14/14 passing.
3. **Full end-to-end integration test against the real trained model**: created a farm with Karnataka context, entered real near-ideal-rice soil values via the correction endpoint, fetched weather through a faked-but-realistic provider, called `POST /recommendation` — the real XGBoost model correctly surfaced **rice in the Top-5** for genuinely rice-favorable conditions (pH 6.5, high N/P/K, high rainfall/humidity), with descending-sorted confidences and full explanations.
4. Verified persistence and retrieval (`GET /recommendation/{id}`) and cross-user ownership isolation (404, not 403, for non-owners).
5. Ran the full combined suite: **127/127 tests passing** (106 backend + 21 ML), confirming zero regressions across every prior phase.

## Design decision: why `app/ml/` duplicates `ml/inference/`

The top-level `ml/` package (Phase 6) is the training/research pipeline — it imports Optuna, scikit-learn's training utilities, and reads directly from `datasets/`. The Docker deployment (`docker-compose.yml`, already set up in Phase 1) only mounts a `scas_ml_artifacts` volume into the backend container at `/app/ml/artifacts` — the training *code* was never going to ship in the production image, only the serialized *artifacts*. So `app/ml/inference_engine.py` is a small, self-contained loader (joblib + numpy only) that doesn't import the top-level `ml` package at all, avoiding an import that would work in this dev sandbox (same filesystem) but silently break in the actual containerized deployment where `ml/training/*` isn't present. This is Vol 9.20's "separate training code from inference code" directive enforced at the deployment boundary, not just the module boundary.

## Explicitly deferred to later phases (not gaps)

- Fertilizer recommendations building on this crop recommendation — Phase 8 (this phase's `Recommendation` row, with its `id`, is exactly the Vol 11.4 "Primary recommended crop" input the fertilizer engine needs).
- STCR-based, zone-specific fertilizer/crop thresholds — flagged in `agronomic_rules_v1.json` itself as requiring the `farms` table to eventually capture `agroclimatic_zone`; out of scope for a schema change at this stage but the rule engine is structured so adding it later doesn't require touching the ranking/confidence/explanation code.
- Climate-specific agronomic rules (Vol 10.7 mentions "climate suitability" as a confidence input) — the current rule set has no climate-specific rules to evaluate; noted as a coverage gap, not silently ignored.

## AIB Compliance Notes

- Raw XGBoost probabilities are never returned directly to a client — every prediction passes through the rule engine and confidence engine before `RecommendationService.generate()` returns anything (Vol 9.20, Vol 10.15).
- Feature ordering is enforced by the single `FEATURE_ORDER`-equivalent list baked into `feature_schema.json` at training time and read back by `InferenceEngine.load()` — never hand-constructed per-request.
- Every recommendation includes an explanation; there is no code path that persists or returns a `Recommendation` without one (Vol 10.9, Vol 2.5 BR-04).
