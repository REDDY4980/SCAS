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
COPY datasets ./datasets
COPY ml ./ml

# Train the crop model INSIDE the image. The trained *.joblib files are
# gitignored, so a fresh clone (Render, CI, a teammate's laptop) has no
# model and /recommendation would fail with ModelNotLoadedError while
# /health still reports OK. Training is deterministic (seed 42, fixed
# Optuna TPE seed) and takes ~1 minute, and it runs against exactly the
# library versions pinned above, so the pickle always loads.
RUN python -m ml.training.run_training --trials 20 --out /app/ml/artifacts

# PaddleOCR's own first-use auto-downloader (det/cls/rec model weights,
# ~16MB, from PaddlePaddle's CDN) is unreliable in this environment —
# reproduced twice: it either takes several minutes on a slow link (an
# earlier local-dev incident, see git history) or produces a truncated/
# corrupted file that crashes on load ("munmap_chunk(): invalid
# pointer" / "free(): invalid pointer", both observed testing this
# exact image). On a host with no persistent disk (e.g. Render's free
# tier, which starts empty on every cold start after the service
# sleeps), that isn't a one-time cost — it repeats on every wake-up and
# reliably exceeds the app's client-side OCR timeout. Shipping the
# already-downloaded, already-verified-working files directly avoids
# the flaky downloader entirely rather than retrying it at a different
# point in the container lifecycle.
COPY ml/paddleocr_models/whl /root/.paddleocr/whl

RUN mkdir -p /app/storage/uploads /app/storage/logs

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    AGRONOMIC_RULES_PATH=/app/datasets/agronomic_rules/agronomic_rules_v1.json \
    FERTILIZER_KB_PATH=/app/datasets/fertilizer_knowledge_base/fertilizer_knowledge_base_v1.json \
    MARKET_DATA_DIR=/app/datasets/market \
    MODEL_PATH=/app/ml/artifacts/model.joblib \
    LABEL_ENCODER_PATH=/app/ml/artifacts/label_encoder.joblib \
    FEATURE_SCHEMA_PATH=/app/ml/artifacts/feature_schema.json

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

RUN chmod +x /app/entrypoint.sh

CMD ["/app/entrypoint.sh"]
