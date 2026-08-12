"""
Fertilizer Selector / Dosage Engine.

AIB v1.0 Vol 11.8 Recommendation Strategy:
    1. Identify deficient nutrients.
    2. Consider crop nutrient demand.
    3. Select appropriate fertilizer(s).
    4. Estimate application dosage.
    5. Validate against agronomic rules.
    6. Produce final recommendation.

Vol 11.12 Failure Handling: "Unknown crop -> fallback nutrient
recommendation." This is the central design decision of this module:
when a crop has no sourced dose in the KB (the overwhelming majority —
21 of 22 ML-supported crops), the fallback path recommends WHICH
nutrient/product class addresses a detected deficiency without
inventing a kg/ha number, and says so explicitly in the reason text.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.rules.deficiency_detector import MACRO_THRESHOLDS, DeficiencyProfile
from app.rules.fertilizer_knowledge_base import FertilizerKnowledgeBase, FertilizerProduct

# Vol 11.8 step 3: which general-purpose product class supplies which
# macronutrient, drawn from the KB's own product catalog (Urea/DAP/MOP
# compositions are product-grade facts, not crop-specific doses).
_NUTRIENT_TO_PRODUCT = {
    "nitrogen": "Urea",
    "phosphorus": "DAP",
    "potassium": "MOP",
}

# Which of FertilizerProduct's nutrient-percent fields supplies each
# deficiency. Available P on an SHC report and P2O5 on a fertilizer bag
# aren't the same unit strictly (P2O5 = P x ~2.29), but the project's
# own deficiency thresholds and this KB already treat "phosphorus" on
# one side and "P2O5_percent" on the other as the working pair for this
# calculation — no separate elemental-P fertilizer % exists in the KB
# to divide by instead.
_NUTRIENT_TO_PERCENT_FIELD = {
    "nitrogen": "n_percent",
    "phosphorus": "p2o5_percent",
    "potassium": "k2o_percent",
}

_ACRE_TO_HECTARE = 0.4047


@dataclass
class FertilizerRecommendationItem:
    fertilizer_name: str
    dosage: str
    target_nutrients: list[str]
    reason: str
    application_method: str
    precautions: str
    source: str = ""


class FertilizerSelector:
    """Vol 11.14 suggested module: fertilizer/fertilizer_selector.py + dosage_engine.py."""

    def __init__(self, kb: FertilizerKnowledgeBase | None = None):
        self.kb = kb or FertilizerKnowledgeBase()

    def select(
        self, crop: str, deficiency: DeficiencyProfile, area_acres: float | None = None
    ) -> list[FertilizerRecommendationItem]:
        crop_dose = self.kb.lookup_crop(crop)
        if crop_dose is not None:
            return self._sourced_recommendation(crop_dose)
        return self._fallback_recommendation(crop, deficiency, area_acres)

    def _sourced_recommendation(self, crop_dose) -> list[FertilizerRecommendationItem]:
        """Vol 11.8 with a matched KB entry — a real sourced dose exists."""
        items: list[FertilizerRecommendationItem] = []
        dose_map = [
            ("Nitrogen (N)", crop_dose.n_kg_ha, "nitrogen"),
            ("Phosphorus (P2O5)", crop_dose.p2o5_kg_ha, "phosphorus"),
            ("Potassium (K2O)", crop_dose.k2o_kg_ha, "potassium"),
        ]
        for label, kg_per_ha, nutrient in dose_map:
            if kg_per_ha <= 0:
                continue
            items.append(
                FertilizerRecommendationItem(
                    fertilizer_name=", ".join(crop_dose.fertilizer_products) or label,
                    dosage=f"{kg_per_ha:.0f} kg/ha {label} ({crop_dose.condition})",
                    target_nutrients=[nutrient],
                    reason=(
                        f"Sourced package-of-practice recommendation for {crop_dose.crop} "
                        f"({crop_dose.region})."
                    ),
                    application_method="Per the cited source's recommended split-application schedule.",
                    precautions=crop_dose.caution,
                    source=crop_dose.source,
                )
            )
        return items

    def _fallback_recommendation(
        self, crop: str, deficiency: DeficiencyProfile, area_acres: float | None
    ) -> list[FertilizerRecommendationItem]:
        """Vol 11.12: 'Unknown crop -> fallback nutrient recommendation.'
        For a crop with no sourced package-of-practice dose, this
        computes a standard nutrient-replacement dosage instead of
        withholding a number: deficit (target sufficiency level minus
        the farm's measured level) converted to product weight via the
        product's own nutrient percentage, then scaled to the farm's
        actual registered area. This is a general agronomic calculation,
        not a crop-specific sourced figure — every item says so."""
        if not deficiency.deficient_macro_nutrients:
            return [
                FertilizerRecommendationItem(
                    fertilizer_name="None required",
                    dosage="Not applicable",
                    target_nutrients=[],
                    reason=(
                        f"No macronutrient deficiency detected in this soil test for {crop}. "
                        f"A source-traceable crop-specific dose for {crop} is not yet in the "
                        f"starter knowledge base, but current soil nutrient levels do not "
                        f"indicate a correction is needed."
                    ),
                    application_method="Not applicable",
                    precautions="Re-test soil periodically; conditions change over a growing season.",
                )
            ]

        items: list[FertilizerRecommendationItem] = []
        for nutrient in deficiency.deficient_macro_nutrients:
            product_name = _NUTRIENT_TO_PRODUCT.get(nutrient)
            if product_name is None:
                continue
            product = self.kb.get_product(product_name)
            items.append(self._calculated_item(crop, nutrient, product_name, product, deficiency, area_acres))
        return items

    def _calculated_item(
        self,
        crop: str,
        nutrient: str,
        product_name: str,
        product: FertilizerProduct | None,
        deficiency: DeficiencyProfile,
        area_acres: float | None,
    ) -> FertilizerRecommendationItem:
        dosage = self._calculate_dosage(nutrient, product, deficiency, area_acres)
        if dosage is None:
            return FertilizerRecommendationItem(
                fertilizer_name=product.name if product else product_name,
                dosage=(
                    "Dosage not available — no source-traceable crop-specific "
                    f"recommendation exists yet for {crop} in the starter knowledge base, and "
                    "this farm's soil report or fertilizer catalog is missing a value this "
                    "estimate needs. Consult a local agricultural extension officer or a "
                    "soil-test-based (STCR) recommendation before applying."
                ),
                target_nutrients=[nutrient],
                reason=(
                    f"Soil test indicates low {nutrient} for this farm. {product_name} is the "
                    f"standard source for this nutrient ({product.primary_use if product else ''})."
                ),
                application_method="Consult local agricultural extension guidance.",
                precautions=(
                    "This is a nutrient-class suggestion only, not a dosage recommendation. "
                    "Applying fertilizer without a soil-test-based dose risks over- or "
                    "under-application."
                ),
                source=product.source if product else "",
            )

        product_kg_ha, total_kg, area_ha, measured, target = dosage
        assert product is not None  # _calculate_dosage only returns non-None when product is present

        if total_kg is not None and area_ha is not None:
            dosage_text = (
                f"~{total_kg:.1f} kg {product.name} total for this farm "
                f"({product_kg_ha:.1f} kg/ha x {area_ha:.2f} ha) — calculated nutrient-"
                f"replacement estimate, not a sourced dose."
            )
        else:
            dosage_text = (
                f"~{product_kg_ha:.1f} kg/ha {product.name} — calculated nutrient-replacement "
                f"estimate, not a sourced dose. Register this farm's area for a total quantity."
            )

        return FertilizerRecommendationItem(
            fertilizer_name=product.name,
            dosage=dosage_text,
            target_nutrients=[nutrient],
            reason=(
                f"Soil test shows {nutrient} at {measured:.1f} kg/ha, below the {target:.0f} "
                f"kg/ha sufficiency threshold for this soil class. {product.name} "
                f"({product.grade}) supplies this nutrient; dosage calculated as "
                f"deficit ÷ product nutrient content, standard agronomic nutrient-replacement "
                f"practice — not a crop-specific package-of-practice figure like the sourced "
                f"KB entries."
            ),
            application_method=(
                "Standard nutrient-replacement estimate — split into 2-3 applications through "
                "the growing season per local extension guidance rather than one basal dose."
            ),
            precautions=(
                "This is a calculated general estimate, not a government/university-sourced "
                f"crop-specific figure for {crop}. Confirm with a local agricultural extension "
                "officer or soil-test-based (STCR) recommendation before applying at scale."
            ),
            source="Calculated: deficit ÷ product nutrient % (standard nutrient-replacement formula).",
        )

    def _calculate_dosage(
        self,
        nutrient: str,
        product: FertilizerProduct | None,
        deficiency: DeficiencyProfile,
        area_acres: float | None,
    ) -> tuple[float, float | None, float | None, float, float] | None:
        """Returns (product_kg_per_ha, total_kg_or_None, area_ha_or_None,
        measured_level, target_level), or None if the calculation can't
        be performed (missing product, missing measured value, or the
        product doesn't actually supply this nutrient)."""
        if product is None:
            return None
        measured = deficiency.macro_values.get(nutrient)
        threshold = MACRO_THRESHOLDS.get(nutrient)
        percent_field = _NUTRIENT_TO_PERCENT_FIELD.get(nutrient)
        if measured is None or threshold is None or percent_field is None:
            return None
        target = threshold[0]  # low_bound: the sufficiency level a "low" reading falls under
        deficit_kg_ha = target - measured
        if deficit_kg_ha <= 0:
            return None
        percent = getattr(product, percent_field, 0.0)
        if not percent:
            return None
        product_kg_ha = deficit_kg_ha / (percent / 100)

        if area_acres is not None and area_acres > 0:
            area_ha = area_acres * _ACRE_TO_HECTARE
            total_kg = product_kg_ha * area_ha
            return product_kg_ha, total_kg, area_ha, measured, target
        return product_kg_ha, None, None, measured, target
