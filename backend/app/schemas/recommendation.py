"""Recommendation schemas — AIB v1.0 Vol 10.10 output contract, Vol 14.2 /recommendation."""

import uuid
from datetime import datetime

from pydantic import BaseModel


class CropRecommendationItem(BaseModel):
    crop: str
    confidence: float
    reason: str


class RecommendationOut(BaseModel):
    id: uuid.UUID | None = None
    farm_id: uuid.UUID
    primary_crop: str
    confidence: float
    explanation: str
    top_recommendations: list[CropRecommendationItem]
    model_version: str
    created_at: datetime | None = None
