# SCAS — OCR memory fix, accuracy fixes, weather/location fixes and free-tier readiness

Branch `feature/scas-free-tier-ocr` (from `8ba2090`, the deployed commit).
All numbers below were measured in this work; nothing is estimated unless
it says so.

## 1. What was wrong

Render reported *"Ran out of memory (used over 512MB)"* when a farmer
triggered OCR. Measured on the original code (same pinned packages, real
app, real PaddleOCR, both calibration PDFs, 2 rounds):

| Stage | RSS |
|---|---|
| App imported | 148 MB |
| After startup (eager PaddleOCR warm-up + crop model) | **690 MB** — already over 512 MB |
| During OCR of a 4-page PDF | **2,691 MB** |
| Peak | **2,811 MB** |

Root causes, isolated one at a time:

1. **PaddlePaddle 2.6 enables oneDNN for CPU inference by default.**
   PaddleOCR 2.8.1's `enable_mkldnn=False` only skips *enabling* it; it
   never calls `Config.disable_mkldnn()`. oneDNN caches kernels/buffers per
   distinct input shape, without bound. Text-line recognition produces a
   new input width for nearly every batch (6 different widths: +800 MB;
   6 identical widths: +17 MB; 16 widths up to 1200 px: 3.2 GB).
2. **Detection/recognition never release Paddle's buffers**
   (`try_shrink_memory()` is only called by the angle classifier).
3. **The Paddle runtime itself** maps ~220 MB of `libpaddle.so` and adds
   ~100 MB anonymous memory on import, plus ~150 MB for the three
   predictors — before a single page is processed.
4. **Eager OCR warm-up at startup** made every instance pay all of that
   even if nobody scans a report.
5. Secondary: all PDF pages were rendered and pre-processed into a list
   before OCR; no page-count or pixel-size limit (a 10 MB PDF/PNG could
   expand to gigabytes); no protection against duplicate/concurrent OCR
   runs (each adds a full working set).

Fixing (1)+(2) inside Paddle cut the peak from 2.8 GB to ~1.0 GB RSS (728 MB
anonymous) with byte-identical output — still far above 512 MB because of
(3). That fix is kept for the optional Paddle backend (§4).

## 2. The fix

**Same models, same algorithm, different runtime.** The bundled PP-OCR
weights were converted 1:1 to ONNX (`ml/paddleocr_models/onnx/`, provenance
in its README) and `backend/app/ocr/ppocr_onnx.py` is a faithful port of the
exact PaddleOCR 2.8.1 code paths SCAS uses (DB detection, quad filtering,
reading-order sort, rotate-crop, 180° classifier, SVTR recognition, CTC
decode), executed on ONNX Runtime 1.19.2. PaddlePaddle is no longer loaded.

Parity, verified by test (`test_onnx_port_reproduces_paddleocr_text_exactly`):
**599 / 599 text lines identical** to PaddleOCR 2.8.1 + PaddlePaddle 2.6.2
on both calibration PDFs, confidence within 0.0001.

Rejected alternatives (measured): RapidOCR (same models, different
pre/post-processing — misread `pH` as `pA` on a calibration page);
PaddleOCR's own `use_onnx=True` (still imports PaddlePaddle); smaller
detection size (lost text boxes); INT8 quantisation of recognition (no
speed-up, model is convolution-bound); Tesseract (not needed — the PP-OCR
models fit once Paddle is removed).

## 3. Memory and time after the fix

### In-process, same harness as the baseline

| | Before | After |
|---|---|---|
| Startup RSS | 690 MB | **245 MB** |
| Peak RSS (4 OCR runs) | 2,811 MB | **469 MB** (359 MB anonymous) |

### Docker image, hard 512 MB limit, no swap, real PostgreSQL (closest to Render)

| Workload | Result |
|---|---|
| Idle after startup | 157–159 MB |
| 1-page farmer card, 0.1 CPU | 200, **peak 347 MB**, 130–137 s |
| 2-page report, 0.1 CPU | 200, 160–170 s |
| 4-page report, 0.1 CPU | 200, 330 s |
| 5-page PDF (max allowed) ×2, 1 CPU | 200, 52 s each, peak 359 MB |
| 6-page PDF | 422 in 0.0 s, nothing rendered |
| 3 simultaneous OCR requests | all 200, processed one at a time (45 / 92 / 139 s) |
| Duplicate request for a running report | 409 |
| **Whole stress session** | **peak cgroup RSS 364 MB**, max usage 422 MB incl. reclaimable page cache, memory-limit hits 0, **OOM-killed: no, restarts: 0** |

Target was ≤ ~430 MB peak RSS: **met** (364 MB).

**Time is the free tier's real limit.** Render's free web service has
0.1 CPU. OCR needs ~11–13 CPU-seconds per page (the same order as the
original Paddle engine), i.e. ~2 minutes per page on the free tier. The
Flutter app previously gave up after 90 s, so it now waits up to 15
minutes and polls the report if the connection drops; the backend queues
reports one at a time (default wait 300 s). Render web requests may run up
to 100 minutes (Render articles; not verified against formal docs).

## 4. Accuracy (real OCR, no mocks)

Ground truth: `tests/fixtures/real_shc_samples.py` (Karnataka card, Tasar
cards 1 and 4) plus Tasar cards 2 and 3, transcribed by hand from the
rendered pages for this work.

| Document | Before (production code) | After |
|---|---|---|
| Tasar SHC cards 1–4 (printed sideways; 4 pages, 48 values) | **0 / 48** extracted (all `needs_review`) | **48 / 48 exact**, all `success` |
| Karnataka SHC (4-page textbook excerpt, 12 values) | `success` with **zinc = 15.0 and iron = 1.0 (wrong; true 0.27 / 0.71)** — a false acceptance | all 12 true values read; disagreement flagged → `needs_review` |
| Mandatory-field accuracy | 6/6 Karnataka, 0/24 Tasar | **30 / 30** |
| False acceptances on calibration set | 1 report (2 wrong values) | **0** |

Three pipeline fixes produced this, each with a regression test:

1. **Page rotation** (`OCR_AUTO_ROTATE`, default on): if most text boxes are
   tall, the page is turned 90° and the angle classifier picks the
   direction. Upright pages take exactly the original path.
2. **Row grouping** (`layout.py`): fragments are compared with the row's
   mean height, not just the previous fragment. A neighbouring table on an
   offset row grid had chained the Sulphur and Zinc rows, so zinc took
   sulphur's value.
3. **Conflicting readings** (`field_parser.py` + `validation.py`): the first
   value per field still wins (unchanged rule), but if the report contains
   a different value for the same parameter, the report goes to manual
   review with a warning naming the values. The 0.85 confidence threshold,
   ranges and mandatory-field rules are unchanged.

Also fixed: a manual correction now marks the report `success` only when
all six mandatory values are present (previously an incomplete correction
became `success` and shadowed the farm's last complete report for
recommendations). The review form now requires those six values and shows
the backend's warnings.

Robustness tests on real OCR: PNG/JPG photo inputs read correctly; 180°
and 90° rotated photos and a degraded 100-DPI JPEG never produce an
accepted wrong value.

## 4b. Weather and location (tested against the live Open-Meteo API)

Found by running the real code against live Open-Meteo (previously blocked
from the development sandbox, so never exercised live):

| Problem | Evidence (live) | Fix |
|---|---|---|
| Country filter silently ignored — searches were worldwide | `country=IN`: "Daman" → Damanhur (Egypt), "Leh" → Le Havre (France), "Panaji" → Guatemala | Use the API's real parameter `countryCode`; also reject non-Indian results |
| A same-named place in another state could be chosen | old code fell back to the top worldwide result when no candidate matched the state | A recognised Indian state is now a hard constraint |
| Common/official district names not found | Bagalkote, Gulbarga, East Godavari, North 24 Parganas → no location; Bellary → a road in Bengaluru; Vijayapura → a village 450 km away | Verified alias table (renamed cities, district HQs), tried first; exact name + population preferred; 1–2 letter spelling-variant search |
| "Fall back to the state" never worked | State names (Karnataka, West Bengal …) are not in the gazetteer | Verified table of state/UT capitals as the approximate last resort; common state spellings (Orissa, Tamilnadu …) understood |
| No-match treated as throttling | ordinary no-match also omits `results`; each miss slept 1.5 s twice | delay 0.5 s, no retry on secondary lookups |
| One flaky connection = no location | TLS handshake timeouts seen live | one retry on transport errors |
| Farm saved without coordinates never got weather (400 forever) | — | weather request now geocodes such a farm once and saves it |
| 2 s weather timeout too tight on 0.1 CPU | a live request needed a retry after a timeout; with 2 s it would fail | 8 s timeout (results cached 30 min) |
| **Crop model fed today's rain** (0 mm on most days) | 4 farms: today 0.0 mm each; last 30 days 25 / 49 / 256 / 250 mm. Model trained on 20–298 mm | rainfall = total of the last 30 complete days (`past_days=30`, same request) |

Geocoding accuracy, 37 real district/state inputs (incl. renamed, district-only
and misspelled-state cases), resolved at district level within 60 km of the
district HQ: **before 21/37 (Bagalkote — the calibration card's own district —
and others got no location), after 37/37.**

Live end-to-end on the Docker image at **0.1 CPU / 512 MB**: 5 farms created
without GPS were geocoded at district level (~1 s each); live weather for all
5 (0.4–1.0 s; one 9 s request recovered via retry; cached repeats 0.01–0.05 s);
crop recommendation 200 using real 30-day rainfall. In the Flutter web UI a new
farmer typing only "Gulbarga, Karnataka" got a dashboard with live weather.

Not changed: the browser GPS capture in the app (already requires HTTPS and
permission, 20 s timeout, falls back to the district/state lookup). The
optional OpenWeatherMap fallback still reports 1-hour rain (it has no 30-day
history; it is not configured on Render).

## 5. Changed files

Backend
- `app/ocr/ppocr_onnx.py` (new) — PP-OCR pipeline on ONNX Runtime.
- `app/ocr/engine.py` — ONNX engine (default), optional Paddle engine with
  the oneDNN/shrink fixes, thread-safe lazy singleton, typed errors
  (`OCRInitializationError`, `OCRInferenceError`, `OCRBusyError`), model-file
  verification, `ocr_slot()` concurrency limit.
- `app/ocr/preprocessing.py` — pages rendered/pre-processed one at a time
  (`iter_preprocessed_pages`), page-count and pixel limits checked before
  allocation, PDFium handles closed deterministically, pixel-identical
  direct BGR render (3 fewer full-page copies). All pre-processing steps
  unchanged; `preprocess_file()` kept for compatibility.
- `app/services/soil_service.py` — sequential page OCR, `processing` status,
  409 for duplicate runs, 503 when busy/engine unavailable, 422 with a
  specific message for bad documents, report always ends `failed` (never
  stuck) on errors, same report id retryable; correction completeness rule.
- `app/ocr/layout.py`, `app/ocr/field_parser.py`, `app/ocr/validation.py` — §4.
- `app/main.py` — no OCR model loading at startup (DB check and crop model kept).
- `app/core/config.py` — OCR settings (all optional, validated, safe defaults).
- `requirements.txt` — removed `paddleocr`, `paddlepaddle`; added
  `onnxruntime==1.19.2`, `pyclipper==1.4.0`, `shapely==2.2.0`. All other pins
  unchanged (NumPy 1.26.4, OpenCV 4.10.0.84, ML stack). `requirements-paddle.txt`
  (new, optional) restores the Paddle backend.
- `Dockerfile` — fails the build if an ONNX model file is missing;
  `OCR_MODEL_DIR`, `OMP_NUM_THREADS=1`, `MALLOC_ARENA_MAX=2`; Paddle weight copy
  removed. `Dockerfile.dockerignore` — excludes the unused Paddle-format weights.
- `entrypoint.sh` — explicit `--workers 1`; comments updated.

- `app/weather/geocoding.py`, `app/weather/client.py`, `app/weather/normalizer.py`,
  `app/services/weather_service.py` — §4b.
- `tests/conftest.py` — tests point the weather/geocoding providers at a closed
  local port, so the suite never depends on live network access.

Models: `ml/paddleocr_models/onnx/` (new, 10.6 MB).

Frontend (Flutter)
- `lib/config/app_config.dart` — OCR timeout 90 s → 15 min (measured), poll interval.
- `lib/screens/ai_analysis_screen.dart` — waits for a still-running OCR
  (timeout / dropped connection / 409 / 502 / 504) by polling the report;
  "can take a few minutes" message; review form shows backend warnings,
  requires the six mandatory values, and flags missing `organic_carbon`
  (snake_case/camelCase mismatch).

Docs: this file, `DEPLOYMENT.md`, model README.

## 6. Tests

- Existing suite: **211 passed, 1 skipped** before changes → all still pass,
  no assertion changed.
- Final: **285 passed, 1 skipped** backend (the skip is the pre-existing
  optional Tesseract test) + 25 ML tests passed.
- New: `tests/unit/test_ocr_preprocessing.py`, `tests/unit/test_ocr_engine.py`,
  `tests/unit/test_ocr_conflicts_and_rows.py`,
  `tests/integration/test_soil_ocr_reliability.py`,
  `tests/integration/test_ocr_engine_real.py` (real engine, no mocks),
  `tests/unit/test_geocoding_india.py`, `tests/unit/test_weather_rainfall_window.py`,
  `tests/integration/test_weather_lazy_geocode.py`.
- Flutter: `flutter analyze` — no new findings (same 35 pre-existing
  info/warning items as the original code); `flutter build web` succeeds.

## 7. Feature verification matrix

Container = Docker image, 512 MB / no swap, PostgreSQL 16, driven over HTTP.
UI = built Flutter web app in headless Chromium against that container.

| Feature | Evidence | Status |
|---|---|---|
| Register / login / bad password / JWT-protected `/me` | Container HTTP (201/401/200/401/200) + UI register & login | Verified |
| Profile | Container `GET /users/profile` 200; UI | Verified |
| Farm create / list / get / ownership | Container + UI farm gate; existing tests | Verified |
| Geocoding (district/state → location) | Live Open-Meteo, 37 inputs 37/37; container + UI | Verified |
| Device GPS | App code reviewed; headless browser has no GPS | Not device-tested |
| Weather | Live Open-Meteo through container (0.1 CPU) + UI dashboard | Verified |
| Market crops / outlook | Container + UI (200) | Verified |
| Soil upload | Container + UI (202) | Verified |
| OCR (1, 2, 4, 5 pages; limit; corrupt; busy; duplicate) | Container + UI + new tests | Verified |
| Manual review + correction + persistence | UI: form blocks empty pH, corrected values in PostgreSQL | Verified |
| Crop recommendation (XGBoost) | UI `POST /recommendation` 200 (top-5 shown) | Verified |
| Fertilizer recommendation | UI `POST /fertilizer/{id}` 200 | Verified |
| History list | UI `GET /history` 200 | Verified |
| Alembic migrations on PostgreSQL | Container: `alembic_version = 0003_location_fields` | Verified |
| Render deployment | — | **Not done (awaiting approval)** |

Local stand-ins (test database only, earlier OCR runs): one weather snapshot
and one farm's coordinates were inserted before live Open-Meteo access was
enabled; weather/location were afterwards verified live (§4b). The Docker `apt-get` step could not run here (Debian mirror blocked
by sandbox egress policy); it is unchanged from the Dockerfile that already
builds on Render. Flutter web was built with Flutter 3.50.0 and, for the
local preview only, `--no-web-resources-cdn` (sandbox blocks gstatic.com).

## 8. Known limitations / risks

- **OCR is slow on 0.1 CPU** (~2 min/page). Memory fits; speed does not
  improve without more CPU (Render Starter, 0.5 CPU, would be ~5× faster —
  not changed, per instruction).
- While a report is being read, the single 0.1 CPU is shared, so other
  requests are slower during that time.
- Render free instances can restart at any time; an OCR interrupted that
  way leaves the report `processing` until the farmer retries (retry works).
- Uploaded files are not persistent on Render free (pre-existing).
- A multi-card PDF (several farmers in one file) goes to manual review —
  intended: values from different cards must not be merged silently.
- Pre-existing, untouched: register screen stays on the form after a 201
  in the web build; dashboard "Crops" opens the upload screen.

## 9. Deploy (after approval)

1. Push `feature/scas-free-tier-ocr`; point `scas-backend` at it (or merge
   per your process). No environment variable changes are required.
2. Rebuild **both** `scas-backend` and `scas-frontend` (the frontend carries
   the new OCR timeout/polling).
3. Check `/health`, then one real upload → OCR; watch Render's Metrics tab
   (memory should stay under ~370 MB) and logs (`OCR models loaded (onnx)`).

## 10. Rollback

Redeploy commit `8ba2090` on both services (Render → Manual Deploy →
specific commit). No database migration was added, so rollback needs no
database change. Reports created with status `processing`/`needs_review`
remain readable by the old code.
