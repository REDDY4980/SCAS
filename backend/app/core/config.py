"""
SCAS centralized configuration.

AIB v1.0 Vol 16.12 — AI Builder Directive:
    "Validate environment variables at startup. Fail fast if critical
    services are unavailable."

All configuration is sourced from environment variables (Vol 16.5).
No secrets are hardcoded in source code (Vol 0.7 Rule 5).
"""

from functools import lru_cache
from typing import List, Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # --- Application ---
    environment: str = Field(default="development", alias="ENVIRONMENT")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    allowed_origins: str = Field(default="http://localhost", alias="ALLOWED_ORIGINS")

    # --- Security ---
    jwt_secret: str = Field(..., alias="JWT_SECRET")
    jwt_algorithm: str = Field(default="HS256", alias="JWT_ALGORITHM")
    jwt_expire_minutes: int = Field(default=1440, alias="JWT_EXPIRE_MINUTES")

    # --- Database ---
    database_url: str = Field(..., alias="DATABASE_URL")

    # --- Weather ---
    open_meteo_base_url: str = Field(
        default="https://api.open-meteo.com/v1", alias="OPEN_METEO_BASE_URL"
    )
    openweathermap_api_key: str = Field(default="", alias="OPENWEATHERMAP_API_KEY")
    weather_cache_ttl_seconds: int = Field(default=1800, alias="WEATHER_CACHE_TTL_SECONDS")
    # Same Open-Meteo account/infra as open_meteo_base_url above, just a
    # different API (geocoding, not forecasts) — resolves farm coordinates
    # from district/state so farmers never type latitude/longitude.
    geocoding_base_url: str = Field(
        default="https://geocoding-api.open-meteo.com/v1/search", alias="GEOCODING_BASE_URL"
    )

    # --- ML ---
    model_path: str = Field(default="/app/ml/artifacts/model.joblib", alias="MODEL_PATH")
    label_encoder_path: str = Field(
        default="/app/ml/artifacts/label_encoder.joblib", alias="LABEL_ENCODER_PATH"
    )
    feature_schema_path: str = Field(
        default="/app/ml/artifacts/feature_schema.json", alias="FEATURE_SCHEMA_PATH"
    )

    # --- Storage ---
    upload_directory: str = Field(default="/app/storage/uploads", alias="UPLOAD_DIRECTORY")
    max_upload_size_mb: int = Field(default=10, alias="MAX_UPLOAD_SIZE_MB")

    # --- OCR ---
    ocr_confidence_threshold: float = Field(default=0.85, alias="OCR_CONFIDENCE_THRESHOLD")
    # Inference backend for the PP-OCR models. "onnx" (default) runs the
    # bundled PP-OCR weights on ONNX Runtime and fits Render's 512 MB free
    # tier; "paddle" runs them on PaddlePaddle and needs
    # requirements-paddle.txt plus well over 512 MB (see
    # docs/OCR_MEMORY_REPORT.md). Both produce identical text.
    ocr_backend: Literal["onnx", "paddle"] = Field(default="onnx", alias="OCR_BACKEND")
    # Directory holding det.onnx / rec.onnx / cls.onnx / en_dict.txt.
    # None = resolve ml/paddleocr_models/onnx relative to the code.
    ocr_model_dir: str | None = Field(default=None, alias="OCR_MODEL_DIR")
    ocr_use_angle_cls: bool = Field(default=True, alias="OCR_USE_ANGLE_CLS")
    # Turn pages scanned/photographed sideways (90/270 degrees) upright
    # before recognition. Without it, a sideways card's table is read
    # transposed and no parameter can be matched to its value.
    ocr_auto_rotate: bool = Field(default=True, alias="OCR_AUTO_ROTATE")
    ocr_num_threads: int = Field(default=1, ge=1, le=8, alias="OCR_NUM_THREADS")
    # One document at a time keeps peak memory bounded: every concurrent
    # OCR run adds its own page image + model activations on top.
    ocr_max_concurrent: int = Field(default=1, ge=1, le=4, alias="OCR_MAX_CONCURRENT")
    # How long a request waits for a free OCR slot before getting 503.
    # On Render's free tier (0.1 CPU) one report takes ~2-5 minutes, so a
    # second farmer queues behind the first instead of failing. A waiting
    # request holds no image or model memory.
    ocr_queue_timeout_seconds: float = Field(
        default=300.0, ge=0.0, le=900.0, alias="OCR_QUEUE_TIMEOUT_SECONDS"
    )
    ocr_max_pdf_pages: int = Field(default=5, ge=1, le=50, alias="OCR_MAX_PDF_PAGES")
    ocr_pdf_dpi: int = Field(default=200, ge=72, le=400, alias="OCR_PDF_DPI")
    ocr_max_image_dimension: int = Field(
        default=1600, ge=640, le=4000, alias="OCR_MAX_IMAGE_DIMENSION"
    )
    # Uploaded photos above this pixel count are rejected before decoding
    # (a 10 MB PNG can otherwise decode to several GB).
    ocr_max_image_pixels: int = Field(
        default=60_000_000, ge=1_000_000, le=200_000_000, alias="OCR_MAX_IMAGE_PIXELS"
    )

    # --- Rules ---
    # None (rather than a hardcoded default) lets AgronomicRuleEngine fall
    # back to its own repo-relative path resolution for local/test runs,
    # while Docker explicitly sets this to the bind-mounted container path
    # (see docker-compose.yml) where that relative resolution doesn't apply.
    agronomic_rules_path: str | None = Field(default=None, alias="AGRONOMIC_RULES_PATH")
    fertilizer_kb_path: str | None = Field(default=None, alias="FERTILIZER_KB_PATH")
    # Market price artefacts (datasets/market); None = repo-relative default.
    market_data_dir: str | None = Field(default=None, alias="MARKET_DATA_DIR")

    @field_validator("jwt_secret")
    @classmethod
    def jwt_secret_must_not_be_trivial(cls, v: str) -> str:
        if not v or len(v) < 16:
            raise ValueError(
                "JWT_SECRET is missing or too short. Set a strong secret in .env "
                "(see .env.example). Refusing to start with an insecure secret."
            )
        return v

    @field_validator("database_url")
    @classmethod
    def database_url_must_be_postgres(cls, v: str) -> str:
        if not v.startswith("postgresql://") and not v.startswith("postgresql+"):
            raise ValueError(
                "DATABASE_URL must be a PostgreSQL connection string per AIB Vol 5.2."
            )
        return v

    @property
    def allowed_origins_list(self) -> List[str]:
        return [origin.strip() for origin in self.allowed_origins.split(",") if origin.strip()]

    @property
    def is_production(self) -> bool:
        return self.environment.lower() == "production"


@lru_cache
def get_settings() -> "Settings":
    """
    Cached settings singleton. Raises pydantic.ValidationError immediately
    if required environment variables are missing or invalid — this is the
    intended fail-fast behavior on application startup.
    """
    return Settings()
