"""User profile routes — AIB v1.0 Vol 14.2 (PUT /users/profile)."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.dependencies.auth import get_current_user
from app.models.user import User
from app.repositories.user_repository import UserRepository
from app.schemas.auth import ProfileUpdate
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
