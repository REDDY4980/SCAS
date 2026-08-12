"""Fertilizer routes — AIB v1.0 Vol 11.11, Vol 2.3 FM-09."""

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.dependencies.auth import get_current_user
from app.models.user import User
from app.repositories.farm_repository import FarmRepository
from app.repositories.fertilizer_repository import FertilizerRepository
from app.repositories.recommendation_repository import RecommendationRepository
from app.repositories.soil_repository import SoilRepository
from app.schemas.common import success_response
from app.services.fertilizer_service import FertilizerService

router = APIRouter(prefix="/fertilizer", tags=["Fertilizer Recommendation"])


def _service(db: Session = Depends(get_db)) -> FertilizerService:
    return FertilizerService(
        RecommendationRepository(db), FarmRepository(db), SoilRepository(db), FertilizerRepository(db)
    )


@router.post("/{recommendation_id}")
def generate_fertilizer_recommendation(
    recommendation_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    service: FertilizerService = Depends(_service),
):
    result = service.generate(current_user, recommendation_id)
    return success_response("Fertilizer recommendation generated.", result.model_dump(mode="json"))


@router.get("/{recommendation_id}")
def get_fertilizer_recommendation(
    recommendation_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    service: FertilizerService = Depends(_service),
):
    result = service.get(current_user, recommendation_id)
    return success_response("Fertilizer recommendation retrieved.", result.model_dump(mode="json"))
