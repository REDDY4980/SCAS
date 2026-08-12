"""
SQLAlchemy declarative base.

AIB v1.0 Vol 5 (Database Engineering). Entity models (User, Farm,
SoilReport, SoilParameters, WeatherSnapshot, Recommendation,
FertilizerRecommendation, UserSettings) are implemented in Phase 2
per the AIB Vol 17 phase plan and imported here so Alembic autogenerate
can discover them via Base.metadata.
"""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


# NOTE: model modules are intentionally NOT imported here. Each model
# module does `from app.models.base import Base`, so importing them from
# this file would create a circular import. All models are instead
# collected in app/models/__init__.py — import `app.models` (the package)
# when you need Base.metadata to be fully populated (e.g. Alembic).
