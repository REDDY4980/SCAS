"""History schemas — AIB v1.0 Vol 14.2 (/history, /history/{id}), Vol 3 SCR-010."""

import uuid
from datetime import datetime

from pydantic import BaseModel


class HistorySummaryOut(BaseModel):
    id: uuid.UUID
    farm_id: uuid.UUID
    farm_name: str
    recommended_crop: str
    confidence_score: float
    created_at: datetime


class SoilParametersSnapshot(BaseModel):
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


class WeatherSnapshotSummary(BaseModel):
    temperature: float | None = None
    humidity: float | None = None
    rainfall: float | None = None
    wind_speed: float | None = None
    captured_at: datetime | None = None


class FertilizerHistoryItem(BaseModel):
    fertilizer_name: str
    dosage: str
    reason: str


class HistoryDetailOut(BaseModel):
    id: uuid.UUID
    farm_id: uuid.UUID
    farm_name: str
    recommended_crop: str
    confidence_score: float
    reasoning: str
    created_at: datetime
    soil_parameters: SoilParametersSnapshot | None
    weather: WeatherSnapshotSummary | None
    fertilizer_recommendations: list[FertilizerHistoryItem]
