"""Validation tests — AIB v1.0 Vol 7.8 range and confidence rules."""

from app.ocr.validation import validate_soil_values
from tests.fixtures.real_shc_samples import KARNATAKA_SHC_EXPECTED, TASAR_SHC_SAMPLE_4_EXPECTED


def test_real_karnataka_report_passes_with_high_confidence():
    result = validate_soil_values(KARNATAKA_SHC_EXPECTED, ocr_confidence=0.95)
    assert result.is_valid is True
    assert result.status == "success"
    assert result.missing_core_fields == []
    assert result.out_of_range_fields == []


def test_low_confidence_triggers_needs_review_even_with_valid_values():
    result = validate_soil_values(KARNATAKA_SHC_EXPECTED, ocr_confidence=0.60)
    assert result.is_valid is False
    assert result.status == "needs_review"
    assert any("confidence" in w.lower() for w in result.warnings)


def test_missing_core_field_triggers_needs_review():
    values = dict(KARNATAKA_SHC_EXPECTED)
    del values["nitrogen"]
    result = validate_soil_values(values, ocr_confidence=0.95)
    assert result.is_valid is False
    assert result.status == "needs_review"
    assert "nitrogen" in result.missing_core_fields


def test_ph_out_of_physical_range_fails_hard():
    values = dict(KARNATAKA_SHC_EXPECTED)
    values["ph"] = 17.0  # impossible — OCR almost certainly misread a digit
    result = validate_soil_values(values, ocr_confidence=0.95)
    assert result.is_valid is False
    assert result.status == "failed"
    assert "ph" in result.out_of_range_fields


def test_negative_nitrogen_fails_hard():
    values = dict(KARNATAKA_SHC_EXPECTED)
    values["nitrogen"] = -5.0
    result = validate_soil_values(values, ocr_confidence=0.95)
    assert result.is_valid is False
    assert result.status == "failed"
    assert "nitrogen" in result.out_of_range_fields


def test_missing_micronutrients_warns_but_does_not_block():
    values = {
        "ph": 6.5,
        "ec": 0.1,
        "organic_carbon": 0.6,
        "nitrogen": 200.0,
        "phosphorus": 20.0,
        "potassium": 150.0,
        # no micronutrients at all
    }
    result = validate_soil_values(values, ocr_confidence=0.95)
    assert result.is_valid is True
    assert result.status == "success"
    assert len(result.warnings) == 1
    assert "micronutrient" in result.warnings[0].lower()


def test_edge_case_very_low_copper_still_valid():
    # Real report TASAR_SHC_SAMPLE_4 has Cu = 0.09 ppm (deficient but
    # physically valid — must not be rejected as "out of range").
    result = validate_soil_values(TASAR_SHC_SAMPLE_4_EXPECTED, ocr_confidence=0.9)
    assert result.is_valid is True
    assert "copper" not in result.out_of_range_fields
