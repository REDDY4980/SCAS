"""
Soil parameter validation.

AIB v1.0 Vol 7.8:
    pH 0-14
    EC >= 0
    N, P, K >= 0
    OCR confidence threshold: 0.85
    Below threshold -> manual review screen.
    Missing mandatory fields -> request user correction.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.core.config import get_settings

# Vol 7.6/7.8: the core set whose absence blocks automatic acceptance.
# Micronutrients (zinc/iron/manganese/copper/boron) are still parsed and
# stored when present, but real Soil Health Cards vary in which
# micronutrients they report, so their absence downgrades confidence
# rather than hard-failing the whole report.
CORE_MANDATORY_FIELDS = ("ph", "ec", "organic_carbon", "nitrogen", "phosphorus", "potassium")
MICRONUTRIENT_FIELDS = ("zinc", "iron", "manganese", "copper", "boron")

_RANGE_RULES: dict[str, tuple[float, float]] = {
    "ph": (0.0, 14.0),
    "ec": (0.0, float("inf")),
    "organic_carbon": (0.0, float("inf")),
    "nitrogen": (0.0, float("inf")),
    "phosphorus": (0.0, float("inf")),
    "potassium": (0.0, float("inf")),
    "zinc": (0.0, float("inf")),
    "iron": (0.0, float("inf")),
    "manganese": (0.0, float("inf")),
    "copper": (0.0, float("inf")),
    "boron": (0.0, float("inf")),
    "sulphur": (0.0, float("inf")),
}


@dataclass
class ValidationResult:
    is_valid: bool
    status: str  # "success" | "needs_review" | "failed"
    missing_core_fields: list[str] = field(default_factory=list)
    out_of_range_fields: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def validate_soil_values(
    values: dict[str, float],
    ocr_confidence: float,
    conflicting_values: dict[str, list[float]] | None = None,
) -> ValidationResult:
    """`conflicting_values`: fields for which the report contained more than
    one different reading (field_parser.ParsedReport.conflicts). Such a
    report always needs human review — the kept value may be the wrong one."""
    settings = get_settings()
    warnings: list[str] = []
    conflicts = {k: v for k, v in (conflicting_values or {}).items() if k in values}

    missing_core = [f for f in CORE_MANDATORY_FIELDS if f not in values]
    out_of_range: list[str] = []
    for name, value in values.items():
        lo, hi = _RANGE_RULES.get(name, (0.0, float("inf")))
        if not (lo <= value <= hi):
            out_of_range.append(name)

    missing_micro = [f for f in MICRONUTRIENT_FIELDS if f not in values]
    if missing_micro:
        warnings.append(
            f"Micronutrient fields not detected (may be absent from this report format): "
            f"{', '.join(missing_micro)}"
        )

    if conflicts:
        details = "; ".join(
            f"{name.replace('_', ' ')}: {', '.join(f'{v:g}' for v in readings)}"
            for name, readings in sorted(conflicts.items())
        )
        warnings = warnings + [
            f"The report contains different values for the same parameter ({details}). "
            "Please check these values against your report."
        ]

    if out_of_range:
        # A value outside a physically valid range (e.g. pH 17) means the
        # OCR/parsing very likely misread a digit — never silently accept it.
        return ValidationResult(
            is_valid=False,
            status="failed",
            missing_core_fields=missing_core,
            out_of_range_fields=out_of_range,
            warnings=warnings,
        )

    if missing_core:
        return ValidationResult(
            is_valid=False,
            status="needs_review",
            missing_core_fields=missing_core,
            out_of_range_fields=out_of_range,
            warnings=warnings + ["One or more mandatory soil parameters were not detected."],
        )

    if conflicts:
        return ValidationResult(
            is_valid=False,
            status="needs_review",
            missing_core_fields=missing_core,
            out_of_range_fields=out_of_range,
            warnings=warnings,
        )

    if ocr_confidence < settings.ocr_confidence_threshold:
        return ValidationResult(
            is_valid=False,
            status="needs_review",
            missing_core_fields=missing_core,
            out_of_range_fields=out_of_range,
            warnings=warnings
            + [
                f"OCR confidence {ocr_confidence:.2f} is below the "
                f"{settings.ocr_confidence_threshold:.2f} threshold; manual verification required."
            ],
        )

    return ValidationResult(
        is_valid=True,
        status="success",
        missing_core_fields=missing_core,
        out_of_range_fields=out_of_range,
        warnings=warnings,
    )
