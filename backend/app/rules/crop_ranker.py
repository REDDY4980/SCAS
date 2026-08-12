"""
Crop Ranker.

AIB v1.0 Vol 10.8 Crop Ranking Strategy:
    1. Sort by adjusted confidence.
    2. Remove invalid crops.
    3. Return Top-5 recommendations.
    4. Mark highest ranked crop as primary recommendation.

"Remove invalid crops" (step 2) refers to hard-rejected crops. The
current rule set's `unknown_rule_policy` explicitly forbids hard
rejection except for authoritative, explicitly-validated constraints
(Vol 10 Vol design philosophy, RULE_ENGINE_SPEC.md) — none of the
loaded rules currently define a hard-reject condition, so this step is
a structural no-op today and will start removing crops the moment a
rule with `hard_reject_policy` scope is added, without any ranking code
changes.
"""

from __future__ import annotations

from app.rules.confidence_engine import ScoredCrop


def rank(scored_crops: list[ScoredCrop]) -> list[ScoredCrop]:
    ranked = sorted(scored_crops, key=lambda sc: sc.adjusted_confidence, reverse=True)
    return ranked[:5]
