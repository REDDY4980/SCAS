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


def test_fallback_computes_real_calculated_dosage_per_hectare():
    """Rice has no sourced KB dose, but with the real Karnataka sample's
    deficiency values the fallback must now compute a real
    nutrient-replacement dosage (deficit / product nutrient %) instead
    of withholding a number — and must clearly label it as a calculated
    estimate, not a sourced package-of-practice figure."""
    deficiency = DeficiencyDetector().analyze(KARNATAKA_SHC_EXPECTED)
    selector = FertilizerSelector()
    items = selector.select("rice", deficiency)  # not in KB, no area given

    assert len(items) == 2  # nitrogen and phosphorus are "low" for this sample; potassium isn't
    n_item = next(i for i in items if "nitrogen" in i.target_nutrients)
    p_item = next(i for i in items if "phosphorus" in i.target_nutrients)

    # N deficit = 280 - 200.6 = 79.4 kg/ha; Urea is 46% N -> 79.4/0.46
    assert "172.6 kg/ha" in n_item.dosage
    assert "Urea" in n_item.fertilizer_name
    # P deficit = 10 - 4.19 = 5.81 kg/ha; DAP is 46% P2O5 -> 5.81/0.46
    assert "12.6 kg/ha" in p_item.dosage
    assert "DAP" in p_item.fertilizer_name

    for item in items:
        assert "calculated" in item.dosage.lower()
        assert "not a sourced dose" in item.dosage.lower()
        assert "calculated" in item.precautions.lower()


def test_fallback_dosage_scales_with_real_farm_area():
    """The same per-hectare rate must scale to a real total when the
    farm's registered area is supplied, and scale further with a
    different area — proving it isn't a fixed/fabricated number."""
    deficiency = DeficiencyDetector().analyze(KARNATAKA_SHC_EXPECTED)
    selector = FertilizerSelector()

    small_farm = selector.select("rice", deficiency, area_acres=2.16)
    large_farm = selector.select("rice", deficiency, area_acres=5.0)

    small_n = next(i for i in small_farm if "nitrogen" in i.target_nutrients)
    large_n = next(i for i in large_farm if "nitrogen" in i.target_nutrients)

    # 2.16 acres = 0.874152 ha; 172.6087 kg/ha x 0.874152 ha ~= 150.9 kg
    assert "150.9 kg" in small_n.dosage
    assert "0.87 ha" in small_n.dosage
    # 5.0 acres = 2.0235 ha; 172.6087 kg/ha x 2.0235 ha ~= 349.3 kg
    assert "349.3 kg" in large_n.dosage
    assert "2.02 ha" in large_n.dosage
    # Same per-hectare rate underlies both — only the total differs.
    assert "172.6 kg/ha" in small_n.dosage
    assert "172.6 kg/ha" in large_n.dosage


def test_fallback_no_area_omits_total_but_still_gives_rate():
    deficiency = DeficiencyDetector().analyze(KARNATAKA_SHC_EXPECTED)
    selector = FertilizerSelector()
    items = selector.select("rice", deficiency)  # area_acres defaults to None

    n_item = next(i for i in items if "nitrogen" in i.target_nutrients)
    assert "172.6 kg/ha" in n_item.dosage
    assert "total for this farm" not in n_item.dosage
    assert "Register this farm's area" in n_item.dosage


def test_fallback_sufficient_nutrient_never_gets_a_dosage():
    """Potassium is 122.8 kg/ha in the real sample, above the 120 kg/ha
    'low' threshold — it must never appear as a deficient item at all,
    calculated or otherwise."""
    deficiency = DeficiencyDetector().analyze(KARNATAKA_SHC_EXPECTED)
    selector = FertilizerSelector()
    items = selector.select("rice", deficiency)
    assert not any("potassium" in i.target_nutrients for i in items)


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
