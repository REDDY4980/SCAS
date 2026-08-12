"""Recommendation repository — pure CRUD, no business logic (AIB v1.0 Vol 12.6)."""

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.models.farm import Farm
from app.models.recommendation import Recommendation


class RecommendationRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, recommendation_id: uuid.UUID) -> Recommendation | None:
        return self.db.get(Recommendation, recommendation_id)

    def get_with_details(self, recommendation_id: uuid.UUID) -> Recommendation | None:
        """Eager-loads relationships needed for a full history detail view."""
        return self.db.execute(
            select(Recommendation)
            .where(Recommendation.id == recommendation_id)
            .options(
                joinedload(Recommendation.fertilizer_recommendations),
                joinedload(Recommendation.report),
                joinedload(Recommendation.weather),
                joinedload(Recommendation.farm),
            )
        ).unique().scalar_one_or_none()

    def list_for_user(
        self, user_id: uuid.UUID, farm_id: uuid.UUID | None = None, limit: int = 50
    ) -> list[Recommendation]:
        """Vol 3 SCR-010: history spans all of a user's farms, optionally
        filtered to one farm."""
        query = (
            select(Recommendation)
            .join(Farm, Farm.id == Recommendation.farm_id)
            .where(Farm.user_id == user_id)
        )
        if farm_id is not None:
            query = query.where(Recommendation.farm_id == farm_id)
        query = query.order_by(Recommendation.created_at.desc()).limit(limit)
        return list(self.db.execute(query).scalars())

    def create(
        self,
        *,
        farm_id: uuid.UUID,
        report_id: uuid.UUID | None,
        weather_id: uuid.UUID | None,
        recommended_crop: str,
        confidence_score: float,
        reasoning: str,
    ) -> Recommendation:
        rec = Recommendation(
            farm_id=farm_id,
            report_id=report_id,
            weather_id=weather_id,
            recommended_crop=recommended_crop,
            confidence_score=confidence_score,
            reasoning=reasoning,
        )
        self.db.add(rec)
        self.db.commit()
        self.db.refresh(rec)
        return rec
