"""
Model registry.

AIB v1.0 Vol 5.3 — importing this package guarantees every ORM model is
registered on `Base.metadata`, which Alembic autogenerate and
`Base.metadata.create_all()` (tests) both rely on.
"""

from app.models.base import Base  # noqa: F401
from app.models.user import User  # noqa: F401
from app.models.farm import Farm  # noqa: F401
from app.models.soil import SoilReport, SoilParameters  # noqa: F401
from app.models.weather import WeatherSnapshot  # noqa: F401
from app.models.recommendation import (  # noqa: F401
    Recommendation,
    FertilizerRecommendation,
)
from app.models.user_settings import UserSettings  # noqa: F401

__all__ = [
    "Base",
    "User",
    "Farm",
    "SoilReport",
    "SoilParameters",
    "WeatherSnapshot",
    "Recommendation",
    "FertilizerRecommendation",
    "UserSettings",
]
