"""Deficiency detector tests — calibrated against real Karnataka/Tasar SHC data."""

from app.rules.deficiency_detector import DeficiencyDetector
from tests.fixtures.real_shc_samples import KARNATAKA_SHC_EXPECTED, TASAR_SHC_SAMPLE_1_EXPECTED


def test_karnataka_real_values_classify_correctly():
    detector = DeficiencyDetector()
    result = detector.analyze(KARNATAKA_SHC_EXPECTED)
    assert result.classifications["nitrogen"] == "low"       # 200.6 < 280
    assert result.classifications["phosphorus"] == "low"     # 4.19 < 10
    assert result.classifications["potassium"] == "medium"   # 122.8 in [120,280)
    assert result.classifications["organic_carbon"] == "low"  # 0.35 < 0.5
    assert set(result.deficient_macro_nutrients) == {"nitrogen", "phosphorus", "organic_carbon"}


def test_tasar_sample_classifies_correctly():
    detector = DeficiencyDetector()
    result = detector.analyze(TASAR_SHC_SAMPLE_1_EXPECTED)
    assert result.classifications["nitrogen"] == "low"        # 111.7 < 280
    assert result.classifications["phosphorus"] == "low"      # 9.30 < 10
    assert result.classifications["potassium"] == "medium"    # 180.3 in [120,280)
    assert result.classifications["organic_carbon"] == "medium"  # 0.57 in [0.5,0.75)


def test_micronutrients_are_not_classified_only_surfaced():
    detector = DeficiencyDetector()
    result = detector.analyze(KARNATAKA_SHC_EXPECTED)
    assert "zinc" not in result.classifications
    assert "boron" not in result.classifications
    assert result.unclassified_values["zinc"] == KARNATAKA_SHC_EXPECTED["zinc"]


def test_missing_values_are_skipped_not_fabricated():
    detector = DeficiencyDetector()
    result = detector.analyze({"nitrogen": 600.0})  # everything else missing; 600 > 560 -> high
    assert "phosphorus" not in result.classifications
    assert "potassium" not in result.classifications
    assert result.classifications["nitrogen"] == "high"


def test_high_nutrients_not_flagged_deficient():
    detector = DeficiencyDetector()
    result = detector.analyze(
        {"nitrogen": 600.0, "phosphorus": 60.0, "potassium": 700.0, "organic_carbon": 1.0}
    )
    assert result.deficient_macro_nutrients == []
