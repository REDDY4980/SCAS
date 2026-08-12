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

from app.rules.deficiency_detector import DeficiencyProfile
from app.rules.fertilizer_knowledge_base import FertilizerKnowledgeBase

# Vol 11.8 step 3: which general-purpose product class supplies which
# macronutrient, drawn from the KB's own product catalog (Urea/DAP/MOP
# compositions are product-grade facts, not crop-specific doses).
_NUTRIENT_TO_PRODUCT = {
    "nitrogen": "Urea",
    "phosphorus": "DAP",
    "potassium": "MOP",
}


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

    def select(self, crop: str, deficiency: DeficiencyProfile) -> list[FertilizerRecommendationItem]:
        crop_dose = self.kb.lookup_crop(crop)
        if crop_dose is not None:
            return self._sourced_recommendation(crop_dose)
        return self._fallback_recommendation(crop, deficiency)

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
        self, crop: str, deficiency: DeficiencyProfile
    ) -> list[FertilizerRecommendationItem]:
        """Vol 11.12: 'Unknown crop -> fallback nutrient recommendation.'
        Names the right product class for each detected deficiency
        without fabricating a dosage number."""
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
            items.append(
                FertilizerRecommendationItem(
                    fertilizer_name=product.name if product else product_name,
                    dosage=(
                        "Dosage not available — no source-traceable crop-specific "
                        f"recommendation exists yet for {crop} in the starter knowledge base. "
                        "Consult a local agricultural extension officer or a soil-test-based "
                        "(STCR) recommendation before applying."
                    ),
                    target_nutrients=[nutrient],
                    reason=(
                        f"Soil test indicates low {nutrient} for this farm. {product_name} is "
                        f"the standard source for this nutrient "
                        f"({product.primary_use if product else ''})."
                    ),
                    application_method="Consult local agricultural extension guidance.",
                    precautions=(
                        "This is a nutrient-class suggestion only, not a dosage recommendation. "
                        "Applying fertilizer without a soil-test-based dose risks over- or "
                        "under-application."
                    ),
                    source=product.source if product else "",
                )
            )
        return items
