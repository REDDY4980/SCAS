"""Farm management routes — AIB v1.0 Vol 14.2 (/farms), Vol 6.5, Vol 6.10."""

import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.dependencies.auth import get_current_user
from app.models.user import User
from app.repositories.farm_repository import FarmRepository
from app.schemas.common import success_response
from app.schemas.farm import FarmCreate, FarmUpdate
from app.services.farm_service import FarmService

router = APIRouter(prefix="/farms", tags=["Farm Management"])


def _service(db: Session = Depends(get_db)) -> FarmService:
    return FarmService(FarmRepository(db))


@router.post("", status_code=status.HTTP_201_CREATED)
def create_farm(
    payload: FarmCreate,
    current_user: User = Depends(get_current_user),
    service: FarmService = Depends(_service),
):
    farm = service.create_farm(current_user, payload)
    return success_response("Farm created.", farm.model_dump(mode="json"))


@router.get("")
def list_farms(
    current_user: User = Depends(get_current_user),
    service: FarmService = Depends(_service),
):
    farms = service.list_farms(current_user)
    return success_response(
        "Farms retrieved.", [f.model_dump(mode="json") for f in farms]
    )


@router.get("/{farm_id}")
def get_farm(
    farm_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    service: FarmService = Depends(_service),
):
    farm = service.get_farm(current_user, farm_id)
    return success_response("Farm retrieved.", farm.model_dump(mode="json"))


@router.put("/{farm_id}")
def update_farm(
    farm_id: uuid.UUID,
    payload: FarmUpdate,
    current_user: User = Depends(get_current_user),
    service: FarmService = Depends(_service),
):
    farm = service.update_farm(current_user, farm_id, payload)
    return success_response("Farm updated.", farm.model_dump(mode="json"))


@router.delete("/{farm_id}", status_code=status.HTTP_200_OK)
def delete_farm(
    farm_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    service: FarmService = Depends(_service),
):
    service.delete_farm(current_user, farm_id)
    return success_response("Farm deleted.", None)
