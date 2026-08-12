"""Fertilizer schemas — AIB v1.0 Vol 11.10 output contract."""

import uuid

from pydantic import BaseModel


class FertilizerRecommendationOut(BaseModel):
    fertilizer_name: str
    dosage: str
    target_nutrients: list[str]
    reason: str
    application_method: str
    precautions: str
    source: str = ""


class FertilizerResponseOut(BaseModel):
    recommendation_id: uuid.UUID
    crop: str
    deficiency_profile: dict[str, str]
    fertilizers: list[FertilizerRecommendationOut]
    knowledge_base_coverage: str
