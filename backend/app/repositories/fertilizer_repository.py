"""Fertilizer recommendation repository — pure CRUD (AIB v1.0 Vol 12.6)."""

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.recommendation import FertilizerRecommendation


class FertilizerRepository:
    def __init__(self, db: Session):
        self.db = db

    def list_for_recommendation(self, recommendation_id: uuid.UUID) -> list[FertilizerRecommendation]:
        return list(
            self.db.execute(
                select(FertilizerRecommendation).where(
                    FertilizerRecommendation.recommendation_id == recommendation_id
                )
            ).scalars()
        )

    def create(
        self, *, recommendation_id: uuid.UUID, fertilizer_name: str, dosage: str, reason: str
    ) -> FertilizerRecommendation:
        item = FertilizerRecommendation(
            recommendation_id=recommendation_id,
            fertilizer_name=fertilizer_name,
            dosage=dosage,
            reason=reason,
        )
        self.db.add(item)
        self.db.commit()
        self.db.refresh(item)
        return item

    def delete_for_recommendation(self, recommendation_id: uuid.UUID) -> None:
        """Clears any prior fertilizer recs before regenerating (idempotent POST)."""
        for item in self.list_for_recommendation(recommendation_id):
            self.db.delete(item)
        self.db.commit()
