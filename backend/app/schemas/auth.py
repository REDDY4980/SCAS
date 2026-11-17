"""Authentication schemas — AIB v1.0 Vol 14.2 (/auth/*), Vol 6.6 validation rules."""

import re
import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field, field_validator

_PHONE_RE = re.compile(r"^\+?[0-9]{10,15}$")


class UserRegister(BaseModel):
    full_name: str = Field(..., min_length=2, max_length=150)
    email: EmailStr
    phone: str
    password: str = Field(..., min_length=8, max_length=128)

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v: str) -> str:
        if not _PHONE_RE.match(v):
            raise ValueError("Phone must be 10-15 digits, optionally prefixed with '+'")
        return v

    @field_validator("password")
    @classmethod
    def validate_password_strength(cls, v: str) -> str:
        if not re.search(r"[A-Za-z]", v) or not re.search(r"[0-9]", v):
            raise ValueError("Password must contain at least one letter and one number")
        return v


class UserLogin(BaseModel):
    """Accepts either email or phone in `identifier`."""

    identifier: str = Field(..., min_length=3)
    password: str = Field(..., min_length=1)


class UserOut(BaseModel):
    id: uuid.UUID
    full_name: str
    email: EmailStr
    phone: str
    created_at: datetime

    model_config = {"from_attributes": True}


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in_minutes: int
    user: UserOut


class ProfileUpdate(BaseModel):
    full_name: str | None = Field(default=None, min_length=2, max_length=150)
    language: str | None = Field(default=None, min_length=2, max_length=10)
    theme: str | None = Field(default=None, pattern="^(light|dark|system)$")
    notifications: bool | None = None


class ProfileOut(BaseModel):
    """Vol 6.9 full profile: identity fields + preferences."""

    id: uuid.UUID
    full_name: str
    email: EmailStr
    phone: str
    created_at: datetime
    language: str
    theme: str
    notifications: bool
    # Last detected device location (None until the app has detected it once).
    latitude: float | None = None
    longitude: float | None = None
    location_accuracy_m: float | None = None
    location_source: str | None = None
    location_updated_at: datetime | None = None

    model_config = {"from_attributes": True}


class LocationUpdate(BaseModel):
    """Device location sent by the app (GPS / browser geolocation)."""

    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)
    accuracy_m: float | None = Field(default=None, ge=0)
    # Optional: also use this position for one of the farmer's farms.
    apply_to_farm_id: uuid.UUID | None = None

    @field_validator("longitude")
    @classmethod
    def reject_null_island(cls, v: float, info) -> float:
        # (0, 0) is what broken location providers return; it is in the Atlantic.
        if v == 0 and info.data.get("latitude") == 0:
            raise ValueError("Location (0, 0) is not a valid device position")
        return v
