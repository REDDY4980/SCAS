"""Auth routes — AIB v1.0 Vol 14.2 (/auth/register, /auth/login, /auth/me)."""

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.dependencies.auth import get_current_user
from app.models.user import User
from app.repositories.user_repository import UserRepository
from app.schemas.auth import TokenResponse, UserLogin, UserOut, UserRegister
from app.schemas.common import success_response
from app.services.auth_service import AuthenticationService

router = APIRouter(prefix="/auth", tags=["Authentication"])


def _service(db: Session = Depends(get_db)) -> AuthenticationService:
    return AuthenticationService(UserRepository(db))


@router.post("/register", status_code=status.HTTP_201_CREATED)
def register(payload: UserRegister, service: AuthenticationService = Depends(_service)):
    user = service.register(payload)
    return success_response("Account created successfully.", user.model_dump(mode="json"))


@router.post("/login")
def login(payload: UserLogin, service: AuthenticationService = Depends(_service)):
    token = service.login(payload.identifier, payload.password)
    return success_response("Login successful.", token.model_dump(mode="json"))


@router.get("/me")
def me(current_user: User = Depends(get_current_user)):
    return success_response(
        "Current user profile.", UserOut.model_validate(current_user).model_dump(mode="json")
    )
