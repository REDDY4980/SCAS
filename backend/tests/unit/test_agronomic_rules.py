"""
Agronomic rule engine tests — exercised against the real Requirement 3
rule set (agronomic_rules_v1.json) and the real Karnataka SHC values
used throughout Phase 4/6 testing.
"""

from app.rules.agronomic_rules import AgronomicRuleEngine
from tests.fixtures.real_shc_samples import KARNATAKA_SHC_EXPECTED


def _engine() -> AgronomicRuleEngine:
    return AgronomicRuleEngine()


def test_rice_in_suitable_ph_range_gets_bonus():
    engine = _engine()
    result = engine.evaluate("rice", {"ph": 6.0})
    assert any(n.rule_id == "AGR-RICE-PH" and n.effect == "bonus" for n in result.notes)
    assert result.score_adjustment > 0


def test_real_karnataka_ph_770_is_outside_rice_range_and_penalized():
    # The real Karnataka SHC sample has pH 7.70, above rice's 5.5-6.5
    # preferred range (Vol 10 example) — must be a soft penalty, never
    # a hard rejection.
    engine = _engine()
    result = engine.evaluate("rice", {"ph": KARNATAKA_SHC_EXPECTED["ph"]})
    assert any(n.rule_id == "AGR-RICE-PH-OUT" for n in result.notes)
    assert result.score_adjustment < 0
    # Never a hard reject: the crop is still scoreable, just penalized.
    assert result.score_adjustment > -1.0


def test_non_rice_crop_gets_unknown_rule_penalty_not_rejection():
    engine = _engine()
    result = engine.evaluate("banana", {"ph": 6.5})
    assert any(n.rule_id == "AGR-UNKNOWN-CROP-RULE" for n in result.notes)
    # Small penalty only, never a hard stop.
    assert -0.05 < result.score_adjustment <= 0


def test_real_karnataka_soil_status_flags_low_n_p_oc():
    engine = _engine()
    result = engine.evaluate("rice", KARNATAKA_SHC_EXPECTED)
    assert result.soil_status_flags["low_nitrogen"] is True   # 200.6 < 280
    assert result.soil_status_flags["low_phosphorus"] is True  # 4.19 < 10
    assert result.soil_status_flags["low_organic_carbon"] is True  # 0.35 < 0.5
    assert result.soil_status_flags["low_potassium"] is False  # 122.8 >= 120


def test_missing_soil_values_do_not_crash_or_flag():
    engine = _engine()
    result = engine.evaluate("rice", {})
    assert result.soil_status_flags == {}


def test_karnataka_black_soil_triggers_informational_note():
    engine = _engine()
    result = engine.evaluate("rice", {"ph": 6.0}, farm_state="Karnataka", farm_soil_type="Black Soil")
    assert any(n.rule_id == "AGR-KA-RED-BLACK-NPK-ZN" for n in result.notes)


def test_non_karnataka_state_does_not_trigger_regional_notes():
    engine = _engine()
    result = engine.evaluate("rice", {"ph": 6.0}, farm_state="Punjab", farm_soil_type="Black Soil")
    assert not any(n.rule_id == "AGR-KA-RED-BLACK-NPK-ZN" for n in result.notes)


def test_zone5_crop_without_zone_data_reports_insufficient_context():
    engine = _engine()
    result = engine.evaluate("ragi", {"ph": 6.5}, farm_state="Karnataka", farm_soil_type=None)
    assert any(n.rule_id == "AGR-KA-ZONE-5-CONTEXT-UNAVAILABLE" for n in result.notes)
    # Explicitly zero score impact — never fabricate a bonus from partial context.
    zone_note = next(n for n in result.notes if n.rule_id == "AGR-KA-ZONE-5-CONTEXT-UNAVAILABLE")
    assert zone_note.magnitude == 0.0
