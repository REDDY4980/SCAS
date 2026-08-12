"""
SCAS Backend — FastAPI application entrypoint.

AIB v1.0 Vol 12 (Backend Engineering) / Vol 16 (Deployment Architecture).

Phase 1 (AIB Vol 17.3): project skeleton, configuration, logging,
standardized error handling and a health endpoint.
Phase 2 (AIB Vol 17.3 "Authentication & Database"): JWT auth, farm
management and the underlying ORM/repository/service layers are now
mounted via `api_router`. Remaining modules (OCR, Weather, ML,
Fertilizer, History) are implemented in their own later phases.
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from sqlalchemy import text

from app.api.v1.router import api_router
from app.core.config import get_settings
from app.core.database import engine
from app.core.exception_handlers import register_exception_handlers
from app.core.logging_config import configure_logging
from app.ocr.engine import get_ocr_engine
from app.schemas.common import success_response

configure_logging()
logger = logging.getLogger("scas.startup")

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Fail-fast startup checks (AIB Vol 16.12).

    Settings validation already occurred at import time via get_settings().
    Phase 2 adds every business route on top of the database, so we now
    also verify the database is reachable before accepting traffic.
    Model-artifact checks are added when Phase 6 (ML) lands.

    Note for tests: TestClient only runs this lifespan when used as a
    context manager (`with TestClient(app) as client:`). Route-level
    tests in this repo construct TestClient directly and therefore
    intentionally skip this block — they exercise the app against an
    overridden, in-memory test database instead (see tests/conftest.py).
    """
    logger.info(
        "SCAS backend starting | environment=%s | log_level=%s",
        settings.environment,
        settings.log_level,
    )
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        logger.info("Database connectivity verified.")
    except Exception:
        logger.exception(
            "Database is unreachable at startup. Failing fast per AIB Vol 16.12."
        )
        raise

    # Warm up PaddleOCR now, inside this actual server process, rather
    # than paying its model-load cost on whichever farmer's upload
    # happens to be the first request after startup — see
    # app/ocr/engine.py's warm_up() docstring for why this specifically
    # cannot be done as a separate subprocess (Dockerfile RUN /
    # entrypoint.sh step) instead. Best-effort: must not block startup
    # on a transient failure, since app/ocr/engine.py's own lazy-load
    # still runs on the first real request either way.
    try:
        get_ocr_engine().warm_up()
        logger.info("OCR engine warmed up.")
    except Exception:
        logger.exception("OCR engine warm-up failed (non-fatal) — will load lazily on first request.")

    yield
    logger.info("SCAS backend shutting down.")


app = FastAPI(
    title="Smart Crop Advisory System (SCAS) API",
    description="Hybrid AI Decision Support System backend — AIB v1.0",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

register_exception_handlers(app)
app.include_router(api_router)


@app.get("/health", tags=["System"])
async def health_check() -> dict:
    """Liveness/readiness probe (AIB Vol 16.8)."""
    return success_response(
        "SCAS backend is healthy",
        {
            "status": "ok",
            "environment": settings.environment,
        },
    )


@app.get("/", tags=["System"])
async def root() -> dict:
    return success_response(
        "Smart Crop Advisory System API",
        {"docs": "/docs", "health": "/health"},
    )
