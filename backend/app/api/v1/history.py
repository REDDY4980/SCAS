"""History routes — AIB v1.0 Vol 14.2 (GET /history, GET /history/{id})."""

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.dependencies.auth import get_current_user
from app.models.user import User
from app.repositories.farm_repository import FarmRepository
from app.repositories.recommendation_repository import RecommendationRepository
from app.schemas.common import success_response
from app.services.history_service import HistoryService

router = APIRouter(prefix="/history", tags=["Recommendation History"])


def _service(db: Session = Depends(get_db)) -> HistoryService:
    return HistoryService(RecommendationRepository(db), FarmRepository(db))


@router.get("")
def list_history(
    farm_id: uuid.UUID | None = None,
    limit: int = 50,
    current_user: User = Depends(get_current_user),
    service: HistoryService = Depends(_service),
):
    results = service.list_history(current_user, farm_id=farm_id, limit=limit)
    return success_response(
        "History retrieved.", [r.model_dump(mode="json") for r in results]
    )


@router.get("/{recommendation_id}")
def get_history_detail(
    recommendation_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    service: HistoryService = Depends(_service),
):
    result = service.get_detail(current_user, recommendation_id)
    return success_response("History detail retrieved.", result.model_dump(mode="json"))
