"""
RecommendationService — orchestrates the full Vol 10.3 decision pipeline:

    Validated Soil JSON + Validated Climate JSON
        -> Feature Engineering -> XGBoost Prediction
        -> Top-N Crop Probabilities -> Agronomic Rule Validation
        -> Confidence Adjustment -> Crop Ranking
        -> Explanation Generation -> Final Recommendation
"""

from __future__ import annotations

import uuid

from fastapi import HTTPException, status

from app.ml.registry import get_inference_engine
from app.models.farm import Farm
from app.models.user import User
from app.repositories.farm_repository import FarmRepository
from app.repositories.recommendation_repository import RecommendationRepository
from app.repositories.soil_repository import SoilRepository
from app.repositories.weather_repository import WeatherRepository
from app.rules.agronomic_rules import AgronomicRuleEngine
from app.rules.confidence_engine import ConfidenceEngine
from app.rules.crop_ranker import rank
from app.rules.explanation_engine import build_explanation
from app.schemas.recommendation import CropRecommendationItem, RecommendationOut


class RecommendationService:
    def __init__(
        self,
        farm_repo: FarmRepository,
        soil_repo: SoilRepository,
        weather_repo: WeatherRepository,
        recommendation_repo: RecommendationRepository,
        rule_engine: AgronomicRuleEngine | None = None,
        confidence_engine: ConfidenceEngine | None = None,
    ):
        self.farm_repo = farm_repo
        self.soil_repo = soil_repo
        self.weather_repo = weather_repo
        self.recommendation_repo = recommendation_repo
        self.rule_engine = rule_engine or AgronomicRuleEngine()
        self.confidence_engine = confidence_engine or ConfidenceEngine()

    def _get_owned_farm_or_404(self, user: User, farm_id: uuid.UUID) -> Farm:
        farm = self.farm_repo.get_by_id(farm_id)
        if farm is None or farm.user_id != user.id:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Farm not found.")
        return farm

    def generate(self, user: User, farm_id: uuid.UUID) -> RecommendationOut:
        farm = self._get_owned_farm_or_404(user, farm_id)

        # Vol 10.4 mandatory inputs: validated soil + climate.
        soil_report = self.soil_repo.get_latest_validated_for_farm(farm_id)
        if soil_report is None or soil_report.soil_parameters is None:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                "No validated soil report found for this farm. Upload and process a soil "
                "report (and correct it if needed) before requesting a recommendation.",
            )
        params = soil_report.soil_parameters
        soil_dict = {
            "ph": params.ph,
            "ec": params.ec,
            "organic_carbon": params.organic_carbon,
            "nitrogen": params.nitrogen,
            "phosphorus": params.phosphorus,
            "potassium": params.potassium,
            "zinc": params.zinc,
            "iron": params.iron,
            "manganese": params.manganese,
            "copper": params.copper,
            "boron": params.boron,
        }

        weather_snapshot = self.weather_repo.get_latest_for_farm(farm_id)
        if weather_snapshot is None:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                "No climate data found for this farm. Call GET /weather/current for this "
                "farm before requesting a recommendation.",
            )
        weather_dict = {
            "temperature": weather_snapshot.temperature,
            "humidity": weather_snapshot.humidity,
            "rainfall": weather_snapshot.rainfall,
            "wind_speed": weather_snapshot.wind_speed,
        }

        # Vol 9.7 Feature Fusion: soil + climate -> ordered feature vector.
        feature_input = {
            "N": soil_dict["nitrogen"],
            "P": soil_dict["phosphorus"],
            "K": soil_dict["potassium"],
            "temperature": weather_dict["temperature"],
            "humidity": weather_dict["humidity"],
            "ph": soil_dict["ph"],
            "rainfall": weather_dict["rainfall"],
        }
        missing_features = [k for k, v in feature_input.items() if v is None]
        if missing_features:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                f"Cannot generate a recommendation: missing values for {missing_features}. "
                f"Please correct the soil report or refresh weather data.",
            )

        engine = get_inference_engine()
        inference_result = engine.predict_top5(feature_input)

        # Vol 10.6/10.7: agronomic validation + confidence adjustment for
        # every candidate the model proposed.
        scored_crops = []
        for prediction in inference_result.predictions:
            rule_eval = self.rule_engine.evaluate(
                prediction.crop, soil_dict, farm_state=farm.state, farm_soil_type=farm.soil_type
            )
            scored_crops.append(
                self.confidence_engine.adjust(prediction.crop, prediction.confidence, rule_eval)
            )

        # Vol 10.8: re-rank by adjusted confidence.
        ranked = rank(scored_crops)
        primary = ranked[0]

        top_recommendations = [
            CropRecommendationItem(
                crop=sc.crop,
                confidence=round(sc.adjusted_confidence, 4),
                reason=build_explanation(
                    sc, soil_dict, weather_dict, inference_result.feature_importance
                ),
            )
            for sc in ranked
        ]

        primary_explanation = top_recommendations[0].reason

        persisted = self.recommendation_repo.create(
            farm_id=farm.id,
            report_id=soil_report.id,
            weather_id=weather_snapshot.id,
            recommended_crop=primary.crop,
            confidence_score=primary.adjusted_confidence,
            reasoning=primary_explanation,
        )

        return RecommendationOut(
            id=persisted.id,
            farm_id=farm.id,
            primary_crop=primary.crop,
            confidence=round(primary.adjusted_confidence, 4),
            explanation=primary_explanation,
            top_recommendations=top_recommendations,
            model_version=inference_result.model_version,
            created_at=persisted.created_at,
        )

    def get_by_id(self, user: User, recommendation_id: uuid.UUID) -> RecommendationOut:
        rec = self.recommendation_repo.get_by_id(recommendation_id)
        if rec is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Recommendation not found.")
        self._get_owned_farm_or_404(user, rec.farm_id)  # ownership via farm
        return RecommendationOut(
            id=rec.id,
            farm_id=rec.farm_id,
            primary_crop=rec.recommended_crop,
            confidence=rec.confidence_score,
            explanation=rec.reasoning,
            top_recommendations=[
                CropRecommendationItem(
                    crop=rec.recommended_crop, confidence=rec.confidence_score, reason=rec.reasoning
                )
            ],
            model_version="",
            created_at=rec.created_at,
        )
