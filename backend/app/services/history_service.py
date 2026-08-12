"""
HistoryService — AIB v1.0 Vol 2.3 FM-10 (Recommendation History), Vol 3
SCR-010 (list/search/filter, persistent storage).

Every completed analysis (Vol 2.5 BR-05) is already persisted as a
Recommendation row with its associated soil_parameters, weather_snapshot
and fertilizer_recommendations (Phases 4/5/7/8) — this service's only
job is to assemble and format that existing data for a farmer-facing
history view, not to persist anything new.
"""

from __future__ import annotations

import uuid

from fastapi import HTTPException, status

from app.models.user import User
from app.repositories.farm_repository import FarmRepository
from app.repositories.recommendation_repository import RecommendationRepository
from app.schemas.history import (
    FertilizerHistoryItem,
    HistoryDetailOut,
    HistorySummaryOut,
    SoilParametersSnapshot,
    WeatherSnapshotSummary,
)


class HistoryService:
    def __init__(self, recommendation_repo: RecommendationRepository, farm_repo: FarmRepository):
        self.recommendation_repo = recommendation_repo
        self.farm_repo = farm_repo

    def list_history(
        self, user: User, farm_id: uuid.UUID | None = None, limit: int = 50
    ) -> list[HistorySummaryOut]:
        if farm_id is not None:
            farm = self.farm_repo.get_by_id(farm_id)
            if farm is None or farm.user_id != user.id:
                raise HTTPException(status.HTTP_404_NOT_FOUND, "Farm not found.")

        records = self.recommendation_repo.list_for_user(user.id, farm_id=farm_id, limit=limit)
        return [
            HistorySummaryOut(
                id=r.id,
                farm_id=r.farm_id,
                farm_name=r.farm.farm_name,
                recommended_crop=r.recommended_crop,
                confidence_score=r.confidence_score,
                created_at=r.created_at,
            )
            for r in records
        ]

    def get_detail(self, user: User, recommendation_id: uuid.UUID) -> HistoryDetailOut:
        rec = self.recommendation_repo.get_with_details(recommendation_id)
        if rec is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "History entry not found.")
        if rec.farm.user_id != user.id:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "History entry not found.")

        soil_snapshot = None
        if rec.report is not None and rec.report.soil_parameters is not None:
            p = rec.report.soil_parameters
            soil_snapshot = SoilParametersSnapshot(
                ph=p.ph, ec=p.ec, organic_carbon=p.organic_carbon,
                nitrogen=p.nitrogen, phosphorus=p.phosphorus, potassium=p.potassium,
                zinc=p.zinc, iron=p.iron, manganese=p.manganese, copper=p.copper, boron=p.boron,
            )

        weather_summary = None
        if rec.weather is not None:
            weather_summary = WeatherSnapshotSummary(
                temperature=rec.weather.temperature,
                humidity=rec.weather.humidity,
                rainfall=rec.weather.rainfall,
                wind_speed=rec.weather.wind_speed,
                captured_at=rec.weather.captured_at,
            )

        return HistoryDetailOut(
            id=rec.id,
            farm_id=rec.farm_id,
            farm_name=rec.farm.farm_name,
            recommended_crop=rec.recommended_crop,
            confidence_score=rec.confidence_score,
            reasoning=rec.reasoning,
            created_at=rec.created_at,
            soil_parameters=soil_snapshot,
            weather=weather_summary,
            fertilizer_recommendations=[
                FertilizerHistoryItem(
                    fertilizer_name=f.fertilizer_name, dosage=f.dosage, reason=f.reason
                )
                for f in rec.fertilizer_recommendations
            ],
        )
