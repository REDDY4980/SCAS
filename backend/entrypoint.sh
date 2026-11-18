#!/usr/bin/env bash
# SCAS backend container entrypoint.
# Implements AIB v1.0 Vol 16.10 steps 4-6: run Alembic migrations,
# then start FastAPI, so the app never serves traffic against an
# unmigrated database.
set -euo pipefail

echo "[entrypoint] Waiting for database..."
python - <<'PYEOF'
import os
import sys
import time
import psycopg2

url = os.environ["DATABASE_URL"]
for attempt in range(1, 31):
    try:
        conn = psycopg2.connect(url)
        conn.close()
        print("[entrypoint] Database is reachable.")
        sys.exit(0)
    except Exception as exc:  # noqa: BLE001
        print(f"[entrypoint] DB not ready (attempt {attempt}/30): {exc}")
        time.sleep(2)
print("[entrypoint] Database unreachable after 30 attempts. Failing fast.")
sys.exit(1)
PYEOF

MODEL_FILE="${MODEL_PATH:-/app/ml/artifacts/model.joblib}"
if [ ! -f "$MODEL_FILE" ]; then
  echo "[entrypoint] No trained model at $MODEL_FILE - training it now (deterministic, ~1 min)..."
  (cd /app && python -m ml.training.run_training --trials 20 --out "$(dirname "$MODEL_FILE")")
fi

echo "[entrypoint] Running Alembic migrations..."
alembic upgrade head

# OCR models are NOT loaded at startup: they load lazily, once, on the
# first soil-report OCR request (app/ocr/engine.py). Exactly ONE Uvicorn
# worker — every extra worker would hold its own copy of the OCR and crop
# models, which does not fit Render's 512 MB free tier.

echo "[entrypoint] Starting SCAS backend..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 1
