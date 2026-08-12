# SCAS Deployment Guide

This is the single consolidated reference for deploying SCAS locally
per AIB v1.0 Vol 16 (Deployment Architecture). Individual phase
completion docs (docs/PHASE_*_COMPLETION.md) explain why things are
built the way they are; this document is the how to actually run it.

This guide has not been executed end-to-end in the environment that
built it -- no Docker daemon was available in that sandbox (checked
repeatedly, Phases 1 and 10). Everything below is correct by careful
construction and cross-checking, in the same spirit as Phase 3's
Flutter code, but the first real `docker compose up` on your machine is
the actual proof, not this document.

## Prerequisites

- Docker and Docker Compose v2 (`docker compose version`)
- ~4GB free disk space (PaddleOCR + XGBoost + OpenCV images are not tiny)
- Ports 8000 (backend), 5432 (Postgres), optionally 5050 (pgAdmin) free

## Step-by-step (Vol 16.10 Deployment Workflow)

### 1. Configure environment

```bash
cp .env.example .env
```

Edit `.env` and set, at minimum:
- `JWT_SECRET` -- generate with `python -c "import secrets; print(secrets.token_urlsafe(64))"`
- `POSTGRES_PASSWORD` -- any strong password; docker-compose.yml requires this to be set

Optional but recommended before Phase 5 features are used for real:
- `OPENWEATHERMAP_API_KEY` -- fallback weather provider (flagged as an open input since DECISIONS.md; Open-Meteo works with no key as the primary provider)

### 2. Build and start

```bash
docker compose up --build
```

This runs, in order (Vol 16.4):
1. postgres container starts, waits for healthy (pg_isready)
2. backend container builds (installs requirements.txt -- this includes PaddleOCR/PaddlePaddle/OpenCV/XGBoost/Optuna, so the first build is slow, plausibly 5-15 minutes depending on connection)
3. backend's entrypoint.sh waits for Postgres to accept connections, then runs `alembic upgrade head` (creates all 8 tables from alembic/versions/0001_initial_schema.py), then starts uvicorn
4. The real trained ML model (ml/artifacts/*.joblib, already in this repo from Phase 6 -- 98.64% test accuracy on the real Requirement 1 dataset) is bind-mounted read-only into the container, so /recommendation works immediately without a separate seeding step

### 3. Verify health

```bash
curl http://localhost:8000/health
```

Or open http://localhost:8000/docs for the interactive Swagger UI -- every one of the 12 real endpoints across Auth, Farms, Soil/OCR, Weather, Recommendation, Fertilizer, and History should be listed there (Vol 14.6).

### 4. Run the smoke test

```bash
./deployment/scripts/smoke_test.sh
```

This exercises the real, live API (Vol 16.10 step 8) -- health check, docs availability, register, login, JWT-protected endpoint access, unauthenticated rejection, and farm creation. It is intentionally NOT a replacement for the 160-test pytest suite (which runs against SQLite and injected fakes for speed) -- this is the first check that the actual containerized deployment works, PaddleOCR model download and all.

### 5. (Optional) Inspect the database

```bash
docker compose --profile dev up pgadmin
# http://localhost:5050
```

## What to expect on first real use (things NOT verified in the build sandbox)

Every phase's completion doc already flags its own specific gap. Consolidated here:

| Component | Status | What "first real use" means |
|---|---|---|
| PaddleOCR (Phase 4) | Code complete, never invoked | First real soil report upload will trigger a PaddleOCR model download (~100s of MB) on first /soil/{id}/ocr call -- expect that first call to take noticeably longer than the Vol 7.13 5s target while the model downloads and loads |
| Open-Meteo / OpenWeatherMap (Phase 5) | Code complete, never called live | First /weather/current call is the first real network round-trip to Open-Meteo from this codebase |
| Docker / Postgres (Phase 1, this phase) | Config complete, never run | This entire guide is the first real end-to-end run |
| Flutter app (Phase 3) | Code complete, never compiled | flutter analyze is the mandatory first step -- see docs/PHASE_3_COMPLETION.md |

Everything else -- the entire backend business logic, the trained ML model, the agronomic/fertilizer rule engines -- has been verified by 160 passing automated tests (94% backend / 87% ML coverage) against real data throughout Phases 1-2, 4-9.

## Rollback

Per Vol 16.11:
```bash
docker compose down          # stop, keep volumes (data preserved)
docker compose down -v       # stop AND delete volumes (full reset, including the Postgres database)
```

Alembic migrations can be rolled back individually:
```bash
docker compose exec backend alembic downgrade -1
```

## Production deployment (not built in this phase)

Per DECISIONS.md: "Deployment target: LOCAL DOCKER FIRST. Cloud deployment is deferred until the application is stable." This guide covers local Docker only. Cloud deployment (Vol 16 doesn't specify a target cloud provider) would additionally need: a managed Postgres instance, container registry + CI/CD pipeline, HTTPS/TLS termination, and real production secrets management -- none of which are in scope until explicitly requested.
