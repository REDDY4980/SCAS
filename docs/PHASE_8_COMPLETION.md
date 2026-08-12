# Phase 8 — Fertilizer Recommendation Engine: Completion Record

Per AIB v1.0 Vol 17.3 "Phase 8 – Fertilizer Engine":
> Implement deficiency detection, knowledge base and dosage engine.

## Deliverables

- [x] `app/rules/deficiency_detector.py` — N/P/K/Organic Carbon classification using the same authoritative SHC national reference classes as the Phase 7 agronomic rule engine; micronutrients deliberately left unclassified (see below)
- [x] `app/rules/fertilizer_knowledge_base.py` — loads the real Requirement 2 KB, **exact-match-only** crop lookup (no fuzzy matching)
- [x] `app/rules/fertilizer_selector.py` — dual-path selector: sourced recommendation for KB-covered crops, honest fallback for uncovered crops (21 of 22 ML crops)
- [x] `app/repositories/fertilizer_repository.py`, `app/schemas/fertilizer.py`, `app/services/fertilizer_service.py` — persistence and orchestration, idempotent regeneration
- [x] `POST /fertilizer/{recommendation_id}`, `GET /fertilizer/{recommendation_id}` — Vol 11.11 integration with the Phase 7 recommendation

## The central design decision: never fabricate a dosage

The real fertilizer knowledge base covers exactly 6 crops (Ragi, Groundnut, Maize, Hybrid Paddy, Cowpea, Horse gram) with sourced kg/ha doses. The ML model (Phase 6) predicts across 22 crop labels. Only **one** — `maize` ↔ `Maize` — is a legitimate exact match.

I deliberately did **not** map the ML model's `rice` prediction onto the KB's `Hybrid Paddy` entry, even though they're related crops, because `Hybrid Paddy`'s dose is documented for a specific hybrid variety under specific conditions — presenting that number as if it applies to any XGBoost "rice" prediction would misrepresent sourced evidence as validated for something it was never validated for. This is exactly the failure mode `MASTER_RESOURCE_INDEX.md` warns against ("Never fabricate fertilizer dosage... Never treat a generic crop dataset as field-validated truth").

Instead, per Vol 11.12's own directive ("Unknown crop → fallback nutrient recommendation"), uncovered crops get a **nutrient-class** recommendation — "your soil is low in nitrogen; Urea is the standard source for that" — with an explicit, visible statement that no source-traceable dose exists for this crop yet and a soil-test-based (STCR) recommendation or local extension officer should be consulted before applying anything. Every fallback dosage field says this in plain language; it's not buried in a footnote.

## Micronutrient classification: another honest gap, not a silent one

Vol 11.5 asks for Low/Medium/High classification of all soil parameters including Zn, Fe, Mn, Cu, B. The only authoritative threshold table available in the project's resolved resources (`agronomic_rules_v1.json`'s `soil_health_card_nutrient_classes`) covers **only** organic carbon, N, P, and K — no generic micronutrient bands were supplied. Rather than inventing plausible-looking cutoffs, `DeficiencyDetector` classifies only the four macro parameters it has real thresholds for, and surfaces micronutrient values as raw numbers for the explanation layer to reference. This directly follows `MASTER_RESOURCE_INDEX.md`'s "Never silently fabricate missing agricultural thresholds" rule, applied here to a case the rule set's authors probably didn't anticipate but the same logic clearly covers.

## Verification performed in this environment

1. Unit-tested the deficiency detector against **both** real SHC samples (Karnataka: N/P/OC low, K medium; Tasar: N/P low, K/OC medium) — classifications matched the SHC's own published ratings for every parameter our threshold table covers.
2. Unit-tested the KB loader's exact-match safety property directly: `test_rice_does_not_fuzzy_match_hybrid_paddy` explicitly asserts `lookup_crop("rice")` returns `None`, not a Hybrid Paddy dose.
3. Unit-tested both selector paths against real Karnataka SHC deficiency data: the sourced path for `maize` returns exactly 150/75/40 kg/ha N/P₂O₅/K₂O — verified against the raw KB JSON — with the real UAS Bengaluru source string attached; the fallback path for `rice` (and other uncovered crops) never contains a bare "kg/ha" figure and always names STCR or a local extension officer.
4. Full end-to-end integration test through the real API: built a farm with genuine Karnataka SHC soil values (low N/P/OC), generated a real Phase 7 recommendation against the real trained model, then generated a fertilizer recommendation from it — confirmed the deficiency profile correctly reports "low" nitrogen/phosphorus, confirmed every fallback-path dosage string explicitly says "not available," and confirmed idempotent regeneration (POSTing twice doesn't duplicate rows).
5. Ran the full combined suite: **148/148 tests passing** (127 backend + 21 ML), zero regressions.

## Explicitly deferred to later phases (not gaps)

- History persistence surfacing past fertilizer recommendations in a farmer-friendly list — Phase 9 (the underlying `fertilizer_recommendations` table, Vol 5.3, is already correctly populated by this phase; Phase 9 just needs to query and format it).
- Expanding KB coverage to more crops via STCR/state package-of-practice sources — explicitly flagged in the KB's own `coverage_note` as future work, not something to rush with invented numbers now.

## AIB Compliance Notes

- No fertilizer recommendation is ever returned without a `reason` string (Vol 11.9, enforced structurally — both `_sourced_recommendation` and `_fallback_recommendation` always populate it).
- Fertilizer composition facts (Urea = 46% N, etc.) are treated as universal product-grade facts (safe to state without a crop context); dosage numbers are treated as crop/region-specific facts that require a real source (never safe to state without one). This distinction is the single organizing principle of the whole module.
- Knowledge base logic (`fertilizer_knowledge_base.py`) is fully separate from XGBoost inference (Vol 11.16: "Keep fertilizer logic independent from XGBoost") — the selector only ever receives a crop *name string* from the recommendation service, never a model object or feature vector.
