"""Fertilizer selector tests — sourced path (maize) and fallback path (uncovered crops)."""

from app.rules.deficiency_detector import DeficiencyDetector
from app.rules.fertilizer_selector import FertilizerSelector
from tests.fixtures.real_shc_samples import KARNATAKA_SHC_EXPECTED


def test_sourced_recommendation_matches_real_kb_values_exactly():
    deficiency = DeficiencyDetector().analyze(KARNATAKA_SHC_EXPECTED)
    selector = FertilizerSelector()
    items = selector.select("maize", deficiency)

    assert len(items) == 3  # N, P2O5, K2O all > 0 for maize in the real KB
    n_item = next(i for i in items if "nitrogen" in i.target_nutrients)
    assert "150 kg/ha" in n_item.dosage
    assert "University of Agricultural Sciences" in n_item.source


def test_fallback_never_fabricates_a_dosage_number():
    deficiency = DeficiencyDetector().analyze(KARNATAKA_SHC_EXPECTED)
    selector = FertilizerSelector()
    items = selector.select("rice", deficiency)  # not in KB

    assert len(items) > 0
    for item in items:
        assert "kg/ha" not in item.dosage  # never a fabricated numeric dose
        assert "not available" in item.dosage.lower()
        assert "STCR" in item.dosage or "extension" in item.dosage.lower()


def test_fallback_addresses_every_detected_deficiency():
    deficiency = DeficiencyDetector().analyze(KARNATAKA_SHC_EXPECTED)  # low N, P, OC
    selector = FertilizerSelector()
    items = selector.select("banana", deficiency)

    targeted_nutrients = {n for item in items for n in item.target_nutrients}
    assert "nitrogen" in targeted_nutrients
    assert "phosphorus" in targeted_nutrients


def test_no_deficiency_no_correction_needed():
    healthy_soil = {"nitrogen": 600.0, "phosphorus": 60.0, "potassium": 700.0, "organic_carbon": 1.0}
    deficiency = DeficiencyDetector().analyze(healthy_soil)
    selector = FertilizerSelector()
    items = selector.select("rice", deficiency)

    assert len(items) == 1
    assert items[0].fertilizer_name == "None required"
