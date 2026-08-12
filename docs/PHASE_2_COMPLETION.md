# Phase 2 — Authentication & Database: Completion Record

Per AIB v1.0 Vol 17.3 "Phase 2 – Authentication & Database":
> Implement authentication, database schema, migrations and repositories.

## Deliverables

### Database (AIB Vol 5)

- [x] `app/models/user.py`, `farm.py`, `soil.py`, `weather.py`, `recommendation.py`, `user_settings.py` — all 8 entities from Vol 5.3 (`users`, `farms`, `soil_reports`, `soil_parameters`, `weather_snapshots`, `recommendations`, `fertilizer_recommendations`, `user_settings`)
- [x] Every relationship from Vol 5.4 implemented with matching cascade rules (`ON DELETE CASCADE` for owned children, `ON DELETE SET NULL` for optional cross-references on `recommendations.report_id` / `weather_id`)
- [x] UUID primary keys throughout (Vol 5.5)
- [x] Unique constraints on `users.email`, `users.phone`, `soil_parameters.report_id`, `user_settings.user_id` (Vol 5.5)
- [x] Indexes on every FK, `created_at`, `email`, `phone` (Vol 5.6)
- [x] `alembic/versions/0001_initial_schema.py` — hand-written initial migration, generates correct PostgreSQL DDL (verified via `alembic upgrade head --sql`, full output reviewed)
- [x] `app/models/__init__.py` — model registry so `Base.metadata` is complete for Alembic autogenerate and tests

### Authentication (AIB Vol 6)

- [x] `app/core/security.py` — bcrypt password hashing, JWT issue/decode (Vol 6.2/6.3)
- [x] `POST /api/v1/auth/register` — duplicate email/phone rejected with 409, weak passwords rejected with 422 (Vol 6.6)
- [x] `POST /api/v1/auth/login` — accepts email or phone as identifier; wrong password and unknown identifier both return an identical 401 (never reveals which was wrong) (Vol 6.11)
- [x] `GET /api/v1/auth/me` — returns current user, requires valid JWT
- [x] `PUT /api/v1/users/profile` — updates name + settings (language/theme/notifications)
- [x] `app/dependencies/auth.py` — Bearer-token dependency; missing/garbage/expired tokens all correctly rejected with 401
- [x] Password hashes never appear in any API response (asserted in tests)

### Farm Management (AIB Vol 6.10, Vol 14.2)

- [x] Full `/api/v1/farms` CRUD (POST, GET list, GET one, PUT, DELETE)
- [x] One user can manage multiple farms (explicit acceptance criterion, Vol 6.14) — tested
- [x] Ownership enforcement: a second user cannot GET/PUT/DELETE another user's farm — gets 404, not 403, so the farm's existence isn't leaked to non-owners (Vol 6.10)

### Repositories & Services (AIB Vol 12.6)

- [x] `user_repository.py`, `farm_repository.py` — pure CRUD, zero business logic
- [x] `auth_service.py`, `farm_service.py` — all business rules (duplicate checks, ownership checks, password hashing orchestration) live here, not in routers

### Tests (AIB Vol 15)

- [x] `tests/unit/test_security.py` — 5 tests: hashing, verification, JWT roundtrip, garbage token, expired token
- [x] `tests/integration/test_auth_api.py` — 13 tests: register/login/me/profile happy paths and failure modes
- [x] `tests/integration/test_farms_api.py` — 7 tests: CRUD, multi-farm ownership, cross-user isolation
- [x] **25/25 tests passing**

## Verification performed in this environment

1. Installed the full Phase 2 dependency set (SQLAlchemy, Alembic, psycopg2-binary, python-jose, passlib, bcrypt, email-validator) into the smoke-test venv.
2. **Found and fixed a real circular-import bug**: model modules imported `Base` from `base.py`, while `base.py` tried to import the model modules back into itself. Fixed by moving the "import every model" step into `app/models/__init__.py`, keeping `base.py` minimal. Re-verified with a direct import + metadata inspection (`Base.metadata.tables` → all 8 tables, correct FKs).
3. **Found and fixed a real `passlib`/`bcrypt` version incompatibility**: `passlib==1.7.4`'s internal bcrypt self-test crashes on `bcrypt>=4.1` (missing `__about__` attribute triggers a `ValueError` on any hash/verify call). Pinned `bcrypt==4.0.1` in `requirements.txt` and confirmed hashing/verification both work.
4. Ran the app via `TestClient` without the lifespan context manager (confirms route-level tests don't accidentally hit the real Postgres reachability check) and with a raw `/openapi.json` fetch — confirmed all 8 Phase 1+2 endpoints are registered with the exact paths from Vol 14.2.
5. Replaced the deprecated `@app.on_event("startup")` handler with FastAPI's modern `lifespan` context manager (removes a deprecation warning; behavior unchanged — still fails fast per Vol 16.12 if Postgres is unreachable).
6. Ran the full pytest suite against an in-memory SQLite substitution (dependency-injection override of `get_db`; production `DATABASE_URL` is still validated as PostgreSQL-only) — **25 passed, 0 failed**.
7. Generated the actual PostgreSQL DDL from the hand-written Alembic migration via `alembic upgrade head --sql` (offline mode, no live DB needed) and read through the full output line by line — table structure, types, defaults, FKs and cascade rules all match the ORM models exactly.
8. `py_compile`'d every `.py` file under `app/` and `alembic/` — all compile cleanly.

**Not verified in this environment** (no Docker daemon / no live Postgres server available in the sandbox): an actual `alembic upgrade head` execution against a running Postgres instance, and a full `docker compose up` run. Both should be the first things run after cloning — the generated SQL above gives high confidence they'll succeed, but a live run is the real test.

## Explicitly deferred to later phases (not gaps)

- OCR pipeline, soil report upload/validation endpoints — Phase 4.
- Weather integration — Phase 5.
- ML inference, hybrid recommendation, fertilizer engine — Phases 6-8.
- History endpoints (`GET /history`, `GET /history/{id}`) — Phase 9 (the `recommendations`/`fertilizer_recommendations` tables already exist to support this).
- Flutter auth screens consuming these APIs — Phase 3.
- Rate limiting on `/auth/*` (Vol 6.11, Vol 12.8 mention it; no rate-limiting library wired in yet — flagged for Phase 10 hardening pass, not silently dropped).

## AIB Compliance Notes

- No TODOs left in generated code (Vol 0.7 Rule 4).
- No hardcoded secrets; JWT secret and DB credentials only ever read from environment (Vol 0.7 Rule 5, Vol 6.7).
- Controllers (routers) never touch the ORM directly — every DB access goes through a repository (Vol 12.6).
- Business logic lives in services, not routers or repositories (Vol 12.4).
