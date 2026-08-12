"""Farm schemas — AIB v1.0 Vol 14.2 (/farms), Vol 5.3 `farms` table."""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field

_COORDINATE_FIELD_DESCRIPTION = (
    "Not a user-facing form field — farmers never see or type coordinates. "
    "Supplied silently by the client from device GPS when permission is "
    "granted; if omitted, FarmService automatically resolves approximate "
    "coordinates from district/state via geocoding."
)


class FarmCreate(BaseModel):
    farm_name: str = Field(..., min_length=2, max_length=150)
    state: str = Field(..., min_length=2, max_length=100)
    district: str = Field(..., min_length=2, max_length=100)
    village: str | None = Field(default=None, max_length=150)
    latitude: float | None = Field(
        default=None, ge=-90, le=90, description=_COORDINATE_FIELD_DESCRIPTION
    )
    longitude: float | None = Field(
        default=None, ge=-180, le=180, description=_COORDINATE_FIELD_DESCRIPTION
    )
    soil_type: str | None = Field(default=None, max_length=50)
    area_acres: float | None = Field(default=None, gt=0)


class FarmUpdate(BaseModel):
    farm_name: str | None = Field(default=None, min_length=2, max_length=150)
    state: str | None = Field(default=None, min_length=2, max_length=100)
    district: str | None = Field(default=None, min_length=2, max_length=100)
    village: str | None = Field(default=None, max_length=150)
    latitude: float | None = Field(
        default=None, ge=-90, le=90, description=_COORDINATE_FIELD_DESCRIPTION
    )
    longitude: float | None = Field(
        default=None, ge=-180, le=180, description=_COORDINATE_FIELD_DESCRIPTION
    )
    soil_type: str | None = Field(default=None, max_length=50)
    area_acres: float | None = Field(default=None, gt=0)


class FarmOut(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    farm_name: str
    state: str
    district: str
    village: str | None
    latitude: float | None
    longitude: float | None
    soil_type: str | None
    area_acres: float | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
