"""
SoilService — orchestrates the upload -> preprocess -> OCR -> layout ->
parse -> validate -> persist pipeline.

AIB v1.0 Vol 7.3 (OCR Architecture), Vol 7.11 (Failure Recovery),
Vol 7.16 ("Keep OCR, parsing and validation as separate services. Only
validated JSON may enter the Feature Engineering pipeline.").
Vol 12.9 (File Upload Pipeline: validate MIME type -> store -> trigger
OCR -> persist metadata -> return tracking ID).
"""

from __future__ import annotations

import logging
import threading
import time
import uuid
from contextlib import contextmanager
from pathlib import Path

from fastapi import HTTPException, UploadFile, status

from app.core.config import get_settings
from app.models.farm import Farm
from app.models.user import User
from app.ocr import field_parser, layout, preprocessing, validation
from app.ocr.engine import (
    OCRBusyError,
    OCREngine,
    OCRInitializationError,
    get_ocr_engine,
    ocr_slot,
)
from app.repositories.farm_repository import FarmRepository
from app.repositories.soil_repository import SoilRepository
from app.schemas.soil import (
    OCRTriggerOut,
    SoilParametersCorrection,
    SoilParametersOut,
    SoilReportOut,
    SoilReportUploadOut,
)

logger = logging.getLogger("scas.services.soil")

_ALLOWED_EXTENSIONS = {".pdf", ".jpg", ".jpeg", ".png"}
_ALLOWED_CONTENT_TYPES = {"application/pdf", "image/jpeg", "image/png", "image/jpg"}

# Vol 5.3 soil_parameters columns. field_parser recognizes a few extra
# fields real reports carry (e.g. sulphur) that have no column in the
# schema — those are surfaced in logs/warnings but never passed to the
# repository, which would otherwise raise a TypeError on an unknown
# ORM constructor kwarg.
_PERSISTABLE_FIELDS = {
    "ph",
    "ec",
    "organic_carbon",
    "nitrogen",
    "phosphorus",
    "potassium",
    "zinc",
    "iron",
    "manganese",
    "copper",
    "boron",
}


# Report ids with an OCR run in progress in THIS process. In-memory on
# purpose: the backend runs a single Uvicorn worker (entrypoint.sh), and if
# the process dies mid-run the set is empty again on restart, so the
# report — left in `processing` in the database — can simply be retried.
_in_flight: set[uuid.UUID] = set()
_in_flight_lock = threading.Lock()


@contextmanager
def _in_flight_guard(report_id: uuid.UUID):
    with _in_flight_lock:
        if report_id in _in_flight:
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                "This soil report is already being processed. Please wait for it to finish.",
            )
        _in_flight.add(report_id)
    try:
        yield
    finally:
        with _in_flight_lock:
            _in_flight.discard(report_id)


class SoilService:
    def __init__(
        self,
        soil_repo: SoilRepository,
        farm_repo: FarmRepository,
        ocr_engine: OCREngine | None = None,
    ):
        self.soil_repo = soil_repo
        self.farm_repo = farm_repo
        # Lazily resolved so importing this service never forces a
        # PaddleOCR model load; only actually running OCR does.
        self._ocr_engine = ocr_engine

    def _engine(self) -> OCREngine:
        if self._ocr_engine is None:
            self._ocr_engine = get_ocr_engine()
        return self._ocr_engine

    def _get_owned_farm_or_404(self, user: User, farm_id: uuid.UUID) -> Farm:
        farm = self.farm_repo.get_by_id(farm_id)
        if farm is None or farm.user_id != user.id:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Farm not found.")
        return farm

    def _get_owned_report_or_404(self, user: User, report_id: uuid.UUID):
        report = self.soil_repo.get_report_by_id(report_id)
        if report is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Soil report not found.")
        # Ownership flows through the report's farm (Vol 6.10).
        self._get_owned_farm_or_404(user, report.farm_id)
        return report

    def upload_report(self, user: User, farm_id: uuid.UUID, file: UploadFile) -> SoilReportUploadOut:
        self._get_owned_farm_or_404(user, farm_id)

        settings = get_settings()
        original_name = file.filename or "upload"
        extension = Path(original_name).suffix.lower()

        # AIB Vol 3 SCR-006 acceptance criterion: "Accept only JPG, PNG, PDF."
        if extension not in _ALLOWED_EXTENSIONS or (
            file.content_type and file.content_type not in _ALLOWED_CONTENT_TYPES
        ):
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                "Unsupported file type. Only PDF, JPG and PNG are accepted.",
            )

        contents = file.file.read()
        size_mb = len(contents) / (1024 * 1024)
        if size_mb > settings.max_upload_size_mb:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                f"File exceeds the {settings.max_upload_size_mb}MB upload limit.",
            )
        if size_mb == 0:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Uploaded file is empty.")

        # Create the DB row first so we use its real, database-generated
        # id for the on-disk filename — reassigning `.id` after commit
        # would NOT rewrite the already-persisted primary key, so the id
        # used for the filename must come from the committed row, not be
        # invented beforehand.
        report = self.soil_repo.create_report(
            farm_id=farm_id, file_path="", file_type=extension.lstrip(".")
        )

        upload_dir = Path(settings.upload_directory)
        upload_dir.mkdir(parents=True, exist_ok=True)
        stored_path = upload_dir / f"{report.id}{extension}"
        stored_path.write_bytes(contents)

        # Vol 7.16: preserve the original uploaded file for audit — we
        # never overwrite/discard it, even after OCR runs.
        report = self.soil_repo.update_file_path(report, file_path=str(stored_path))

        return SoilReportUploadOut(
            report_id=report.id,
            farm_id=farm_id,
            ocr_status=report.ocr_status,
            message="Soil report uploaded successfully. Trigger OCR processing next.",
        )

    def run_ocr(self, user: User, report_id: uuid.UUID) -> OCRTriggerOut:
        """
        Runs OCR on a stored report, one page at a time (see
        docs/OCR_MEMORY_REPORT.md):

        * a second OCR request for a report that is already being processed
          gets 409 instead of a duplicate run (double-taps/client retries
          would otherwise double peak memory);
        * at most OCR_MAX_CONCURRENT documents are processed at once —
          beyond that, requests wait up to OCR_QUEUE_TIMEOUT_SECONDS, then 503;
        * each page is rendered -> pre-processed -> OCR'd -> reduced to text
          lines and released before the next page is rendered;
        * any failure leaves the report in `failed` (never stuck in
          `processing`), the original upload is untouched, and the same
          report id can simply be retried.
        """
        report = self._get_owned_report_or_404(user, report_id)

        with _in_flight_guard(report.id):
            try:
                with ocr_slot():
                    return self._run_ocr_pipeline(report)
            except OCRBusyError as exc:
                raise HTTPException(
                    status.HTTP_503_SERVICE_UNAVAILABLE,
                    "The soil report reader is busy with another report. Please try again in a minute.",
                ) from exc

    def _run_ocr_pipeline(self, report) -> OCRTriggerOut:
        report_id = report.id
        self.soil_repo.update_ocr_status(report, status="processing", confidence=report.ocr_confidence)

        start = time.monotonic()
        all_lines: list[str] = []
        confidences: list[float] = []
        page_count = 0
        try:
            engine = self._engine()
            for image in preprocessing.iter_preprocessed_pages(report.file_path):
                page_result = engine.extract(image)
                del image  # release the page before the next one is rendered
                page_count += 1
                confidences.append(page_result.average_confidence)
                all_lines.extend(layout.reconstruct_rows(page_result))
                del page_result
        except preprocessing.DocumentError as exc:
            logger.warning("Document rejected for report %s: %s", report_id, exc)
            self.soil_repo.update_ocr_status(report, status="failed", confidence=None)
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, exc.user_message) from exc
        except OCRInitializationError as exc:
            logger.exception("OCR engine could not be initialised (report %s)", report_id)
            self.soil_repo.update_ocr_status(report, status="failed", confidence=None)
            raise HTTPException(
                status.HTTP_503_SERVICE_UNAVAILABLE,
                "The soil report reader is temporarily unavailable. Please try again later, "
                "or enter the soil values manually.",
            ) from exc
        except Exception as exc:
            logger.exception("OCR failed for report %s after %d page(s)", report_id, page_count)
            self.soil_repo.update_ocr_status(report, status="failed", confidence=None)
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                "Could not read the uploaded report. Please re-upload a clearer scan or photo, "
                "or enter the soil values manually.",
            ) from exc

        overall_confidence = sum(confidences) / len(confidences) if confidences else 0.0

        parsed = field_parser.parse_lines(all_lines)
        persistable_values = {
            k: v for k, v in parsed.values.items() if k in _PERSISTABLE_FIELDS
        }
        skipped_fields = set(parsed.values) - _PERSISTABLE_FIELDS
        if skipped_fields:
            logger.info(
                "Report %s: parsed but not persisted (no schema column): %s",
                report_id,
                sorted(skipped_fields),
            )
        if parsed.conflicts:
            logger.info(
                "Report %s: conflicting readings for %s -> manual review",
                report_id,
                sorted(parsed.conflicts),
            )
        result = validation.validate_soil_values(
            persistable_values, overall_confidence, conflicting_values=parsed.conflicts
        )

        elapsed = time.monotonic() - start
        logger.info(
            "OCR pipeline for report %s: status=%s confidence=%.2f elapsed=%.2fs pages=%d fields=%d",
            report_id,
            result.status,
            overall_confidence,
            elapsed,
            page_count,
            len(persistable_values),
        )

        params = None
        if persistable_values:
            params = self.soil_repo.upsert_parameters(report, **persistable_values)

        self.soil_repo.update_ocr_status(report, status=result.status, confidence=overall_confidence)

        return OCRTriggerOut(
            report_id=report.id,
            ocr_status=result.status,
            ocr_confidence=overall_confidence,
            soil_parameters=SoilParametersOut.model_validate(params) if params else None,
            warnings=result.warnings,
            missing_fields=result.missing_core_fields,
        )

    def correct_parameters(
        self, user: User, report_id: uuid.UUID, corrections: SoilParametersCorrection
    ) -> SoilReportOut:
        report = self._get_owned_report_or_404(user, report_id)
        fields = {k: v for k, v in corrections.model_dump().items() if v is not None}
        if not fields:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "No correction values supplied.")

        params = self.soil_repo.upsert_parameters(report, **fields)
        # A human has now verified/corrected the values — treat as fully
        # validated regardless of the original OCR confidence, but ONLY if
        # every mandatory parameter is now present. An incomplete report
        # must never become `success`: recommendations use the farm's latest
        # successful report, so it would also hide an earlier complete one.
        missing = [f for f in validation.CORE_MANDATORY_FIELDS if getattr(params, f) is None]
        if missing:
            updated_report = self.soil_repo.update_ocr_status(
                report, status="needs_review", confidence=report.ocr_confidence
            )
        else:
            updated_report = self.soil_repo.update_ocr_status(report, status="success", confidence=1.0)
        return SoilReportOut.model_validate(updated_report)

    def get_report(self, user: User, report_id: uuid.UUID) -> SoilReportOut:
        report = self._get_owned_report_or_404(user, report_id)
        return SoilReportOut.model_validate(report)
