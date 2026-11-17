# Smart Crop Advisory System (SCAS): Step-by-Step Implementation Guide

This guide takes you from an empty laptop to a running, deployed SCAS: the FastAPI backend, the machine-learning model, OCR for Soil Health Cards, live weather, crop, fertilizer and market advice, the Flutter app, automated tests and cloud deployment. Every command here was run against this code base.

---

## 0. What you are building

```
 Flutter app (Android / iOS / Web, English · Kannada · Hindi · Telugu)
        │  HTTPS + JWT  (REST API /api/v1)
        ▼
 FastAPI backend ──────────────────────────────────────────────────────────
  Soil path      SHC PDF/photo → OpenCV clean-up → PaddleOCR → row rebuild
                 → regex field parser → range + confidence check (≥ 0.85)
  Climate path   farm location → Open-Meteo (OpenWeatherMap fallback) → 30-min cache
  Decision       [N, P, K, temp, humidity, pH, rainfall] → XGBoost Top-5
                 → agronomic rules (bonus/penalty) → re-rank → explanation
  Fertilizer     SHC low/medium/high bands → sourced dose or deficit ÷ nutrient %
  Market         mandi prices → seasonal outlook (only if it beat a naive forecast)
                 → sell now / hold / time harvest
  Storage        PostgreSQL (users, farms, soil reports, weather, recommendations)
```

| Layer | Technology |
|---|---|
| Mobile / web UI | Flutter 3 (Dart ≥ 3.3), Riverpod, go_router, Dio |
| API | Python 3.11, FastAPI, Pydantic v2, Uvicorn |
| Database | PostgreSQL 16, SQLAlchemy 2, Alembic migrations |
| ML | XGBoost 2.1, scikit-learn, Optuna |
| OCR | PaddleOCR 2.8 (PP-OCRv3 detector, PP-OCRv4 recogniser), OpenCV |
| Weather | Open-Meteo API (no key), OpenWeatherMap (optional fallback) |
| Security | JWT (python-jose), bcrypt password hashing (passlib) |
| Deployment | Docker, Docker Compose, Render (Blueprint + Static Site) |
| Testing | pytest, pytest-cov (237 automated tests) |

### Project folders

```
SCAS/
├── backend/                FastAPI app
│   ├── app/
│   │   ├── api/v1/         routes: auth, users, farms, soil, weather,
│   │   │                   recommendation, fertilizer, history, market
│   │   ├── services/       business logic (one service per feature)
│   │   ├── repositories/   database access
│   │   ├── models/         SQLAlchemy tables
│   │   ├── schemas/        request/response models
│   │   ├── ocr/            preprocessing, engine, layout, field_parser, validation
│   │   ├── weather/        client, normalizer, cache, geocoding
│   │   ├── ml/             model registry + inference engine
│   │   ├── rules/          agronomic rules, confidence, ranking, explanation,
│   │   │                   deficiency detector, fertilizer selector + KB
│   │   ├── market/         market forecaster
│   │   └── core/           config, database, security, logging, errors
│   ├── alembic/            database migrations
│   ├── tests/              unit, integration, acceptance (objective-wise)
│   ├── Dockerfile, entrypoint.sh, requirements.txt
├── ml/                     training pipeline (datasets, features, training, evaluation)
│   └── market/             build_market_data.py (market artefacts)
├── datasets/               crop dataset, fertilizer KB, agronomic rules, OCR samples, market data
├── mobile/                 Flutter app (lib/screens, lib/repositories, lib/models …)
├── docs/                   phase reports, deployment guide, testing report
├── docker-compose.yml, render.yaml, .env.example
```

---

## 1. Install the prerequisites

| Tool | Version | Check |
|---|---|---|
| Git | any | `git --version` |
| Python | 3.11 | `python --version` |
| PostgreSQL | 14–16 (or use Docker) | `psql --version` |
| Docker Desktop | 24+ (for the Docker route) | `docker compose version` |
| Flutter SDK | 3.22+ stable | `flutter doctor` |
| VS Code or Android Studio | any | – |

Windows users: install Python from python.org (tick **Add to PATH**), Docker Desktop with WSL 2, and Flutter from flutter.dev. Use PowerShell for the commands below (replace `source .venv/bin/activate` with `.venv\Scripts\activate`).

You need about 6 GB of free disk space (PaddlePaddle and the Flutter SDK are large) and 8 GB of RAM.

---

## 2. Get the code

```bash
git clone https://github.com/REDDY4980/SCAS.git
cd SCAS
```

If you received `SCAS_changes.patch` (testing + deployment fixes + market module), apply it:

```bash
git checkout -b final
git am SCAS_changes.patch
```

---

## 3. Configure the environment

```bash
cp .env.example .env
python -c "import secrets; print(secrets.token_urlsafe(64))"   # copy the output
```

Edit `.env`:

| Variable | What to put | Notes |
|---|---|---|
| `JWT_SECRET` | the long random string you generated | The app refuses to start if it is shorter than 16 characters |
| `POSTGRES_PASSWORD` | any strong password | Used by Docker's Postgres |
| `DATABASE_URL` | `postgresql://scas_user:<password>@postgres:5432/scas_db` | Use `localhost` instead of `postgres` when running without Docker |
| `ALLOWED_ORIGINS` | `http://localhost,http://localhost:3000` | Add your deployed web-app URL later |
| `OPENWEATHERMAP_API_KEY` | optional | Only used if Open-Meteo is down |
| `MARKET_DATA_DIR` | leave empty locally | Docker sets `/app/datasets/market` |

---

## 4. Run the backend locally (without Docker)

### 4.1 Create the database

```bash
psql -U postgres -c "CREATE USER scas_user WITH PASSWORD 'your_password';"
psql -U postgres -c "CREATE DATABASE scas_db OWNER scas_user;"
```

### 4.2 Install Python packages

```bash
cd backend
python -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\activate
pip install --upgrade pip
pip install -r requirements.txt       # 5–15 min: PaddlePaddle is large
```

### 4.3 Train the crop model (once)

The trained model files are not stored in git. From the **repository root**:

```bash
cd ..
python -m ml.training.run_training --trials 20
```

Expected output (deterministic, seed 42):

```
Split: train=1760 val=220 test=220
Best params: {'learning_rate': 0.0357..., 'max_depth': 10, 'n_estimators': 233, ...}
Validation: accuracy=0.9955 | Test: accuracy=0.9909 f1_macro=0.9909
Artifacts written to ml/artifacts: model.joblib, label_encoder.joblib, ...
```

### 4.4 Create the tables and start the API

```bash
cd backend
export $(grep -v '^#' ../.env | xargs)      # Windows: set the variables in PowerShell
export DATABASE_URL=postgresql://scas_user:your_password@localhost:5432/scas_db
export MODEL_PATH=../ml/artifacts/model.joblib
export LABEL_ENCODER_PATH=../ml/artifacts/label_encoder.joblib
export UPLOAD_DIRECTORY=../storage/uploads
alembic upgrade head                         # creates 8 tables (3 migrations)
uvicorn app.main:app --reload
```

Open **http://localhost:8000/docs**. This is the interactive API page where you can try every endpoint. `GET /health` should return `{"success": true, ...}`. The start-up log should include `Database connectivity verified.`, `ML model loaded.` and (once PaddleOCR is installed) `OCR engine warmed up.`

---

## 5. How each module works (code walkthrough)

### 5.1 Authentication: `app/api/v1/auth.py`, `app/core/security.py`

* `POST /auth/register` checks the request (name, email, a 10–15 digit phone number, and a password of at least 8 characters with at least one letter and one digit), hashes the password with bcrypt and stores the user.
* `POST /auth/login` accepts an email or phone number plus the password and returns a JWT access token (valid for 24 h by default).
* Every other endpoint uses the `get_current_user` dependency, which decodes the token. Farms and reports belonging to another user return **404**, so the API never reveals that they exist.

### 5.2 Farms: `app/services/farm_service.py`

A farm stores its name, state, district, village, soil type and area (acres), plus its coordinates and **how they were obtained** (`location_source`):

* **`gps`**: the app detected the device position when the farm form opened (the farmer tapped *Allow*). The accuracy in metres is saved too, and the same position is saved on the **farmer profile**.
* **`district` / `state`**: no GPS, so the service geocoded the typed district (or the state, if the district was not found) with the Open-Meteo geocoding API.

Editing the district never overwrites a GPS position. `PUT /users/location` saves a newly detected position on the profile and, with `apply_to_farm_id`, on a farm. The app uses this for **Profile → Detect my location** and **Edit farm → Use GPS**.

### 5.3 Soil Health Card OCR: `app/ocr/`

| Step | File | What it does |
|---|---|---|
| 1 | `preprocessing.py` | Renders PDF pages at 200 dpi, caps size at 1600 px, crops borders, deskews, denoises (grayscale non-local means), boosts contrast (CLAHE), adaptive threshold |
| 2 | `engine.py` | PaddleOCR (English), loaded once per process. Models ship in `ml/paddleocr_models` so no download is needed |
| 3 | `layout.py` | Groups text boxes into table rows by their vertical position (15 px tolerance) |
| 4 | `field_parser.py` | Keyword + regex matching for pH, EC, OC, N, P, K, S, Zn, Fe, Mn, Cu, B; also reads district, soil type and date |
| 5 | `validation.py` | pH 0–14, values ≥ 0, mandatory pH/EC/OC/N/P/K; if mean OCR confidence < 0.85 the status is **needs_review** and the farmer corrects the values |

API flow: `POST /soil/upload?farm_id=…` (file) → `POST /soil/{id}/ocr` → `GET /soil/{id}` → optional `PUT /soil/{id}/correct`.

### 5.4 Weather: `app/weather/`

`client.py` calls Open-Meteo (`temperature_2m`, `relative_humidity_2m`, `wind_speed_10m`, `cloud_cover`, daily `rain_sum`). It retries once, then falls back to OpenWeatherMap if a key is set. `normalizer.py` converts both providers into one record and adds the IMD season (winter, summer, monsoon, post-monsoon). The `weather_snapshots` table is the cache: a snapshot younger than 30 minutes is reused.

### 5.5 Crop model: `ml/`

* **Dataset:** `datasets/crop_recommendation/Crop_recommendation.csv`, with 2,200 rows, 22 crops (100 each) and 7 features.
* **`feature_engineering/feature_engineer.py`:** the single fixed feature order `[N, P, K, temperature, humidity, ph, rainfall]`.
* **`training/trainer.py`:** 80/10/10 stratified split, Optuna TPE (20 trials) over learning rate, depth, trees, subsample, column sample, gamma and min child weight, each scored by 5-fold CV.
* **`evaluation/evaluator.py`:** accuracy, macro precision/recall/F1, confusion matrix, feature importance, latency.
* **Result:** 99.09% test accuracy, macro-F1 0.991, about 0.03 ms per prediction.

### 5.6 Hybrid recommendation: `app/services/recommendation_service.py` + `app/rules/`

1. Load the latest **validated** soil report and the latest weather snapshot (if either is missing the API returns 400 with a clear message).
2. Build the feature vector and get the **Top-5 probabilities** from XGBoost.
3. `agronomic_rules.py` computes an adjustment Δ for each crop:
   * −0.02 per macronutrient in the SHC "low" band, capped at −0.08
   * rice: +0.05 if pH is 5.5–6.5, otherwise −0.05
   * crops with no sourced rule: −0.01 and an "agronomic validation is limited" note
4. `confidence_engine.py`: `score = clip(probability + Δ, 0, 1)`. `crop_ranker.py` sorts the crops and the first becomes the primary recommendation.
5. `explanation_engine.py` writes a plain-language reason for each crop: the top features, pH, weather and every rule that fired.

### 5.7 Fertilizer: `app/rules/deficiency_detector.py`, `fertilizer_selector.py`

* Bands (SHC national reference): N < 280 low, 280–560 medium, ≥ 560 high (kg/ha); P < 10 / 10–25 / ≥ 25; K < 120 / 120–280 / ≥ 280; OC < 0.5 / 0.5–0.75 / ≥ 0.75 %.
* If the crop has a **sourced dose** in `datasets/fertilizer_knowledge_base` (UAS Bengaluru packages for maize, ragi, groundnut, hybrid paddy, cowpea, horse gram), that dose is returned with its citation.
* Otherwise, for each low nutrient: `product kg/ha = (threshold − measured) ÷ (nutrient % ÷ 100)` using Urea (46 % N), DAP (46 % P₂O₅) or MOP (60 % K₂O), multiplied by farm area × 0.4047 to get hectares. Example: N 200.6 on 3.5 acres → Urea 172.6 kg/ha × 1.42 ha ≈ **244.5 kg**.
* Every calculated item is labelled "calculated estimate, not a sourced dose".

### 5.8 Market price outlook: `app/market/forecaster.py`, `ml/market/build_market_data.py`

* **Data** (Government of India Agmarknet via data.gov.in, see `datasets/market/SOURCES.md`):
  * `current_prices.csv`: the 30-day median mandi price per crop (Karnataka if there are at least 20 records, otherwise all-India), with the 25th–75th percentile range
  * `seasonal_index.csv`: the month-of-year price pattern per crop, learnt from 2014–16 monthly APMC prices
  * `backtest.json`: out-of-sample accuracy of the seasonal forecast compared with "price stays the same"
* **Forecast:** `expected price (month m) = current price × S(m) ÷ S(current month)`.
* **Validation gate:** a forecast is shown **only** where it beat the naive forecast in the backtest (apple, chickpea, maize, orange, watermelon). For other crops the app shows the current price range and says so.
* **Advice:**
  * Gain below 8 % → **sell now**.
  * Perishable crop → **time the harvest** for the best month.
  * Storable crop → **hold until** the best month (if dry storage is available).
* **Endpoints:** `GET /market/crops` and `GET /market/{crop}/outlook?months=6`.
* **Refreshing prices:** download a fresh Agmarknet export from data.gov.in, then run
  `python -m ml.market.build_market_data --history <Monthly_data_cmo.csv> --recent <mandi_prices.csv> --out datasets/market`.

### 5.9 History: `app/services/history_service.py`

`GET /history` lists past analyses across all of the farmer's farms, newest first. `GET /history/{id}` combines the soil values, weather, recommendation and fertilizer advice into one record.

---

## 6. Run the Flutter app

```bash
cd mobile
flutter pub get
flutter doctor                          # fix anything it reports
```

| Target | Command |
|---|---|
| Chrome (web) | `flutter run -d chrome --dart-define=API_BASE_URL=http://localhost:8000` |
| Android emulator | `flutter create --platforms=android .` (once), then `flutter run --dart-define=API_BASE_URL=http://10.0.2.2:8000` |
| Real phone (same Wi-Fi) | `flutter run --dart-define=API_BASE_URL=http://<your-laptop-LAN-IP>:8000` |

The repository only ships the `web/` platform folder. `flutter create --platforms=android .` adds the Android folder without touching `lib/`. For a phone on Wi-Fi, also add `http://<your-laptop-IP>` to `ALLOWED_ORIGINS`.

### Screens and the API calls behind them

| Screen (`lib/screens/`) | What the farmer does | API |
|---|---|---|
| `splash_screen`, `login_screen`, `register_screen` | Choose language, register, log in | `/auth/register`, `/auth/login`, `/auth/me` |
| `farm_registration_screen`, `farm_management_screen`, `edit_farm_screen` | Add or edit farms (GPS filled silently) | `/farms` |
| `dashboard_screen` | Weather card, latest recommendation, quick actions | `/weather/current`, `/history` |
| `upload_screen` | Upload a SHC as PDF, from the gallery, or with the camera | `/soil/upload` |
| `ai_analysis_screen` | See extracted N, P, K, pH; correct if needed | `/soil/{id}/ocr`, `/soil/{id}/correct` |
| `crop_recommendation_screen` | Primary crop, explanation, Top-5, market card | `/recommendation`, `/market/{crop}/outlook` |
| `fertilizer_recommendation_screen` | Nutrient status, product, quantity for the farm | `/fertilizer/{id}` |
| `market_screen` | Current mandi price, 6-month outlook, when to sell | `/market/crops`, `/market/{crop}/outlook` |
| `history_screen`, `history_detail_screen` | Past analyses | `/history` |
| `profile_screen`, `profile_drawer` | Profile, **my location (detect / update)**, language, theme, logout | `/users/profile`, `/users/location` |

#### Location permission (GPS)

* **Web:** browsers share location only on **https** pages or `localhost`. Opening the app as `http://<LAN-IP>:port` shows *"Browsers only share location on secure (https) pages"*. Use the Render https link or `localhost`.
* **Android / iOS:** after `flutter create --platforms=android,ios .`, run `bash tool/enable_location_permissions.sh` from `mobile/`. It adds `ACCESS_FINE_LOCATION`/`ACCESS_COARSE_LOCATION` to `AndroidManifest.xml` and `NSLocationWhenInUseUsageDescription` to `Info.plist`. Without them the phone refuses location without asking.
* **What the farmer sees:** the farm form shows *Detecting your location…* and then either *Location detected (within 24 m)* or the reason it failed, with a *Try again* button. The profile shows the saved coordinates, accuracy and date.

All screen text comes from `lib/localization/app_strings.dart`, which has 59 keys in English, Kannada, Hindi and Telugu.

---

## 7. Test everything

From `backend/` (with the virtual environment active and the model trained):

```bash
pytest tests -v --cov=app                   # 212 tests: unit + integration + acceptance
pytest tests/acceptance -v                  # 29 objective-wise tests (O1–O5)
cd .. && pytest ml/tests --cov=ml           # 25 ML tests
```

| Suite | Tests | Covers |
|---|---|---|
| Unit | 102 | OCR parser/layout/validation, weather, rules, fertilizer, market, security |
| Integration | 81 | Every API route against an in-memory database, including the real SHC PDF |
| Acceptance | 29 | Objectives O1 crop, O2 fertilizer, O3 market, O4 usability/security/speed, O5 robustness |
| ML | 25 | Dataset loader, features, trainer, evaluator, inference |

After deployment, run the live smoke test: `./deployment/scripts/smoke_test.sh https://<backend-url>`.

---

## 8. Run everything with Docker (recommended for demos)

```bash
cp .env.example .env            # fill JWT_SECRET and POSTGRES_PASSWORD (section 3)
docker compose up --build
```

What happens:

1. **postgres** starts and passes its health check.
2. The **backend** image installs requirements and trains the crop model (about 1 minute).
3. `entrypoint.sh` waits for the database, trains the model if it is missing (compose mounts `./ml`), runs `alembic upgrade head` and starts Uvicorn.
4. The API is served at http://localhost:8000/docs. Optional pgAdmin: `docker compose --profile dev up pgadmin` → http://localhost:5050.

Then run the web app against it: `cd mobile && flutter run -d chrome --dart-define=API_BASE_URL=http://localhost:8000`.

---

## 9. Deploy to the cloud (Render)

### 9.1 Backend + database (Blueprint)

1. Push the code (with the patch applied) to GitHub.
2. Go to render.com → **New + → Blueprint** → connect `REDDY4980/SCAS` → **Apply**. `render.yaml` creates:
   * `scas-backend`: a Docker web service with health check `/health` and an auto-generated `JWT_SECRET`
   * `scas-db`: PostgreSQL
3. The first build takes 10–20 minutes (PaddlePaddle plus model training). Then open `https://<backend>.onrender.com/health`.

### 9.2 Web app (Static Site)

1. Go to **New + → Static Site** and pick the same repository.
2. **Build command:**
   ```
   git clone https://github.com/flutter/flutter.git -b stable --depth 1 _flutter_sdk && export PATH="$PWD/_flutter_sdk/bin:$PATH" && cd mobile && flutter pub get && flutter build web --release --dart-define=API_BASE_URL=$API_BASE_URL
   ```
3. **Publish directory:** `mobile/build/web`.
4. **Environment:** set `API_BASE_URL` to `https://<backend>.onrender.com`.
5. After it deploys, set the backend's `ALLOWED_ORIGINS` to the static site URL. Render redeploys automatically.

### 9.3 Android APK (to install on a phone)

```bash
cd mobile
flutter create --platforms=android .
flutter build apk --release --dart-define=API_BASE_URL=https://<backend>.onrender.com
# APK: mobile/build/app/outputs/flutter-apk/app-release.apk
```

### 9.4 Before a live demo

* **Render free tier:** 512 MB RAM, sleeps after 15 minutes idle (the first request then takes 30–60 s), and the free PostgreSQL expires after 30 days. PaddleOCR plus the model can exceed 512 MB. For the review day, use a paid instance or run `docker compose up` on a laptop.
* **Warm up the server:** open `/health` a minute before presenting.
* **Uploads:** uploaded files are not kept across restarts on the free tier. That is fine for a demo.
* **After deploying:** run the smoke test against the deployed URL.

---

## 10. API reference

| Method | Path | Purpose |
|---|---|---|
| POST | `/api/v1/auth/register` | Create account |
| POST | `/api/v1/auth/login` | Get JWT |
| GET | `/api/v1/auth/me` | Current user |
| GET/PUT | `/api/v1/users/profile` | Profile and settings (includes the saved location) |
| PUT | `/api/v1/users/location` | Save detected GPS location on the profile (and optionally a farm) |
| GET/POST | `/api/v1/farms` | List / create farms |
| GET/PUT/DELETE | `/api/v1/farms/{farm_id}` | Read / edit / delete a farm |
| POST | `/api/v1/soil/upload?farm_id=` | Upload SHC (PDF/JPG/PNG, ≤ 10 MB) |
| POST | `/api/v1/soil/{report_id}/ocr` | Run OCR + validation |
| GET | `/api/v1/soil/{report_id}` | Read extracted values |
| PUT | `/api/v1/soil/{report_id}/correct` | Farmer correction |
| GET | `/api/v1/weather/current?farm_id=` | Current weather (cached 30 min) |
| POST | `/api/v1/weather/refresh?farm_id=` | Force refresh |
| GET | `/api/v1/weather/history/{farm_id}` | Past snapshots |
| POST | `/api/v1/recommendation?farm_id=` | Hybrid crop recommendation |
| GET | `/api/v1/recommendation/{id}` | Read a recommendation |
| POST/GET | `/api/v1/fertilizer/{recommendation_id}` | Fertilizer advice |
| GET | `/api/v1/history` | Past analyses |
| GET | `/api/v1/history/{recommendation_id}` | Full analysis record |
| GET | `/api/v1/market/crops` | Market data coverage |
| GET | `/api/v1/market/{crop}/outlook?months=6` | Price outlook and when to sell |
| GET | `/health` | Health check |

Every response uses the envelope `{success, message, data, errors, timestamp}`.

---

## 11. Troubleshooting

| Problem | Cause | Fix |
|---|---|---|
| `JWT_SECRET is missing or too short` at start-up | `.env` not loaded | Set a 64-character secret (section 3) |
| `/recommendation` returns 500 and the log says `Missing required ML artifact` | Model not trained | `python -m ml.training.run_training --trials 20` from the repo root |
| `/recommendation` returns 400 "No validated soil report" | OCR status is `needs_review` or `failed` | Correct the values on the analysis screen (`PUT /soil/{id}/correct`) |
| `/recommendation` returns 400 "No climate data" | Weather never fetched | Open the dashboard or call `GET /weather/current` first |
| Weather returns 503 | No internet / Open-Meteo blocked | Check the network; set `OPENWEATHERMAP_API_KEY` as fallback |
| OCR is slow the first time | PaddleOCR loading | Normal; it is warmed up at start-up afterwards |
| Web app shows a CORS error | Origin not allowed | Add the web URL to `ALLOWED_ORIGINS` and restart the backend |
| Android emulator cannot reach the API | `localhost` points to the emulator | Use `http://10.0.2.2:8000` |
| `pip install` fails on PaddlePaddle | Unsupported Python | Use Python 3.11 (64-bit) |
| Location "not detected" in the browser | Page opened over http, or permission blocked | Use the https link or localhost; allow location in the browser's site settings and tap *Try again* |
| Location never asked on Android | Permissions missing from the manifest | `bash tool/enable_location_permissions.sh`, then rebuild |
| Market outlook returns 404 | No mandi data for that crop (moth beans) | Expected; 21 of the 22 crops are covered |

---

## 12. Demo script for the project review (5 minutes)

1. Open the app and switch the language to Kannada and back (multilingual).
2. Register a farmer and add the farm "Bagalkote, Karnataka, 3.5 acres". Tap **Allow** when the browser asks for location; the form shows *Location detected*. Open **Profile** to show the saved location.
3. The dashboard shows live weather.
4. Go to **Soil Test → PDF** and upload `datasets/ocr_calibration/01_Karnataka_SHC_redacted_2017.pdf`. The extracted N 200.6, P 4.19, K 122.8 and pH 7.7 appear.
5. **Recommended Crops:** the primary crop with its explanation, the Top-5 list, and the market card.
6. **Fertilizer:** Urea ≈ 244.5 kg and DAP ≈ 17.9 kg for the farm, with precautions.
7. **Market:** pick *maize*, then *watermelon*, to show "sell now" versus "aim harvest for Nov 2026", the 6-month chart and the tested accuracy.
8. **History:** the analysis is saved.
9. Show `http://<backend>/docs` and the test report (`docs/testing/`).
