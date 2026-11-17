"""User repository — pure CRUD, no business logic (AIB v1.0 Vol 12.6)."""

import uuid

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models.user import User
from app.models.user_settings import UserSettings


class UserRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, user_id: uuid.UUID) -> User | None:
        return self.db.get(User, user_id)

    def get_by_email(self, email: str) -> User | None:
        return self.db.execute(select(User).where(User.email == email)).scalar_one_or_none()

    def get_by_phone(self, phone: str) -> User | None:
        return self.db.execute(select(User).where(User.phone == phone)).scalar_one_or_none()

    def get_by_email_or_phone(self, identifier: str) -> User | None:
        return self.db.execute(
            select(User).where(or_(User.email == identifier, User.phone == identifier))
        ).scalar_one_or_none()

    def create(self, *, full_name: str, email: str, phone: str, password_hash: str) -> User:
        user = User(full_name=full_name, email=email, phone=phone, password_hash=password_hash)
        self.db.add(user)
        self.db.flush()

        # Every user gets default settings at creation time (Vol 5.3 user_settings).
        self.db.add(UserSettings(user_id=user.id))
        self.db.commit()
        self.db.refresh(user)
        return user

    def update_profile(self, user: User, *, full_name: str | None) -> User:
        if full_name is not None:
            user.full_name = full_name
        self.db.commit()
        self.db.refresh(user)
        return user

    def update_location(self, user: User, *, latitude: float, longitude: float,
                        accuracy_m: float | None, source: str) -> User:
        from datetime import datetime, timezone

        user.latitude = latitude
        user.longitude = longitude
        user.location_accuracy_m = accuracy_m
        user.location_source = source
        user.location_updated_at = datetime.now(timezone.utc)
        self.db.commit()
        self.db.refresh(user)
        return user

    def get_settings(self, user_id: uuid.UUID) -> UserSettings | None:
        return self.db.execute(
            select(UserSettings).where(UserSettings.user_id == user_id)
        ).scalar_one_or_none()

    def update_settings(
        self,
        settings_row: UserSettings,
        *,
        language: str | None,
        theme: str | None,
        notifications: bool | None,
    ) -> UserSettings:
        if language is not None:
            settings_row.language = language
        if theme is not None:
            settings_row.theme = theme
        if notifications is not None:
            settings_row.notifications = notifications
        self.db.commit()
        self.db.refresh(settings_row)
        return settings_row
