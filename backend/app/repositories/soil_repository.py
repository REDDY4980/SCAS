"""Soil report repository — pure CRUD, no business logic (AIB v1.0 Vol 12.6)."""

import uuid

from sqlalchemy.orm import Session

from app.models.soil import SoilParameters, SoilReport


class SoilRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_report_by_id(self, report_id: uuid.UUID) -> SoilReport | None:
        return self.db.get(SoilReport, report_id)

    def create_report(
        self, *, farm_id: uuid.UUID, file_path: str, file_type: str
    ) -> SoilReport:
        report = SoilReport(
            farm_id=farm_id, file_path=file_path, file_type=file_type, ocr_status="pending"
        )
        self.db.add(report)
        self.db.commit()
        self.db.refresh(report)
        return report

    def update_ocr_status(
        self, report: SoilReport, *, status: str, confidence: float | None
    ) -> SoilReport:
        report.ocr_status = status
        report.ocr_confidence = confidence
        self.db.commit()
        self.db.refresh(report)
        return report

    def update_file_path(self, report: SoilReport, *, file_path: str) -> SoilReport:
        report.file_path = file_path
        self.db.commit()
        self.db.refresh(report)
        return report

    def get_latest_validated_for_farm(self, farm_id) -> SoilReport | None:
        """Vol 10.4: recommendation requires validated soil parameters.
        Returns the most recent soil report for a farm whose OCR status
        is 'success' (auto-validated) or that has been manually
        corrected (also 'success' post-correction — see soil_service)."""
        from sqlalchemy import select

        return self.db.execute(
            select(SoilReport)
            .where(SoilReport.farm_id == farm_id, SoilReport.ocr_status == "success")
            .order_by(SoilReport.uploaded_at.desc())
            .limit(1)
        ).scalar_one_or_none()

    def upsert_parameters(self, report: SoilReport, **fields) -> SoilParameters:
        existing = report.soil_parameters
        if existing is not None:
            for key, value in fields.items():
                if value is not None:
                    setattr(existing, key, value)
            self.db.commit()
            self.db.refresh(existing)
            return existing

        params = SoilParameters(report_id=report.id, **fields)
        self.db.add(params)
        self.db.commit()
        self.db.refresh(params)
        return params
