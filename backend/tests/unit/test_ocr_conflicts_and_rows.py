"""
Regression tests for two false-acceptance bugs found by running the REAL
OCR engine on the calibration documents (docs/OCR_MEMORY_REPORT.md):

1. A textbook page mentioning "Zinc sulphate (15 -)" before the results
   table made zinc=15.0 (true 0.27) and the report was auto-accepted.
2. A neighbouring table with a different row grid chained two result rows
   ("Sulphur ... Zinc ... 5.15 0.18"), pairing zinc with sulphur's value.
"""

from app.ocr.engine import OCRLine, OCRPageResult
from app.ocr.field_parser import parse_lines
from app.ocr.layout import reconstruct_rows
from app.ocr.validation import validate_soil_values
from tests.fixtures.real_shc_samples import KARNATAKA_SHC_EXPECTED, KARNATAKA_SHC_LINES

_TEXTBOOK_LINES = [
    "1 Zinc (Zn) Zinc sulphate (15 -) 0.5% Zinc sulphate +0.25% lim",
    "Iron (Fe) Ferrous sulphate 1% Ferrous sulphate (Spray th",
]


def _box(x, y, w=60, h=24):
    return [(x, y - h / 2), (x + w, y - h / 2), (x + w, y + h / 2), (x, y + h / 2)]


def test_first_value_still_wins_but_conflicts_are_recorded():
    parsed = parse_lines(_TEXTBOOK_LINES + KARNATAKA_SHC_LINES)
    assert parsed.values["zinc"] == 15.0  # unchanged first-match rule
    assert parsed.conflicts["zinc"] == [15.0, 0.27]
    assert parsed.conflicts["iron"] == [1.0, 0.71]


def test_identical_repeated_values_are_not_conflicts():
    parsed = parse_lines(KARNATAKA_SHC_LINES + ["Available Zinc (Zn) 0.27 ppm"])
    assert "zinc" not in parsed.conflicts


def test_clean_report_has_no_conflicts():
    assert parse_lines(KARNATAKA_SHC_LINES).conflicts == {}


def test_conflicting_values_are_never_auto_accepted():
    parsed = parse_lines(_TEXTBOOK_LINES + KARNATAKA_SHC_LINES)
    values = {k: v for k, v in parsed.values.items() if k != "sulphur"}
    result = validate_soil_values(values, 0.99, conflicting_values=parsed.conflicts)
    assert result.status == "needs_review"
    assert any("zinc: 15, 0.27" in w for w in result.warnings)


def test_validation_without_conflicts_is_unchanged():
    values = {k: v for k, v in KARNATAKA_SHC_EXPECTED.items() if k != "sulphur"}
    assert validate_soil_values(values, 0.95, conflicting_values={}).status == "success"
    assert validate_soil_values(values, 0.95).status == "success"


def test_conflicts_on_out_of_range_report_still_fail():
    result = validate_soil_values({"ph": 17.0, "zinc": 1.0}, 0.99, conflicting_values={"zinc": [1.0, 2.0]})
    assert result.status == "failed"


def test_offset_neighbour_table_does_not_chain_two_result_rows():
    """Real geometry from Tasar SHC card 1 (y centres in px)."""
    lines = [
        OCRLine("Available Sulphur (S)", 0.97, _box(51, 1001.5, 200)),
        OCRLine("5.15", 0.97, _box(326, 1002.0)),
        OCRLine("25", 0.97, _box(660, 1015.0)),  # fertilizer table, offset grid
        OCRLine("20", 0.97, _box(981, 1016.0)),
        OCRLine("Required", 0.97, _box(732, 1028.0)),
        OCRLine("Available Zinc(Zn)", 0.97, _box(51, 1029.5, 200)),
        OCRLine("0.18", 0.97, _box(326, 1030.0)),
    ]
    rows = reconstruct_rows(OCRPageResult(lines))
    sulphur_row = next(r for r in rows if "Sulphur" in r)
    zinc_row = next(r for r in rows if "Zinc" in r)
    assert sulphur_row != zinc_row
    parsed = parse_lines(rows)
    assert parsed.values["sulphur"] == 5.15
    assert parsed.values["zinc"] == 0.18
