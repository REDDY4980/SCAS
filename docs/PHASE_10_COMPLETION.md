# Phase 10 — Testing & Deployment: Completion Record

Per AIB v1.0 Vol 17.3 "Phase 10 – Testing & Deployment":
> Complete testing, Docker deployment and production validation.

## Deliverables

- [x] Full-suite coverage measurement: 94% backend, 87% ML — both comfortably above the Vol 0.11 "Critical service code coverage >=80%" target
- [x] Closed a real coverage gap: ml/training/trainer.py and ml/evaluation/evaluator.py had 0% automated-test coverage (only exercised via the manual Phase 6 training run) — added ml/tests/test_trainer_and_evaluator.py, a fast synthetic-data smoke test that caught nothing wrong but genuinely exercises the code path CI would otherwise miss entirely
- [x] deployment/scripts/smoke_test.sh — a real curl-based post-deployment check (register -> login -> JWT-protected access -> unauthenticated rejection -> farm creation) against a live running instance, distinct from the pytest suite's SQLite/fake-based tests
- [x] docs/DEPLOYMENT_GUIDE.md — single consolidated deployment reference, consciously honest about what has and hasn't been run end-to-end
- [x] Fixed two deprecation warnings (HTTP_422_UNPROCESSABLE_ENTITY -> HTTP_422_UNPROCESSABLE_CONTENT) — down to 2 warnings total, both from third-party library internals

## Two real, significant bugs found in this final review pass

### 1. The scas_ml_artifacts Docker volume would have started empty

docker-compose.yml mounted a named Docker volume at /app/ml/artifacts. Named volumes start empty on first `docker compose up` — nothing was populating it with the real trained model from Phase 6. The very first /recommendation request against a fresh deployment would have failed with ModelNotLoadedError, and nothing in the existing test suite would have caught it, because every test runs with MODEL_PATH pointed directly at the repo's ml/artifacts/ on the local filesystem, never through the Docker volume path. Fixed by switching to a read-only bind mount (./ml/artifacts:/app/ml/artifacts:ro) of the actual trained artifacts already in this repo.

### 2. requirements.txt had drifted significantly from what was actually tested

Across Phases 1, 4, and 6, dependencies were installed ad-hoc into the working sandbox venv without version pins. Phase 1's original pins were never revisited. A pip freeze comparison in this phase found the actual installed versions had diverged substantially — most critically xgboost==2.1.1 was pinned but xgboost==3.4.0 was what actually trained and serialized ml/artifacts/model.joblib. XGBoost has shipped breaking serialization-format changes across major versions; installing the stale pin in a fresh Docker build could easily have produced a backend that starts fine but throws on the first attempt to actually load the trained model.

Fixed by pinning every dependency to its exact confirmed-working pip freeze version. The one exception, called out explicitly in the file's own comments: paddleocr/paddlepaddle were never actually installed in any environment this project touched, so those two pins remain reasonable-but-unverified rather than confirmed.

## Honest Definition of Done assessment (AIB Vol 0.10)

| Vol 0.10 criterion | Status |
|---|---|
| Every screen functions | Code-complete, never compiled (Phase 3 gap) |
| OCR extracts supported soil reports | Pipeline logic proven correct against real SHC data; PaddleOCR's actual engine never invoked |
| Soil parameters are validated | Done, tested |
| Climate data is integrated | Client logic correct against real API docs; never called live |
| Crop and fertilizer recommendations are generated | Done, tested end-to-end against the real trained model |
| Explanations are produced | Done, tested |
| History is stored | Done, tested |
| APIs documented | Done — OpenAPI/Swagger auto-generated, inspected via TestClient |
| Database migrations complete | Migration written, DDL validated offline (alembic upgrade head --sql); never run against a live Postgres |
| Tests pass | 160/160 backend+ML; zero Flutter tests exist |
| Application builds successfully | Backend structurally sound (clean imports, py_compile, dependency-consistent requirements.txt as of this phase); docker build never actually run; flutter build never actually run |
| Deployment instructions are available | Done — docs/DEPLOYMENT_GUIDE.md, docker-compose.yml, entrypoint.sh, smoke_test.sh |

## Honest Success Criteria assessment (AIB Vol 0.11)

| Criterion | Status |
|---|---|
| OCR extraction accuracy >=95% | Field-parsing logic: 100% on 3 real SHC samples. Real end-to-end OCR accuracy (including PaddleOCR's actual text recognition) unmeasured |
| Crop recommendation response <=2s | Inference measured at 0.029ms/sample; full request path not load-tested |
| Weather retrieval <=2s | Enforced via a 2s client timeout in code; never measured against a live provider |
| Recommendation generation success >=99% | Every attempted test run succeeded (100% in testing), but this is not the same claim as a real-world load/variance success rate |
| App startup <=3s | Unmeasurable without a compiled Flutter app |
| API success >=99% | No load testing performed |
| Critical service code coverage >=80% | 94% backend / 87% ML — the one criterion fully, numerically verified |

## What this means, plainly

The backend is genuinely done: real code, real tests, a real trained model, real bugs found and fixed by actually running things rather than assuming they'd work. That part of the Vol 17.9 Definition of Completion bar is met for every backend phase.

What remains before the whole system clears that bar is entirely infrastructure this sandbox does not have: a Docker daemon, a live Postgres instance, live internet access to PaddleOCR's model registry and Open-Meteo, and a Flutter SDK. None of these are code problems. They are "run it somewhere that has the infrastructure" problems, and docs/DEPLOYMENT_GUIDE.md is written specifically to make that next step as close to turnkey as this environment allows.

## Explicitly deferred (not gaps, but real remaining work)

- Running this entire guide for real, on a machine with Docker.
- flutter analyze / flutter test / flutter build — Phase 3's flagged next step.
- Load/performance testing against the Vol 0.11 latency and success-rate targets under realistic concurrent traffic.
- CI/CD pipeline — would have caught both of this phase's bugs automatically going forward.
