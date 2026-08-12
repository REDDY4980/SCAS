"""Weather routes — AIB v1.0 Vol 14.2 (/weather/current, /weather/refresh, /weather/history/{farm_id})."""

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.dependencies.auth import get_current_user
from app.models.user import User
from app.repositories.farm_repository import FarmRepository
from app.repositories.weather_repository import WeatherRepository
from app.schemas.common import success_response
from app.services.weather_service import WeatherService

router = APIRouter(prefix="/weather", tags=["Climate Intelligence"])


def _service(db: Session = Depends(get_db)) -> WeatherService:
    return WeatherService(WeatherRepository(db), FarmRepository(db))


@router.get("/current")
def get_current_weather(
    farm_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    service: WeatherService = Depends(_service),
):
    result = service.get_current(current_user, farm_id)
    message = "Weather retrieved from cache." if result.cache_hit else "Weather retrieved and refreshed."
    return success_response(message, result.model_dump(mode="json"))


@router.post("/refresh")
def refresh_weather(
    farm_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    service: WeatherService = Depends(_service),
):
    result = service.refresh(current_user, farm_id)
    return success_response("Weather refreshed.", result.model_dump(mode="json"))


@router.get("/history/{farm_id}")
def get_weather_history(
    farm_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    service: WeatherService = Depends(_service),
):
    results = service.get_history(current_user, farm_id)
    return success_response("Weather history retrieved.", [r.model_dump(mode="json") for r in results])
