"""
Layout reconstruction tests — AIB v1.0 Vol 7.3.

Includes a regression test for a real bug found during Phase 4
integration testing: lines lacking bounding-box data were being
transitively merged into a single giant row instead of staying as
independent rows.
"""

from app.ocr.engine import OCRLine, OCRPageResult
from app.ocr.layout import reconstruct_rows


def test_empty_result_returns_empty_rows():
    assert reconstruct_rows(OCRPageResult(lines=[])) == []


def test_lines_without_bounding_boxes_never_merge():
    lines = [OCRLine(text=f"line {i}", confidence=0.9) for i in range(20)]
    result = OCRPageResult(lines=lines)
    rows = reconstruct_rows(result)
    assert len(rows) == 20
    assert rows == [f"line {i}" for i in range(20)]


def test_lines_on_same_row_by_bounding_box_are_joined_left_to_right():
    lines = [
        OCRLine(text="World", confidence=0.9, bounding_box=[(100, 10), (150, 10), (150, 30), (100, 30)]),
        OCRLine(text="Hello", confidence=0.9, bounding_box=[(0, 12), (50, 12), (50, 28), (0, 28)]),
    ]
    result = OCRPageResult(lines=lines)
    rows = reconstruct_rows(result)
    assert rows == ["Hello World"]


def test_lines_on_different_rows_stay_separate():
    lines = [
        OCRLine(text="Row One", confidence=0.9, bounding_box=[(0, 10), (50, 10), (50, 30), (0, 30)]),
        OCRLine(text="Row Two", confidence=0.9, bounding_box=[(0, 100), (50, 100), (50, 120), (0, 120)]),
    ]
    result = OCRPageResult(lines=lines)
    rows = reconstruct_rows(result)
    assert rows == ["Row One", "Row Two"]
