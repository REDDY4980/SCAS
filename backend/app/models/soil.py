"""
SoilReport and SoilParameters entities.

AIB v1.0 Vol 5.3 `soil_reports` / `soil_parameters` tables.
AIB v1.0 Vol 7 — OCR pipeline populates these; one soil report has at
most one soil_parameters record (Vol 5.4: "One Soil Report -> One Soil
Parameter Record").
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class SoilReport(Base):
    __tablename__ = "soil_reports"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    farm_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("farms.id", ondelete="CASCADE"), nullable=False, index=True
    )
    file_path: Mapped[str] = mapped_column(String(500), nullable=False)
    file_type: Mapped[str] = mapped_column(String(10), nullable=False)  # pdf | jpg | png
    ocr_status: Mapped[str] = mapped_column(
        String(30), nullable=False, default="pending"
    )  # pending | processing | success | needs_review | failed
    ocr_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    farm: Mapped["Farm"] = relationship(back_populates="soil_reports")
    soil_parameters: Mapped["SoilParameters"] = relationship(
        back_populates="report", uselist=False, cascade="all, delete-orphan"
    )
    recommendations: Mapped[list["Recommendation"]] = relationship(back_populates="report")


class SoilParameters(Base):
    __tablename__ = "soil_parameters"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    report_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("soil_reports.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )

    ph: Mapped[float | None] = mapped_column(Float, nullable=True)
    ec: Mapped[float | None] = mapped_column(Float, nullable=True)
    organic_carbon: Mapped[float | None] = mapped_column(Float, nullable=True)
    nitrogen: Mapped[float | None] = mapped_column(Float, nullable=True)
    phosphorus: Mapped[float | None] = mapped_column(Float, nullable=True)
    potassium: Mapped[float | None] = mapped_column(Float, nullable=True)
    zinc: Mapped[float | None] = mapped_column(Float, nullable=True)
    iron: Mapped[float | None] = mapped_column(Float, nullable=True)
    manganese: Mapped[float | None] = mapped_column(Float, nullable=True)
    copper: Mapped[float | None] = mapped_column(Float, nullable=True)
    boron: Mapped[float | None] = mapped_column(Float, nullable=True)

    report: Mapped["SoilReport"] = relationship(back_populates="soil_parameters")
