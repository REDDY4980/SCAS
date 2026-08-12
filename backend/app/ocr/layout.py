"""
Layout analysis.

AIB v1.0 Vol 7.3 pipeline position: PaddleOCR -> **Layout Analysis** ->
Field Extraction -> Regex Parsing.

PaddleOCR returns one detection per text fragment with its own bounding
box, not one detection per table row. This module groups fragments that
share a horizontal band (i.e. sit on the same table row) and joins them
left-to-right into a single reconstructed line, which is the input
contract `app.ocr.field_parser.parse_lines` expects.
"""

from __future__ import annotations

from app.ocr.engine import OCRPageResult


def _y_center(bounding_box: list[tuple[float, float]] | None, fallback: float) -> float:
    if not bounding_box:
        return fallback
    ys = [point[1] for point in bounding_box]
    return sum(ys) / len(ys)


def _x_start(bounding_box: list[tuple[float, float]] | None, fallback: float) -> float:
    if not bounding_box:
        return fallback
    return min(point[0] for point in bounding_box)


def reconstruct_rows(result: OCRPageResult, y_tolerance: float = 15.0) -> list[str]:
    """
    Groups OCR line fragments into row-level text by proximity of their
    bounding-box vertical center, then orders each row left-to-right.

    Fragments without bounding-box data (e.g. injected directly in tests,
    or already-line-level text such as the calibration fixtures) are
    each treated as their own standalone row and never merged with
    neighbors — there is no positional information to group them by, so
    guessing would silently corrupt the field parser's input contract
    (one row per detected label/value pair).
    """
    if not result.lines:
        return []

    has_box = [line.bounding_box is not None for line in result.lines]

    if not any(has_box):
        # No positional data at all on any line: pass every line through
        # unmodified, in original order.
        return [line.text for line in result.lines]

    indexed = [
        (_y_center(line.bounding_box, fallback=0.0), _x_start(line.bounding_box, fallback=0.0), line.text)
        for line in result.lines
        if line.bounding_box is not None
    ]
    indexed.sort(key=lambda item: item[0])

    rows: list[list[tuple[float, str]]] = []
    current_row: list[tuple[float, str]] = []
    last_y: float | None = None

    for y, x, text in indexed:
        if last_y is None or abs(y - last_y) <= y_tolerance:
            current_row.append((x, text))
        else:
            rows.append(current_row)
            current_row = [(x, text)]
        # Rolling comparison against the most recently added line, not
        # the row's first line — otherwise a generous tolerance lets
        # unrelated lines merge transitively across many small steps.
        last_y = y
    if current_row:
        rows.append(current_row)

    reconstructed = [
        " ".join(text for _, text in sorted(row, key=lambda item: item[0])) for row in rows
    ]

    # Lines that never had bounding-box data are appended as their own
    # standalone rows, preserving their original relative order.
    reconstructed.extend(line.text for line in result.lines if line.bounding_box is None)
    return reconstructed
