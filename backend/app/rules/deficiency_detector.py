"""
Deficiency Detection Engine.

AIB v1.0 Vol 11.5 Nutrient Analysis: "Classify each as Low, Medium or
High using configurable thresholds."
Vol 11.6 Deficiency Detection Engine: "Generate a structured nutrient
deficiency profile before fertilizer selection."

Only N, P, K, and Organic Carbon are classified here, using the same
authoritative Government of India Soil Health Card national reference
classes already used by the agronomic rule engine (Vol 8, Requirement
3's `agronomic_rules_v1.json`). Micronutrients (Zn, Fe, Mn, Cu, B) are
NOT auto-classified into Low/Medium/High bands, because no
authoritative generic threshold table for them was supplied in the
project's resolved resources — MASTER_RESOURCE_INDEX.md's explicit
directive is "Never silently fabricate missing agricultural
thresholds." Their raw values are still surfaced for the explanation
layer to reference.
"""

from __future__ import annotations

from dataclasses import dataclass, field

_MACRO_THRESHOLDS = {
    # (low_upper_bound_exclusive, medium_upper_bound_exclusive) — same
    # source as app/rules/agronomic_rules.py's soil-status classification.
    "nitrogen": (280, 560),
    "phosphorus": (10, 25),
    "potassium": (120, 280),
    "organic_carbon": (0.5, 0.75),
}

UNCLASSIFIED_MICRONUTRIENTS = ("zinc", "iron", "manganese", "copper", "boron")


@dataclass
class DeficiencyProfile:
    classifications: dict[str, str] = field(default_factory=dict)  # "low" | "medium" | "high"
    deficient_macro_nutrients: list[str] = field(default_factory=list)
    unclassified_values: dict[str, float] = field(default_factory=dict)


class DeficiencyDetector:
    """Vol 11.14 suggested module: fertilizer/deficiency_detector.py."""

    def analyze(self, soil: dict[str, float | None]) -> DeficiencyProfile:
        classifications: dict[str, str] = {}
        deficient: list[str] = []

        for nutrient, (low_bound, medium_bound) in _MACRO_THRESHOLDS.items():
            value = soil.get(nutrient)
            if value is None:
                continue
            if value < low_bound:
                classifications[nutrient] = "low"
                deficient.append(nutrient)
            elif value < medium_bound:
                classifications[nutrient] = "medium"
            else:
                classifications[nutrient] = "high"

        unclassified = {
            n: soil[n] for n in UNCLASSIFIED_MICRONUTRIENTS if soil.get(n) is not None
        }

        return DeficiencyProfile(
            classifications=classifications,
            deficient_macro_nutrients=deficient,
            unclassified_values=unclassified,
        )
