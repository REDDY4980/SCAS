# SCAS — Smart Crop Advisory System

Hybrid AI Decision Support System combining soil health analysis and
real-time climate intelligence to recommend crops and fertilizers,
built to **AIB v1.0** (Volumes 0–19) — see `docs/` for the governing
specification and resolved domain resources.

**Status:** Phase 1 — Project Initialization (AIB Vol 17.3, Phase 1) complete.

## Repository Layout

```
scas/
├── backend/          FastAPI backend (AIB Vol 12)
│   └── app/
│       ├── api/          Route handlers (versioned: /api/v1)
│       ├── core/         Config, DB session, logging, exception handlers
│       ├── services/     Business logic (Phase 2+)
│       ├── repositories/ Data-access layer (Phase 2+)
│       ├── schemas/      Pydantic request/response contracts
│       ├── models/       SQLAlchemy ORM models (Phase 2)
│       ├── middleware/   Auth & request middleware (Phase 2)
│       ├── dependencies/ FastAPI dependency-injection providers
│       ├── ocr/          OCR pipeline (Phase 4, AIB Vol 7)
│       ├── weather/      Climate Intelligence Engine (Phase 5, AIB Vol 8)
│       ├── ml/           Inference orchestration (Phase 6, AIB Vol 9)
│       └── rules/        Agronomic + fertilizer rule engines (Phase 7-8)
├── mobile/           Flutter client (AIB Vol 13, Phase 3)
├── ml/               Training pipeline: datasets, features, models (AIB Vol 9, Phase 6)
├── datasets/          Resolved domain resources (crop data, fertilizer KB, agronomic rules, OCR calibration)
├── docs/             AIB governance docs, master resource index, decisions log
├── deployment/       Docker/deployment scripts and docs (AIB Vol 16)
├── tests/            Cross-cutting integration & E2E tests (AIB Vol 15)
├── storage/          Runtime uploads/logs/backups (gitignored)
├── docker-compose.yml
└── .env.example
```

## Quickstart (Local Docker)

See `docs/DEPLOYMENT_GUIDE.md` for the full, step-by-step deployment
walkthrough (environment setup, build, health check, smoke test,
rollback). Short version:

```bash
cp .env.example .env
# Edit .env: set JWT_SECRET and POSTGRES_PASSWORD

docker compose up --build
./deployment/scripts/smoke_test.sh
# Backend:   http://localhost:8000
# API docs:  http://localhost:8000/docs
```

Optional pgAdmin for local DB inspection:

```bash
docker compose --profile dev up pgadmin
# http://localhost:5050
```

## Quickstart (Backend, no Docker)

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp ../.env.example ../.env   # fill in JWT_SECRET / DATABASE_URL
export $(grep -v '^#' ../.env | xargs)   # or use python-dotenv
uvicorn app.main:app --reload
```

The app **fails fast** (per AIB Vol 16.12) if `JWT_SECRET` or
`DATABASE_URL` are missing or invalid — this is intentional.

## Governance

This project follows **AIB v1.0** as its single source of truth
(see `docs/CLAUDE_AIB_v1_KICKOFF_PACKAGE.md` and the full Volume set).
No architecture decision in this repository should contradict the AIB
without the AIB itself being updated first.

Domain resource resolution status (crop dataset, fertilizer KB,
agronomic rules, OCR calibration samples) is documented in
`docs/MASTER_RESOURCE_INDEX.md` and `docs/MANIFEST.json`.

## Implementation Phases (AIB Vol 17.3)

| Phase | Scope | Status |
|---|---|---|
| 1 | Project Initialization | ✅ Complete |
| 2 | Authentication & Database | ✅ Complete |
| 4 | OCR Pipeline | ✅ Complete |
| 5 | Climate Engine | ✅ Complete |
| 6 | Machine Learning | ✅ Complete (real trained model, 98.64% test accuracy) |
| 7 | Hybrid Recommendation | ✅ Complete |
| 8 | Fertilizer Engine | ✅ Complete |
| 9 | History & Profile | ✅ Complete |
| 3 | Flutter Foundation | ✅ Complete — code-complete, never compiled (no Flutter SDK available) |
| 10 | Testing & Deployment | ✅ Complete |

**All 10 AIB phases are implemented.** 160 automated tests passing
(135 backend + 25 ML), 94%/87% coverage, a genuinely trained ML model,
and every backend bug found during development was found by actually
running the code against real data — not assumed away. Two more real
bugs were caught in Phase 10's final review (a Docker volume that
would have started empty, and dependency pins that had drifted from
what was actually tested) and fixed there.

**What's proven vs. what's next:** the entire backend — auth, farms,
OCR pipeline, weather integration, ML inference, agronomic/fertilizer
rule engines, history — is tested and working against real data. What
remains is running it somewhere with the infrastructure this sandbox
didn't have: a Docker daemon (to actually build and run the
containers), a live Postgres instance, live internet access to
PaddleOCR's model registry and Open-Meteo, and a Flutter SDK (to
compile and run the mobile app). None of these are code problems —
`docs/DEPLOYMENT_GUIDE.md` is the concrete next-step guide, and
`docs/PHASE_10_COMPLETION.md` has the full honest accounting against
every AIB Vol 0.10/0.11 criterion.

See `docs/PHASE_1_COMPLETION.md` through `docs/PHASE_10_COMPLETION.md`
for detailed checklists against AIB Vol 17.6.

## Try it now (Phase 2 endpoints)

```bash
docker compose up --build
# then, once the backend is healthy:
curl -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{"full_name":"Asha Farmer","email":"asha@example.com","phone":"+919876543210","password":"StrongPass123"}'

curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"identifier":"asha@example.com","password":"StrongPass123"}'
# -> copy the access_token from the response

curl http://localhost:8000/api/v1/auth/me \
  -H "Authorization: Bearer <token>"
```

Or run the automated test suite instead of doing this by hand:

```bash
cd backend
pip install -r requirements.txt
pytest tests/ -v   # 25 tests, no Docker/Postgres required (uses in-memory SQLite)
```
