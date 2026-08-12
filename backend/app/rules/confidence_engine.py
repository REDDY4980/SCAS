"""
Confidence Engine.

AIB v1.0 Vol 10.7:
    "Initial confidence originates from XGBoost. Confidence may be
    adjusted using: Climate suitability, Soil suitability, Rule
    penalties, Rule bonuses. Final score used for ranking."

Climate suitability is folded into the rule engine's soil/crop context
evaluation (Vol 10 doesn't specify a separate climate rule set beyond
what Requirement 3 supplies, and the current agronomic_rules_v1.json has
no climate-specific rules yet — documented as a known coverage gap, same
as the Karnataka Zone-5 regional rules).
"""

from __future__ import annotations

from dataclasses import dataclass

from app.rules.agronomic_rules import RuleEvaluation


@dataclass
class ScoredCrop:
    crop: str
    model_confidence: float
    adjusted_confidence: float
    rule_evaluation: RuleEvaluation


class ConfidenceEngine:
    """Vol 10.16 suggested module: confidence/confidence_engine.py."""

    def adjust(self, crop: str, model_confidence: float, rule_evaluation: RuleEvaluation) -> ScoredCrop:
        adjusted = model_confidence + rule_evaluation.score_adjustment
        # Confidence is a probability-like score; keep it in a sane
        # [0, 1] range after rule adjustments rather than letting
        # cumulative penalties push it negative.
        adjusted = max(0.0, min(1.0, adjusted))
        return ScoredCrop(
            crop=crop,
            model_confidence=model_confidence,
            adjusted_confidence=adjusted,
            rule_evaluation=rule_evaluation,
        )
