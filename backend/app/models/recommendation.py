"""
Recommendation and FertilizerRecommendation entities.

AIB v1.0 Vol 5.3 `recommendations` / `fertilizer_recommendations` tables.
AIB v1.0 Vol 10 (Hybrid Crop Recommendation Engine) writes Recommendation.
AIB v1.0 Vol 11 (Fertilizer Recommendation Engine) writes FertilizerRecommendation,
one Recommendation -> many FertilizerRecommendations (Vol 5.4).
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, Float, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class Recommendation(Base):
    __tablename__ = "recommendations"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    farm_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("farms.id", ondelete="CASCADE"), nullable=False, index=True
    )
    report_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("soil_reports.id", ondelete="SET NULL"), nullable=True, index=True
    )
    weather_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("weather_snapshots.id", ondelete="SET NULL"), nullable=True
    )
    recommended_crop: Mapped[str] = mapped_column(String(100), nullable=False)
    confidence_score: Mapped[float] = mapped_column(Float, nullable=False)
    reasoning: Mapped[str] = mapped_column(Text, nullable=False)
    # Python-side default (microsecond precision) rather than relying
    # solely on server_default=func.now(): SQLite's CURRENT_TIMESTAMP
    # only has 1-second resolution, which made two Recommendations
    # created in rapid succession (e.g. in a test, or a farmer running
    # back-to-back analyses) tie on created_at and made "most recent
    # first" ordering non-deterministic. PostgreSQL's now() already has
    # microsecond precision, so this only changes behavior for SQLite
    # (dev/test), but the fix is correct and harmless for both.
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
        index=True,
    )

    farm: Mapped["Farm"] = relationship(back_populates="recommendations")
    report: Mapped["SoilReport"] = relationship(back_populates="recommendations")
    weather: Mapped["WeatherSnapshot"] = relationship(back_populates="recommendations")
    fertilizer_recommendations: Mapped[list["FertilizerRecommendation"]] = relationship(
        back_populates="recommendation", cascade="all, delete-orphan"
    )


class FertilizerRecommendation(Base):
    __tablename__ = "fertilizer_recommendations"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    recommendation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("recommendations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    fertilizer_name: Mapped[str] = mapped_column(String(150), nullable=False)
    # Text, not String(150): the fallback path's dosage value is a full
    # explanatory sentence ("Dosage not available — no source-traceable
    # ... consult a local agricultural extension officer..."), not a
    # short "N kg/ha" figure — see FertilizerSelector._fallback_recommendation.
    dosage: Mapped[str] = mapped_column(Text, nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)

    recommendation: Mapped["Recommendation"] = relationship(
        back_populates="fertilizer_recommendations"
    )
