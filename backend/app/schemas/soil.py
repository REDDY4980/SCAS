"""Soil report schemas — AIB v1.0 Vol 14.2 (/soil/*), Vol 7.9 JSON output contract."""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class SoilParametersOut(BaseModel):
    ph: float | None = None
    ec: float | None = None
    organic_carbon: float | None = None
    nitrogen: float | None = None
    phosphorus: float | None = None
    potassium: float | None = None
    zinc: float | None = None
    iron: float | None = None
    manganese: float | None = None
    copper: float | None = None
    boron: float | None = None

    model_config = {"from_attributes": True}


class SoilReportOut(BaseModel):
    id: uuid.UUID
    farm_id: uuid.UUID
    file_type: str
    ocr_status: str
    ocr_confidence: float | None
    uploaded_at: datetime
    soil_parameters: SoilParametersOut | None = None

    model_config = {"from_attributes": True}


class SoilReportUploadOut(BaseModel):
    report_id: uuid.UUID
    farm_id: uuid.UUID
    ocr_status: str
    message: str


class OCRTriggerOut(BaseModel):
    report_id: uuid.UUID
    ocr_status: str
    ocr_confidence: float
    soil_parameters: SoilParametersOut | None
    warnings: list[str] = Field(default_factory=list)
    missing_fields: list[str] = Field(default_factory=list)


class SoilParametersCorrection(BaseModel):
    """Manual correction payload — AIB Vol 7.10 PUT /soil/{report_id}/correct."""

    ph: float | None = Field(default=None, ge=0, le=14)
    ec: float | None = Field(default=None, ge=0)
    organic_carbon: float | None = Field(default=None, ge=0)
    nitrogen: float | None = Field(default=None, ge=0)
    phosphorus: float | None = Field(default=None, ge=0)
    potassium: float | None = Field(default=None, ge=0)
    zinc: float | None = Field(default=None, ge=0)
    iron: float | None = Field(default=None, ge=0)
    manganese: float | None = Field(default=None, ge=0)
    copper: float | None = Field(default=None, ge=0)
    boron: float | None = Field(default=None, ge=0)
