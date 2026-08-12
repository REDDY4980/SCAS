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

# System deps required by OpenCV / PaddleOCR / psycopg2 at runtime
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
COPY ml/artifacts ./ml/artifacts
COPY datasets ./datasets

RUN mkdir -p /app/storage/uploads /app/storage/logs

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    AGRONOMIC_RULES_PATH=/app/datasets/agronomic_rules/agronomic_rules_v1.json \
    FERTILIZER_KB_PATH=/app/datasets/fertilizer_knowledge_base/fertilizer_knowledge_base_v1.json \
    MODEL_PATH=/app/ml/artifacts/model.joblib \
    LABEL_ENCODER_PATH=/app/ml/artifacts/label_encoder.joblib \
    FEATURE_SCHEMA_PATH=/app/ml/artifacts/feature_schema.json

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

RUN chmod +x /app/entrypoint.sh

CMD ["/app/entrypoint.sh"]
