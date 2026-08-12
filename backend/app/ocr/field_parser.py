"""
Soil report field parser.

AIB v1.0 Vol 7.3 pipeline position: PaddleOCR -> Layout Analysis ->
**Field Extraction -> Regex Parsing** -> Unit Normalization.

This module implements the Field Extraction + Regex Parsing steps. It
operates on text *lines* that have already been through layout analysis
(each line represents one reconstructed table row / label-value pair —
layout analysis, not this module, is responsible for that reconstruction).

Vol 7.7 Parsing Strategy: "Use keyword mapping + regex... Normalize units
before storage... Unknown fields ignored but logged."
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field

logger = logging.getLogger("scas.ocr.field_parser")

# Vol 7.6 mandatory numeric soil parameters, in priority-checked order.
# Longer/more specific keyword patterns are listed first so e.g.
# "organic carbon" is matched before a bare, riskier single-letter test.
_FIELD_PATTERNS: list[tuple[str, list[str]]] = [
    ("organic_carbon", [r"organic\s*carbon", r"\boc\b"]),
    ("phosphorus", [r"phosphorus", r"\(p\)"]),
    ("potassium", [r"potassium", r"\(k\)"]),
    ("nitrogen", [r"nitrogen", r"\(n\)"]),
    ("manganese", [r"manganese", r"\(mn\)"]),
    ("magnesium", [r"magnesium", r"\(mg\)"]),
    ("zinc", [r"\bzinc\b", r"\(zn\)"]),
    ("copper", [r"\bcopper\b", r"\(cu\)"]),
    ("boron", [r"\bboron\b", r"\(b\)"]),
    ("iron", [r"\biron\b", r"\(fe\)"]),
    ("sulphur", [r"sulphur", r"sulfur", r"\(s\)"]),
    ("ec", [r"\bec\b", r"electrical\s*conductivity"]),
    ("ph", [r"\bph\b"]),
]

_NUMBER_RE = re.compile(r"-?\d+\.?\d*")

# Vol 7.7 unit normalization: SHC reports mix "kg/ha", "kg ha-1", "kg ha−1".
# All observed macro/micronutrient units already match the target storage
# unit for this dataset (kg/ha or ppm) — normalization here is about
# *recognizing* the unit token, not converting scale, since the AIB
# schema stores these fields unit-less (Vol 5.3 soil_parameters columns
# carry no unit suffix; unit is implied by field/domain convention).
_UNIT_HINTS = ("kg/ha", "kg ha", "ppm", "%", "ds/m", "ds m")

_METADATA_PATTERNS: dict[str, str] = {
    "district": r"district\s*[:\-]\s*(.+)",
    "village": r"village\s*[:\-]\s*(.+)",
    "state": r"state\s*[:\-]\s*(.+)",
    "soil_type": r"soil\s*type\s*[:\-]\s*(.+)",
}

_DATE_RE = re.compile(r"\b(\d{1,2})[/-](\d{1,2})[/-](\d{2,4})\b")


@dataclass
class ParsedField:
    field_name: str
    raw_text: str
    value: float
    unit_hint: str | None = None


@dataclass
class ParsedReport:
    values: dict[str, float] = field(default_factory=dict)
    metadata: dict[str, str] = field(default_factory=dict)
    unmatched_lines: list[str] = field(default_factory=list)
    matched_fields: list[ParsedField] = field(default_factory=list)


def _find_unit_hint(line: str) -> str | None:
    lowered = line.lower()
    for hint in _UNIT_HINTS:
        if hint in lowered:
            return hint
    return None


def _extract_number_after(line: str, keyword_end: int) -> tuple[str, float] | None:
    """Finds the first numeric token appearing at/after `keyword_end`."""
    match = _NUMBER_RE.search(line, keyword_end)
    if match is None:
        return None
    raw = match.group(0)
    try:
        return raw, float(raw)
    except ValueError:
        return None


def parse_lines(lines: list[str]) -> ParsedReport:
    """
    Parses layout-reconstructed OCR lines into structured soil fields.

    Vol 7.7: unknown/unmatched lines are not an error — they're logged
    and ignored, since a soil report contains plenty of boilerplate
    (headers, disclaimers, government seals text, etc.) that carries no
    soil-parameter data.
    """
    report = ParsedReport()
    claimed_field_names: set[str] = set()

    for raw_line in lines:
        line = raw_line.strip()
        if not line:
            continue

        matched = False

        # Metadata fields first — explicit "Label: value" patterns.
        for meta_name, pattern in _METADATA_PATTERNS.items():
            m = re.search(pattern, line, re.IGNORECASE)
            if m and meta_name not in report.metadata:
                report.metadata[meta_name] = m.group(1).strip()
                matched = True
                break
        if matched:
            continue

        date_match = _DATE_RE.search(line)
        if "date" in line.lower() and date_match and "sample_date" not in report.metadata:
            report.metadata["sample_date"] = date_match.group(0)
            matched = True
            continue

        # Numeric soil-parameter fields.
        for canonical_name, patterns in _FIELD_PATTERNS:
            if canonical_name in claimed_field_names:
                continue  # first match per field wins; avoid rating-table overwrite
            for pattern in patterns:
                kw_match = re.search(pattern, line, re.IGNORECASE)
                if kw_match is None:
                    continue
                extracted = _extract_number_after(line, kw_match.end())
                if extracted is None:
                    continue
                raw_number, value = extracted
                report.values[canonical_name] = value
                report.matched_fields.append(
                    ParsedField(
                        field_name=canonical_name,
                        raw_text=line,
                        value=value,
                        unit_hint=_find_unit_hint(line),
                    )
                )
                claimed_field_names.add(canonical_name)
                matched = True
                break
            if matched:
                break

        if not matched:
            report.unmatched_lines.append(line)
            logger.debug("OCR line did not match any known field: %r", line)

    return report
