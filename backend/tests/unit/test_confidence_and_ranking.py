"""Confidence Engine + Crop Ranker tests — AIB v1.0 Vol 10.7/10.8."""

import pytest

from app.rules.agronomic_rules import RuleEvaluation
from app.rules.confidence_engine import ConfidenceEngine
from app.rules.crop_ranker import rank


def _rule_eval(adjustment: float) -> RuleEvaluation:
    return RuleEvaluation(crop="test", score_adjustment=adjustment, notes=[], soil_status_flags={})


def test_confidence_adjustment_applies_bonus():
    engine = ConfidenceEngine()
    scored = engine.adjust("rice", 0.80, _rule_eval(0.05))
    assert scored.adjusted_confidence == pytest.approx(0.85)


def test_confidence_adjustment_applies_penalty():
    engine = ConfidenceEngine()
    scored = engine.adjust("rice", 0.80, _rule_eval(-0.10))
    assert abs(scored.adjusted_confidence - 0.70) < 1e-9


def test_confidence_never_goes_below_zero():
    engine = ConfidenceEngine()
    scored = engine.adjust("rice", 0.05, _rule_eval(-0.50))
    assert scored.adjusted_confidence == 0.0


def test_confidence_never_exceeds_one():
    engine = ConfidenceEngine()
    scored = engine.adjust("rice", 0.98, _rule_eval(0.50))
    assert scored.adjusted_confidence == 1.0


def test_ranker_sorts_descending_by_adjusted_confidence():
    engine = ConfidenceEngine()
    scored = [
        engine.adjust("banana", 0.60, _rule_eval(0.0)),
        engine.adjust("rice", 0.90, _rule_eval(-0.20)),  # adjusted -> 0.70
        engine.adjust("maize", 0.50, _rule_eval(0.0)),
    ]
    ranked = rank(scored)
    assert [sc.crop for sc in ranked] == ["rice", "banana", "maize"]


def test_ranker_caps_at_five():
    engine = ConfidenceEngine()
    scored = [engine.adjust(f"crop{i}", 0.1 * i, _rule_eval(0.0)) for i in range(10)]
    ranked = rank(scored)
    assert len(ranked) == 5
    # Highest scores retained.
    assert ranked[0].crop == "crop9"
