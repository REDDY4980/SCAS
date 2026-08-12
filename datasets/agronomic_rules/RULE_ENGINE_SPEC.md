# SCAS Requirement 3 — Agronomic Rule Engine Specification

## Professional design decision

The SCAS rule engine must **not become a collection of invented if/else thresholds**.

The correct architecture is an evidence-backed, context-aware validation/reranking layer:

XGBoost prediction
→ agronomic evidence lookup
→ regional/context checks
→ confidence adjustment
→ top-5 ranking
→ explanation

The Government of India Soil Health Card system explicitly frames fertilizer advice around the measured soil status of a holding and crop-wise recommendations. The UAS Bengaluru Soil Test Crop Response programme exists specifically to calibrate fertilizer recommendations from soil-test values and targeted yield. Therefore, SCAS should prefer matching STCR/state/zone rules over generic blanket rules.

## Rule categories

1. `soil_status`
   - Classifies N/P/K/OC status using the cited SHC reference classes.
2. `crop_suitability`
   - Uses a crop-specific source where a preferred range is explicitly documented.
3. `regional_context`
   - Uses state/agro-climatic-zone evidence to adjust ranking.
4. `regional_soil_context`
   - Flags known regional nutrient constraints.
5. `decision_priority`
   - Controls precedence among STCR, state package-of-practice and generic fallback rules.

## Critical safety/quality rule

A preferred range is **not automatically a hard exclusion**.

Example: if a source says rice grows well at pH 5.5–6.5, pH 7.0 should lower confidence / trigger validation, not automatically declare rice impossible.

Hard rejection is allowed only where the evidence explicitly supports a limiting condition and the SCAS input contains the required context.

## Soil nutrient classes

The Government of India SHC manual gives the following reference classes:

- Organic carbon: <0.5% low; 0.5–0.75% medium; >0.75% high.
- Available N: <280 kg/ha low; 280–560 medium; >560 high.
- Available P: <10 kg/ha low; 10–25 medium; >25–50 high; >50 very high.
- Available K: <120 kg/ha low; 120–280 medium; >280–600 high; >600 very high.

These are classification rules, not fertilizer-dose equations.

## Karnataka context

UAS Bengaluru's Soil Test Crop Response programme reports STCR targeted-yield fertilizer prescription equations for Karnataka zones 3–7. The SCAS fertilizer service should therefore support:

`state + agroclimatic_zone + crop + soil_test + target_yield`

as a lookup key.

UAS Bengaluru's ARS Chintamani is in Karnataka Eastern Dry Zone (Zone V) and conducts location-specific research on ragi, groundnut, pigeon pea, cowpea, horse gram and other dryland crops.

ICAR's Karnataka profile identifies N, P and Zn deficiency as important constraints in red and black soils.

## Current scope

This v1 rule set deliberately contains only rules that can be traced to identified authoritative sources. It is NOT acceptable to fill the remaining 22 crops with guessed thresholds.

The rule schema is designed so additional rules can be added without architecture changes.

## Required rule record

Every rule must contain:

- id
- type
- condition
- action
- severity
- confidence
- source
- source_url
- scope
- explanation

## Recommended implementation behavior

- Missing pH: do not reject.
- Missing N/P/K: do not reject.
- Unknown crop/region rule: reduce confidence, don't reject.
- Matching STCR equation: highest priority.
- Matching state/zone package: next priority.
- Generic fallback: lowest priority and clearly labeled.
- Every final recommendation must explain which rules affected its score.

## Evidence hierarchy

1. Government of India / Soil Health Card
2. ICAR institutes / KVKs
3. State Agricultural Universities (e.g. UAS Bengaluru)
4. Published agricultural research / package-of-practice documents
5. General public sources — only as a last-resort contextual reference, never as the sole basis for a hard agronomic constraint.

## Sources

Government of India Soil Health Card FAQ:
https://soilhealth.dac.gov.in/files/FAQ_Final_English.pdf

Government of India Soil Sampling & Testing Manual:
https://soilhealth.dac.gov.in/files/Manual/140723_ManualClass11_12.pdf

Soil Health Card portal support:
https://support.soilhealth.dac.gov.in/kb/faq.php?id=39

UAS Bengaluru Soil Test Crop Response:
https://www.uasbangalore.edu.in/en/soil-test-crop-response/

UAS Bengaluru ARS Chintamani:
https://www.uasbangalore.edu.in/en/ars-chintamani/

ICAR Karnataka profile:
https://www.icar.gov.in/en/node/17269

TNAU Paddy cultivation practices:
https://agritech.tnau.ac.in/expert_system/paddy/cultivationpractices1.html

ICAR balanced nutrient-management guidance:
https://www.icar.gov.in/en/farmers-sensitized-soil-test-based-balanced-nutrient-management-icar-ccari
