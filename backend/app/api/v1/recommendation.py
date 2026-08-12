"""Recommendation routes — AIB v1.0 Vol 14.2 (POST /recommendation, GET /recommendation/{id})."""

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.dependencies.auth import get_current_user
from app.models.user import User
from app.repositories.farm_repository import FarmRepository
from app.repositories.recommendation_repository import RecommendationRepository
from app.repositories.soil_repository import SoilRepository
from app.repositories.weather_repository import WeatherRepository
from app.schemas.common import success_response
from app.services.recommendation_service import RecommendationService

router = APIRouter(prefix="/recommendation", tags=["Hybrid Crop Recommendation"])


def _service(db: Session = Depends(get_db)) -> RecommendationService:
    return RecommendationService(
        FarmRepository(db), SoilRepository(db), WeatherRepository(db), RecommendationRepository(db)
    )


@router.post("")
def generate_recommendation(
    farm_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    service: RecommendationService = Depends(_service),
):
    result = service.generate(current_user, farm_id)
    return success_response("Crop recommendation generated.", result.model_dump(mode="json"))


@router.get("/{recommendation_id}")
def get_recommendation(
    recommendation_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    service: RecommendationService = Depends(_service),
):
    result = service.get_by_id(current_user, recommendation_id)
    return success_response("Recommendation retrieved.", result.model_dump(mode="json"))
