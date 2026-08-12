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

echo "[entrypoint] Running Alembic migrations..."
alembic upgrade head

# PaddleOCR is warmed up inside app/main.py's FastAPI lifespan startup,
# not here — a separate `python3 -c "..."` subprocess reliably crashes
# loading it (reproduced repeatedly against this exact image), while
# the identical call succeeds every time inside the actual uvicorn
# worker process below. See app/ocr/engine.py's warm_up() docstring.

echo "[entrypoint] Starting SCAS backend..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
