# SCAS Backend — AIB v1.0 Vol 16.4
#
# Build context is the REPO ROOT, not backend/ — see docker-compose.yml
# and render.yaml, both of which set `context: .` with
# `dockerfile: backend/Dockerfile`. This is required so the image can
# bake in ml/artifacts/ and datasets/, which live outside backend/ and
# in local dev only reach the container via docker-compose's bind
# mounts (docker-compose.yml still mounts them read-only on top of
# this for live-editing convenience). A standalone deploy target
# (Render, or `docker build` with no docker-compose) has no bind
# mounts at all, so the image must be self-contained.
FROM python:3.11-slim AS base

# System deps required by OpenCV / psycopg2 at runtime
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libglib2.0-0 \
    libpq-dev \
    gcc \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY backend/requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

COPY backend/ .
COPY datasets ./datasets
COPY ml ./ml

# Train the crop model INSIDE the image. The trained *.joblib files are
# gitignored, so a fresh clone (Render, CI, a teammate's laptop) has no
# model and /recommendation would fail with ModelNotLoadedError while
# /health still reports OK. Training is deterministic (seed 42, fixed
# Optuna TPE seed) and takes ~1 minute, and it runs against exactly the
# library versions pinned above, so the pickle always loads.
RUN python -m ml.training.run_training --trials 20 --out /app/ml/artifacts

# OCR models: the bundled PP-OCR weights (en_PP-OCRv3_det, en_PP-OCRv4_rec,
# ch_ppocr_mobile_v2.0_cls), converted 1:1 to ONNX, ship inside the repo at
# ml/paddleocr_models/onnx/ and are copied with `COPY ml ./ml` above —
# nothing is ever downloaded at runtime. They run on ONNX Runtime
# (app/ocr/ppocr_onnx.py); PaddlePaddle is not installed in this image
# because it cannot fit Render's 512 MB free tier
# (docs/OCR_MEMORY_REPORT.md). Fail the build if a model file is missing.
RUN test -s /app/ml/paddleocr_models/onnx/det.onnx \
    && test -s /app/ml/paddleocr_models/onnx/rec.onnx \
    && test -s /app/ml/paddleocr_models/onnx/cls.onnx \
    && test -s /app/ml/paddleocr_models/onnx/en_dict.txt

RUN mkdir -p /app/storage/uploads /app/storage/logs

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    AGRONOMIC_RULES_PATH=/app/datasets/agronomic_rules/agronomic_rules_v1.json \
    FERTILIZER_KB_PATH=/app/datasets/fertilizer_knowledge_base/fertilizer_knowledge_base_v1.json \
    MARKET_DATA_DIR=/app/datasets/market \
    MODEL_PATH=/app/ml/artifacts/model.joblib \
    LABEL_ENCODER_PATH=/app/ml/artifacts/label_encoder.joblib \
    FEATURE_SCHEMA_PATH=/app/ml/artifacts/feature_schema.json \
    OCR_MODEL_DIR=/app/ml/paddleocr_models/onnx \
    OMP_NUM_THREADS=1 \
    MALLOC_ARENA_MAX=2

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

RUN chmod +x /app/entrypoint.sh

CMD ["/app/entrypoint.sh"]
