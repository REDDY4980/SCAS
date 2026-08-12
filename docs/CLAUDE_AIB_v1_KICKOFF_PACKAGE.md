# SCAS — AIB v1.0 Implementation Kickoff Package

**Prepared by:** Chief Software Architect / Senior ML Engineer / Senior Flutter Engineer / Senior FastAPI Engineer / DevOps Engineer / QA Lead (combined review role) **Source:** AIB v1.0, Volumes 1–19 (full read, cross-referenced) **Status:** Pre-implementation gate. Nothing in Phase 1 (Vol. 17) starts until Part B below is resolved.

---

## PART A — Cross-Volume Review Findings

### A.1 Overall verdict

The 19 volumes are internally coherent and form a legitimate, traceable spec: Vision → Functional → UX → Architecture → DB → Auth → OCR → Climate → ML → Crop Engine → Fertilizer Engine → Backend → Flutter → API → Testing → Deployment → Manifest → Handbook → Defense. Volume 17 already gives the correct phase order and Volume 5's ERD, Volume 14's endpoints, and Volume 12's services all agree with each other. This is buildable as written.

### A.2 Inconsistencies / gaps found (need your decision before I code against them)

1. **Platform scope conflict.** Volume 1 §1.6 scopes v1.0 as *"Android application"* only. Volume 13 specifies Flutter (cross-platform by nature) with no iOS exclusion stated. → **Decision needed:** Android-only build target, or Android+iOS from Flutter's shared codebase (no extra cost either way in Flutter, but affects signing/store requirements).
2. **No training dataset exists anywhere in the AIB.** Volume 9 specifies the full XGBoost pipeline (features, split ratios, CV, Optuna tuning) but there is no source dataset referenced. This is the single largest blocker — the ML engine, the rule engine's crop list, and the fertilizer engine's "suitable crops" mapping (Vol. 10, Vol. 11) all *depend* on knowing which crops the model supports.
3. **Fertilizer Knowledge Base (Vol. 11 §11.7) has no data source.** It's specified as a config-driven JSON catalog, but no fertilizer catalog (names, NPK composition, dosage formulas, precautions) is provided.
4. **OCR field synonyms (Vol. 7 §7.7) are illustrative, not exhaustive.** Indian Soil Health Cards vary in layout by state/lab. Without at least a few real sample reports, the keyword/regex map will be guessed rather than calibrated, directly risking the ≥95% OCR accuracy target in Vol. 1 §1.14 / Vol. 7 §7.13.
5. **Agronomic rule thresholds are examples only** (Vol. 10 §10.6 gives 3 illustrative rules; Vol. 11 §11.5 says "configurable thresholds" without values). These need either a domain-expert-approved rule set or a defensible public agronomic reference to cite for your project defense (relevant given Vol. 19 is literally a "technical defense" volume — a jury may ask where the numbers came from).
6. **Volume 3 screen specs are templated.** Every SCR-00x has identical boilerplate for Loading/Failure/Security/Testing sections. This is fine to build from (the global rules in §3.2/§3.4 cover it), just flagging it's not screen-specific detail — I'll rely on Vol. 13 UI standards to fill the gaps.
7. **Weather fallback provider unspecified.** Vol. 8 §8.3 says "Fallback: OpenWeatherMap/WeatherAPI" (either/or, not decided). Needs one explicit choice since it determines which credential to obtain.

None of these block starting Phase 1–3 (repo, DB, auth, Flutter shell) — they only block Phase 4 (OCR) through Phase 8 (Fertilizer). I'll sequence around that.

---

## PART B — Requirements, APIs & Credentials Needed From You

Organized by what's needed and when. Items marked **(auto)** I generate myself and don't need from you.

### B.1 Accounts / API Credentials

| Item Needed for Required? Notes                                        |                               |                                                     |                                                                                               |
| ---------------------------------------------------------------------- | ----------------------------- | --------------------------------------------------- | --------------------------------------------------------------------------------------------- |
| Weather fallback API key (OpenWeatherMap **or** WeatherAPI — pick one) | Vol. 8 Climate Engine         | Required before Phase 5                             | Open-Meteo (primary) needs no key. Pick one fallback and get a free-tier key.                 |
| PostgreSQL connection details (host/user/password) for staging/prod    | Vol. 5, Vol. 16               | Required only for deployment beyond local Docker    | Local dev uses Docker Postgres — no external creds needed for Phases 1–15.                    |
| Cloud provider account (AWS/GCP/Azure/DigitalOcean/Render/etc.)        | Vol. 16 Deployment            | Required before Phase 10                            | Tell me which one — affects Docker Compose vs. managed service config.                        |
| Domain name + DNS access                                               | Vol. 16 §16.9 (HTTPS in prod) | Required before Phase 10                            | For TLS/SSL cert (Let's Encrypt) and CORS `ALLOWED_ORIGINS`.                                  |
| Container registry (Docker Hub / GHCR / ECR)                           | Vol. 16 §16.4, §16.11         | Optional, needed only if deploying to a remote host |                                                                                               |
| GitHub repo URL (+ push access if you want me committing directly)     | Vol. 18 §18.5 Git workflow    | Recommended before Phase 1                          | If you'd rather I hand you files to push yourself, that's fine too — tell me your preference. |
| Google Play Console account                                            | Future — app store release    | Not required for v1.0 build                         | Only needed at actual publish time.                                                           |

**JWT\_SECRET, DATABASE\_URL (local), MODEL\_PATH, UPLOAD\_DIRECTORY** → **(auto)** — I'll generate/configure these as environment variables per Vol. 16 §16.5. You'll just need to store the generated `JWT_SECRET` securely once issued.

### B.2 Datasets & Domain Knowledge (the real gate — see A.2 above)

| Item Why it's required Your options                                                                         |                                                         |                                                                                                                                                                                                                                                                                         |
| ----------------------------------------------------------------------------------------------------------- | ------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Crop recommendation training dataset** (soil params + climate → crop label)                               | Vol. 9 can't train XGBoost without this                 | (a) You provide a proprietary/collected dataset, or (b) I use a recognized public agricultural dataset (e.g., a standard Kaggle-style crop-recommendation dataset with N/P/K/temperature/humidity/pH/rainfall/label) as a documented placeholder you can swap later. **Tell me which.** |
| **Supported crop list**                                                                                     | Drives Vol. 10 rule engine + Vol. 11 fertilizer mapping | Derived automatically once the dataset (above) is chosen, unless you want a specific fixed list (e.g., only crops relevant to a specific state).                                                                                                                                        |
| **Fertilizer knowledge base** (fertilizer name, NPK composition, suitable crops, dosage logic, precautions) | Vol. 11 §11.7                                           | (a) You supply it (e.g., from ICAR/state agri-department guidelines), or (b) I build a starter catalog from publicly documented standard fertilizers (Urea, DAP, MOP, Zinc Sulphate, etc.) that you can expand. **Tell me which.**                                                      |
| **Agronomic rule set with real thresholds**                                                                 | Vol. 10 §10.6                                           | Same choice as above — expert-provided vs. a documented public-reference starter set.                                                                                                                                                                                                   |
| **2–3 sample Soil Health Card files** (PDF or photo)                                                        | Calibrates Vol. 7 OCR field extraction                  | Strongly recommended even if dummy/redacted — without this, OCR regex mapping is unvalidated guesswork.                                                                                                                                                                                 |

> If you don't have (a) for any of the above, say so explicitly and I'll proceed with (b) — a clearly-labeled placeholder/starter version — so the pipeline is fully wired end-to-end and swappable later without architecture changes (consistent with Vol. 11 §11.16: "Support future expansion of fertilizer catalog").

### B.3 Decisions (no credential needed, just your answer)

1. Android-only or Android+iOS (A.2 #1).
2. Public placeholder dataset OK for ML training, or wait for your real data (A.2 #2)?
3. Weather fallback provider: OpenWeatherMap or WeatherAPI (A.2 #7)?
4. Deployment target for Phase 10: local Docker only for now, or a specific cloud host?
5. State management: Vol. 13 §13.4 prefers Riverpod — confirm, or you want BLoC?
6. Do you want me committing to a Git repo as I go, or delivering files per phase for you to review/commit?

### B.4 Local Tooling (I'll use inside my own environment — confirming so nothing surprises you)

- Python 3.11+, FastAPI, SQLAlchemy, Alembic, PaddleOCR, XGBoost, Optuna, scikit-learn
- PostgreSQL (Dockerized for dev)
- Flutter SDK + Dart (Riverpod, Dio, flutter\_secure\_storage)
- Docker & Docker Compose
- pytest for backend, flutter\_test for mobile

No action needed from you here — listed for transparency per Vol. 18 documentation standards.

---

## PART C — Master Implementation Self-Prompt

*(This is the operating directive I will follow across the build. Reusable at the start of every future session on this project — paste it back to me if a session needs re-grounding.)*

```
ROLE: Acting simultaneously as Chief Software Architect, Senior ML Engineer,
Senior Flutter Engineer, Senior FastAPI Engineer, DevOps Engineer, and QA Lead
for SCAS (Smart Crop Advisory System), built strictly per AIB v1.0 (Volumes 1–19).

NON-NEGOTIABLE RULES:
1. AIB v1.0 is the single source of truth. Never redesign architecture,
   rename entities, or invent endpoints not defined in Vol. 4/5/12/14.
2. Follow Vol. 17's phase order exactly. Do not start a phase whose
   dependency phase (Vol. 17 §17.5 Dependency Matrix) is incomplete.
3. Every module must satisfy its own volume's Acceptance Criteria section
   before being marked done — do not self-report completion otherwise.
4. Respect layer boundaries at all times (Vol. 4 §4.5, Vol. 12 §12.6):
   Controllers → Services → Repositories → DB. No business logic in
   routers, no ORM access in controllers, no business logic in Flutter
   widgets (Vol. 13 §13.13).
5. ML inference never happens on-device (Vol. 4 §4.12). OCR text never
   goes straight to ML (Vol. 7 §7.16, Vol. 9 §9.20) — it must pass
   validation first. Every crop prediction must pass through the
   Agronomic Rule Engine + Confidence Engine before reaching the user
   (Vol. 9 §9.20, Vol. 10 §10.15). Every recommendation (crop or
   fertilizer) must ship with an explanation — no silent outputs
   (Vol. 2 BR-04, Vol. 10 §10.9, Vol. 11 §11.9).
6. Random Forest is explicitly excluded (Vol. 9 §9.3) — XGBoost only.
7. No hardcoded secrets; all config via environment variables validated
   at startup (Vol. 16 §16.5, §16.12).
8. Generate tests alongside every module, not after (Vol. 15, Vol. 17
   §17.8) — unit → integration → API → UI → E2E per Vol. 15 §15.3 pyramid.
9. Where AIB placeholders exist (dataset, fertilizer catalog, agronomic
   thresholds — see Part B.2 of the kickoff package), use the explicitly
   agreed placeholder/source and label it clearly in code comments and
   docs as "SOURCE: <placeholder|user-provided>, replace via config,
   no architecture change required" — never fabricate data silently.
10. Commit/deliver at the end of each completed task (Vol. 17 §17.8),
    not mid-task. If a task fails, stop dependent tasks, fix root cause,
    re-test, then continue (Vol. 17 §17.7).

EXECUTION ORDER (Vol. 17 §17.3, do not reorder):
Phase 1  Project Initialization — repo, folder structure (Vol. 4 §4.8,
         Vol. 12 §12.3, Vol. 13 §13.3), Docker, dependencies.
Phase 2  Authentication & Database — Vol. 5 schema + Alembic migrations,
         Vol. 6 auth service, bcrypt, JWT.
Phase 3  Flutter Foundation — Vol. 13 navigation, auth screens (SCR-001
         to SCR-003), Riverpod, Dio client with JWT interceptor.
Phase 4  OCR Pipeline — Vol. 7: upload → OpenCV preprocessing → PaddleOCR
         → field extraction → validation → structured JSON.
Phase 5  Climate Engine — Vol. 8: Open-Meteo primary + fallback, caching
         (30 min TTL), normalization.
Phase 6  Machine Learning — Vol. 9: dataset pipeline, feature engineering,
         XGBoost training (Optuna-tuned, stratified 5-fold CV), Joblib
         serialization, inference service (<=2s).
Phase 7  Hybrid Recommendation — Vol. 10: rule engine, confidence engine,
         Top-5 ranking, explainability engine.
Phase 8  Fertilizer Engine — Vol. 11: deficiency detection, knowledge
         base, dosage engine, explainability.
Phase 9  History & Profile — Vol. 5/Vol. 14 persistence + SCR-010/SCR-011.
Phase 10 Testing & Deployment — Vol. 15 full pyramid, Vol. 16 Docker
         Compose, migrations-before-boot, health checks, smoke tests.

DEFINITION OF DONE (Vol. 17 §17.9):
Every volume's Acceptance Criteria satisfied + full E2E journey passes:
Register → Login → Add Farm → Upload Report → OCR → Weather →
Recommendation → Fertilizer → History, with explanations present at
every recommendation step and all tests green.

BEFORE WRITING ANY CODE FOR PHASE 4+: confirm Part B.2 decisions
(dataset source, fertilizer catalog source, agronomic thresholds,
weather fallback provider) are resolved. If not resolved, pause and
ask rather than fabricating data.

```

---

## What I need from you to actually start

Reply with answers to **B.3 (1–6)** and tell me your calls on **B.2** (real data vs. documented placeholders). Phases 1–3 (repo/folder structure, DB schema + migrations, auth, Flutter shell) can start immediately regardless — they don't depend on any of the open items. I can kick those off as soon as you confirm the platform scope (B.3 #1) and repo preference (B.3 #6).