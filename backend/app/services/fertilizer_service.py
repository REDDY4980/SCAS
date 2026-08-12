"""
FertilizerService — orchestrates the Vol 11.3 pipeline:

    Validated Soil Parameters + Selected Crop
        -> Nutrient Analysis -> Deficiency Detection
        -> Crop Nutrient Requirement -> Fertilizer Knowledge Base
        -> Dosage Estimation -> Explainable Fertilizer Recommendation
"""

from __future__ import annotations

import uuid

from fastapi import HTTPException, status

from app.models.user import User
from app.repositories.farm_repository import FarmRepository
from app.repositories.fertilizer_repository import FertilizerRepository
from app.repositories.recommendation_repository import RecommendationRepository
from app.repositories.soil_repository import SoilRepository
from app.rules.deficiency_detector import DeficiencyDetector
from app.rules.fertilizer_knowledge_base import FertilizerKnowledgeBase
from app.rules.fertilizer_selector import FertilizerSelector
from app.schemas.fertilizer import FertilizerRecommendationOut, FertilizerResponseOut


class FertilizerService:
    def __init__(
        self,
        recommendation_repo: RecommendationRepository,
        farm_repo: FarmRepository,
        soil_repo: SoilRepository,
        fertilizer_repo: FertilizerRepository,
        kb: FertilizerKnowledgeBase | None = None,
    ):
        self.recommendation_repo = recommendation_repo
        self.farm_repo = farm_repo
        self.soil_repo = soil_repo
        self.fertilizer_repo = fertilizer_repo
        self.detector = DeficiencyDetector()
        self.selector = FertilizerSelector(kb)

    def _get_owned_recommendation_or_404(self, user: User, recommendation_id: uuid.UUID):
        rec = self.recommendation_repo.get_by_id(recommendation_id)
        if rec is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Recommendation not found.")
        farm = self.farm_repo.get_by_id(rec.farm_id)
        if farm is None or farm.user_id != user.id:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Recommendation not found.")
        return rec

    def generate(self, user: User, recommendation_id: uuid.UUID) -> FertilizerResponseOut:
        rec = self._get_owned_recommendation_or_404(user, recommendation_id)

        if rec.report_id is None:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                "This recommendation has no associated soil report; cannot generate a "
                "fertilizer recommendation without soil data.",
            )
        soil_report = self.soil_repo.get_report_by_id(rec.report_id)
        if soil_report is None or soil_report.soil_parameters is None:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST, "Soil parameters for this recommendation are unavailable."
            )
        params = soil_report.soil_parameters
        soil_dict = {
            "nitrogen": params.nitrogen,
            "phosphorus": params.phosphorus,
            "potassium": params.potassium,
            "organic_carbon": params.organic_carbon,
            "zinc": params.zinc,
            "iron": params.iron,
            "manganese": params.manganese,
            "copper": params.copper,
            "boron": params.boron,
        }

        deficiency = self.detector.analyze(soil_dict)
        items = self.selector.select(rec.recommended_crop, deficiency)

        # Idempotent regeneration: clear any prior fertilizer recs for
        # this recommendation before writing the fresh set.
        self.fertilizer_repo.delete_for_recommendation(recommendation_id)
        for item in items:
            self.fertilizer_repo.create(
                recommendation_id=recommendation_id,
                fertilizer_name=item.fertilizer_name,
                dosage=item.dosage,
                reason=item.reason,
            )

        coverage = "sourced" if self.selector.kb.lookup_crop(rec.recommended_crop) else "fallback"

        return FertilizerResponseOut(
            recommendation_id=recommendation_id,
            crop=rec.recommended_crop,
            deficiency_profile=deficiency.classifications,
            fertilizers=[
                FertilizerRecommendationOut(
                    fertilizer_name=i.fertilizer_name,
                    dosage=i.dosage,
                    target_nutrients=i.target_nutrients,
                    reason=i.reason,
                    application_method=i.application_method,
                    precautions=i.precautions,
                    source=i.source,
                )
                for i in items
            ],
            knowledge_base_coverage=coverage,
        )

    def get(self, user: User, recommendation_id: uuid.UUID) -> FertilizerResponseOut:
        rec = self._get_owned_recommendation_or_404(user, recommendation_id)
        stored = self.fertilizer_repo.list_for_recommendation(recommendation_id)
        if not stored:
            raise HTTPException(
                status.HTTP_404_NOT_FOUND,
                "No fertilizer recommendation generated yet for this recommendation. "
                "POST to this endpoint first.",
            )
        return FertilizerResponseOut(
            recommendation_id=recommendation_id,
            crop=rec.recommended_crop,
            deficiency_profile={},  # not re-derived on GET; see reasoning field per item
            fertilizers=[
                FertilizerRecommendationOut(
                    fertilizer_name=s.fertilizer_name,
                    dosage=s.dosage,
                    target_nutrients=[],
                    reason=s.reason,
                    application_method="",
                    precautions="",
                    source="",
                )
                for s in stored
            ],
            knowledge_base_coverage="",
        )
