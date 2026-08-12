"""
Field parser tests — calibrated against real, redacted Soil Health Card
data (Requirement 4 / AIB Vol 7.14 test scenarios).
"""

import pytest

from app.ocr.field_parser import parse_lines
from tests.fixtures.real_shc_samples import (
    KARNATAKA_SHC_EXPECTED,
    KARNATAKA_SHC_LINES,
    TASAR_SHC_SAMPLE_1_EXPECTED,
    TASAR_SHC_SAMPLE_1_LINES,
    TASAR_SHC_SAMPLE_4_EXPECTED,
    TASAR_SHC_SAMPLE_4_LINES,
)


@pytest.mark.parametrize(
    "lines,expected",
    [
        (KARNATAKA_SHC_LINES, KARNATAKA_SHC_EXPECTED),
        (TASAR_SHC_SAMPLE_1_LINES, TASAR_SHC_SAMPLE_1_EXPECTED),
        (TASAR_SHC_SAMPLE_4_LINES, TASAR_SHC_SAMPLE_4_EXPECTED),
    ],
    ids=["karnataka_shc_2017", "tasar_shc_sample_1", "tasar_shc_sample_4"],
)
def test_parses_all_fields_from_real_shc(lines, expected):
    result = parse_lines(lines)
    for field_name, expected_value in expected.items():
        assert field_name in result.values, f"Missing field: {field_name}"
        assert result.values[field_name] == pytest.approx(expected_value), (
            f"{field_name}: got {result.values[field_name]}, expected {expected_value}"
        )


def test_karnataka_metadata_extraction():
    result = parse_lines(KARNATAKA_SHC_LINES)
    assert result.metadata.get("soil_type") == "Black Soil"
    assert result.metadata.get("sample_date") == "10/09/2017"


def test_does_not_confuse_row_number_with_value():
    # Row-number prefixes ("4 Available Nitrogen...") must not be picked
    # up as the field value.
    result = parse_lines(["4 Available Nitrogen (N) 200.6 kg/ha Low 280-560 kg/ha"])
    assert result.values["nitrogen"] == pytest.approx(200.6)


def test_ph_not_confused_with_phosphorus():
    result = parse_lines(
        [
            "1 pH 7.70 Moderately alkaline",
            "5 Available Phosphorus (P) 4.19 kg/ha Very Low",
        ]
    )
    assert result.values["ph"] == pytest.approx(7.70)
    assert result.values["phosphorus"] == pytest.approx(4.19)


def test_unrecognized_lines_are_logged_not_erroring():
    result = parse_lines(
        [
            "Department of Agriculture, Cooperation and Farmers Welfare",
            "Kisan toll free number: 1800-180-1551",
            "1 pH 6.50 Neutral",
        ]
    )
    assert result.values["ph"] == pytest.approx(6.50)
    assert len(result.unmatched_lines) == 2


def test_empty_input_produces_empty_report():
    result = parse_lines([])
    assert result.values == {}
    assert result.metadata == {}


def test_first_match_per_field_wins_ignores_reference_range_numbers():
    # The reference-range column ("280-560 kg/ha") appears *after* the
    # real value in the same line and must not overwrite it.
    result = parse_lines(["4 Available Nitrogen (N) 200.6 kg/ha Low 280-560 kg/ha"])
    assert result.values["nitrogen"] == pytest.approx(200.6)
