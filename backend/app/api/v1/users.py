"""User profile routes — AIB v1.0 Vol 14.2 (PUT /users/profile)."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.dependencies.auth import get_current_user
from app.models.user import User
from app.repositories.user_repository import UserRepository
from app.repositories.farm_repository import FarmRepository
from app.schemas.auth import LocationUpdate, ProfileUpdate
from app.services.farm_service import FarmService
from app.schemas.common import success_response
from app.services.auth_service import AuthenticationService

router = APIRouter(prefix="/users", tags=["User Profile"])


def _service(db: Session = Depends(get_db)) -> AuthenticationService:
    return AuthenticationService(UserRepository(db))


@router.put("/profile")
def update_profile(
    payload: ProfileUpdate,
    current_user: User = Depends(get_current_user),
    service: AuthenticationService = Depends(_service),
):
    updated = service.update_profile(current_user, payload)
    return success_response("Profile updated.", updated.model_dump(mode="json"))


@router.get("/profile")
def get_profile(
    current_user: User = Depends(get_current_user),
    service: AuthenticationService = Depends(_service),
):
    result = service.get_current_user_profile(current_user)
    return success_response("Profile retrieved.", result.model_dump(mode="json"))


@router.put("/location")
def update_location(
    payload: LocationUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Save the device's detected location on the farmer profile and,
    if `apply_to_farm_id` is given, use it as that farm's GPS position."""
    farm = None
    if payload.apply_to_farm_id is not None:
        farm = FarmService(FarmRepository(db)).apply_device_location(
            current_user, payload.apply_to_farm_id, latitude=payload.latitude,
            longitude=payload.longitude, accuracy_m=payload.accuracy_m,
        )
    UserRepository(db).update_location(
        current_user, latitude=payload.latitude, longitude=payload.longitude,
        accuracy_m=payload.accuracy_m, source="gps",
    )
    profile = AuthenticationService(UserRepository(db)).get_current_user_profile(current_user)
    data = {"profile": profile.model_dump(mode="json"), "farm": farm.model_dump(mode="json") if farm else None}
    return success_response("Location saved.", data)
