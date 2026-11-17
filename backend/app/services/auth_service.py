"""
AuthenticationService — business logic for registration, login and profile.

AIB v1.0 Vol 6.13 — implement authentication before any business module;
never expose password hashes; never trust client-side validation alone.
"""

from fastapi import HTTPException, status

from app.core.security import create_access_token, hash_password, verify_password
from app.core.config import get_settings
from app.models.user import User
from app.repositories.user_repository import UserRepository
from app.schemas.auth import ProfileOut, ProfileUpdate, TokenResponse, UserOut, UserRegister

settings = get_settings()


class AuthenticationService:
    def __init__(self, repo: UserRepository):
        self.repo = repo

    def register(self, payload: UserRegister) -> UserOut:
        if self.repo.get_by_email(payload.email) is not None:
            raise HTTPException(
                status.HTTP_409_CONFLICT, "An account with this email already exists."
            )
        if self.repo.get_by_phone(payload.phone) is not None:
            raise HTTPException(
                status.HTTP_409_CONFLICT, "An account with this phone number already exists."
            )

        user = self.repo.create(
            full_name=payload.full_name,
            email=payload.email,
            phone=payload.phone,
            password_hash=hash_password(payload.password),
        )
        return UserOut.model_validate(user)

    def login(self, identifier: str, password: str) -> TokenResponse:
        user = self.repo.get_by_email_or_phone(identifier)
        if user is None or not verify_password(password, user.password_hash):
            # Deliberately identical error for unknown user vs wrong password
            # (AIB Vol 6.11) — never reveal which part was wrong.
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid credentials.")

        token = create_access_token(user.id)
        return TokenResponse(
            access_token=token,
            expires_in_minutes=settings.jwt_expire_minutes,
            user=UserOut.model_validate(user),
        )

    def _build_profile_out(self, user: User) -> ProfileOut:
        settings_row = self.repo.get_settings(user.id)
        return ProfileOut(
            id=user.id,
            full_name=user.full_name,
            email=user.email,
            phone=user.phone,
            created_at=user.created_at,
            language=settings_row.language if settings_row else "en",
            theme=settings_row.theme if settings_row else "system",
            notifications=settings_row.notifications if settings_row else True,
            latitude=float(user.latitude) if user.latitude is not None else None,
            longitude=float(user.longitude) if user.longitude is not None else None,
            location_accuracy_m=user.location_accuracy_m,
            location_source=user.location_source,
            location_updated_at=user.location_updated_at,
        )

    def get_current_user_profile(self, user: User) -> ProfileOut:
        return self._build_profile_out(user)

    def update_profile(self, user: User, payload: ProfileUpdate) -> ProfileOut:
        updated = self.repo.update_profile(user, full_name=payload.full_name)

        settings_row = self.repo.get_settings(user.id)
        if settings_row is not None and (
            payload.language is not None
            or payload.theme is not None
            or payload.notifications is not None
        ):
            self.repo.update_settings(
                settings_row,
                language=payload.language,
                theme=payload.theme,
                notifications=payload.notifications,
            )

        return self._build_profile_out(updated)
