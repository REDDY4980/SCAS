"""Soil report routes — AIB v1.0 Vol 14.2 (/soil/upload, /soil/ocr, /soil/{id}, /soil/{id}/correct)."""

import uuid

from fastapi import APIRouter, Depends, File, UploadFile, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.dependencies.auth import get_current_user
from app.models.user import User
from app.repositories.farm_repository import FarmRepository
from app.repositories.soil_repository import SoilRepository
from app.schemas.common import success_response
from app.schemas.soil import SoilParametersCorrection
from app.services.soil_service import SoilService

router = APIRouter(prefix="/soil", tags=["Soil Report Processing"])


def _service(db: Session = Depends(get_db)) -> SoilService:
    return SoilService(SoilRepository(db), FarmRepository(db))


@router.post("/upload", status_code=status.HTTP_202_ACCEPTED)
def upload_soil_report(
    farm_id: uuid.UUID,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    service: SoilService = Depends(_service),
):
    result = service.upload_report(current_user, farm_id, file)
    return success_response("Soil report accepted for processing.", result.model_dump(mode="json"))


@router.post("/{report_id}/ocr")
def trigger_ocr(
    report_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    service: SoilService = Depends(_service),
):
    result = service.run_ocr(current_user, report_id)
    message = {
        "success": "OCR completed successfully.",
        "needs_review": "OCR completed but requires manual review.",
        "failed": "OCR failed validation. Please correct the values manually.",
    }.get(result.ocr_status, "OCR processing completed.")
    return success_response(message, result.model_dump(mode="json"))


@router.get("/{report_id}")
def get_soil_report(
    report_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    service: SoilService = Depends(_service),
):
    result = service.get_report(current_user, report_id)
    return success_response("Soil report retrieved.", result.model_dump(mode="json"))


@router.put("/{report_id}/correct")
def correct_soil_report(
    report_id: uuid.UUID,
    payload: SoilParametersCorrection,
    current_user: User = Depends(get_current_user),
    service: SoilService = Depends(_service),
):
    result = service.correct_parameters(current_user, report_id, payload)
    return success_response("Soil report values corrected.", result.model_dump(mode="json"))
