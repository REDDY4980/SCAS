# SCAS — Master AI Developer Resource Index

## Purpose

This ZIP is the consolidated resource package for implementing SCAS (Smart Crop Advisory System) according to AIB v1.0, Volumes 1–19 and the supplied Claude kickoff package.

The AI developer must treat the original AIB specification as the architectural source of truth and use the resource folders below as the approved external/domain inputs.

## Requirements status

| Requirement | Status | Contents |
|---|---|---|
| 1. Crop recommendation training dataset | RESOLVED | Raw 2,200-row, 22-class dataset + validation metadata |
| 2. Fertilizer knowledge base | RESOLVED | Source-traceable starter catalog + crop references |
| 3. Agronomic rule set | RESOLVED | Source-traceable starter rules + evidence hierarchy |
| 4. Real farmer soil reports for OCR | RESOLVED | Redacted filled Indian reports + OCR calibration notes |

## Critical interpretation

### Requirement 1
The public crop dataset is a **starter training dataset**, not proprietary field data. Do not describe it as farmer-collected ground truth.

### Requirement 2
The fertilizer knowledge base is source-traceable but intentionally conservative. Do not invent doses for uncovered crops. Prefer soil-test/STCR/state-specific recommendations.

### Requirement 3
Agronomic rules are evidence-backed starter rules. A preferred range should normally reduce suitability or confidence rather than trigger an automatic hard rejection. Hard rejection requires authoritative evidence.

### Requirement 4
The supplied OCR documents are real filled farmer-specific Indian soil reports reproduced by government/institutional sources, with identifying information redacted. They are OCR calibration/input-format resources, not ML training labels.

## Required AI behavior

1. Never silently fabricate missing agricultural thresholds.
2. Never fabricate fertilizer dosage.
3. Never treat a generic crop dataset as field-validated truth.
4. Never bypass OCR validation before ML inference.
5. Never put secrets in source control.
6. Preserve source/provenance metadata for domain rules.
7. Keep all datasets/rules/configuration replaceable without changing API architecture.
8. Generate tests alongside each module.
9. Follow the phase order in the AIB exactly.
10. Do not claim a phase is complete until its acceptance criteria and tests pass.

## Phase dependency mapping

- Phase 1–3: no domain credentials required.
- Phase 4: Requirement 4 is required for OCR calibration.
- Phase 5: Open-Meteo primary; OpenWeatherMap fallback key required.
- Phase 6: Requirement 1 is required for XGBoost training.
- Phase 7: Requirement 3 is required.
- Phase 8: Requirement 2 is required.
- Phase 9: persistence/history.
- Phase 10: testing/deployment; cloud credentials only if cloud deployment is selected.

## Final E2E acceptance journey

Register → Login → Add Farm → Upload Soil Report → OCR → Validation → Weather → XGBoost → Agronomic Rule Engine → Top-5 recommendation → Fertilizer recommendation → Explanation → History.

Every recommendation must contain an explanation and evidence/provenance where applicable.

## Important source files

- `00_MASTER_INSTRUCTIONS/CLAUDE_AIB_v1_KICKOFF_PACKAGE.md`
- `01_CROP_RECOMMENDATION_DATASET/README.md`
- `02_FERTILIZER_KNOWLEDGE_BASE/README.md`
- `03_AGRONOMIC_RULES/RULE_ENGINE_SPEC.md`
- `04_SOIL_HEALTH_CARD_OCR_SAMPLES/OCR_CALIBRATION_NOTES.md`
- `05_CREDENTIALS_AND_DECISIONS/DECISIONS.md`
