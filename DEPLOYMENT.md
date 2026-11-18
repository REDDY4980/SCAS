# Deploying SCAS to Render

Two pieces, deployed separately: the backend (FastAPI + Postgres) via
the `render.yaml` Blueprint in this repo, then the frontend (Flutter
web) as a Render Static Site pointed at the backend's live URL.

## 1. Sign up / log in at Render

https://render.com — free account, GitHub login is easiest since
you'll be connecting this repo.

## 2. Deploy the backend + database

1. Render dashboard -> **New +** -> **Blueprint**.
2. Connect the `REDDY4980/SCAS` GitHub repo.
3. Render detects `render.yaml` at the repo root and shows two
   resources: `scas-backend` (web service) and `scas-db` (Postgres).
   Click **Apply**.
4. First build takes several minutes (Python dependencies, plus the
   crop model is trained inside the image). OCR runs the bundled PP-OCR
   models on ONNX Runtime — PaddlePaddle is no longer installed, see
   `docs/OCR_MEMORY_REPORT.md`.
5. Once live, open the service and copy its URL, e.g.
   `https://scas-backend-xxxx.onrender.com`. Confirm it's actually
   healthy: visit `<that-url>/health` — should return
   `{"success":true,...}`.

**Free tier note:** Render's free web services spin down after 15
minutes of inactivity and take ~30-60s to wake up on the next request
— expect a slow first request after idle periods. The free Postgres
instance is also time-limited (expires after 30 days on Render's free
tier); when that happens, create a new free Postgres (on Render, or an
external option like Neon/Supabase) and update `DATABASE_URL`.

## 3. Deploy the frontend

1. Render dashboard -> **New +** -> **Static Site**.
2. Connect the same repo.
3. Configure:
   - **Build Command**:
     ```
     git clone https://github.com/flutter/flutter.git -b stable --depth 1 _flutter_sdk && export PATH="$PWD/_flutter_sdk/bin:$PATH" && cd mobile && flutter pub get && flutter build web --release --dart-define=API_BASE_URL=$API_BASE_URL
     ```
   - **Publish Directory**: `mobile/build/web`
4. Under **Environment**, add a variable:
   - `API_BASE_URL` = the backend URL from step 2.5 (e.g.
     `https://scas-backend-xxxx.onrender.com`)
5. Deploy. This build also takes a while (~5-10 min) since it
   downloads the Flutter SDK fresh each time.
6. Once live, copy the static site's URL, e.g.
   `https://scas-frontend-xxxx.onrender.com`.

## 4. Connect them: allow the frontend's origin on the backend

The backend's CORS policy (`ALLOWED_ORIGINS`) defaults to
`http://localhost` in `render.yaml` — the deployed frontend can't call
it until you add its real URL.

1. Render dashboard -> `scas-backend` -> **Environment**.
2. Edit `ALLOWED_ORIGINS` to the frontend's URL from step 3.6, e.g.
   `https://scas-frontend-xxxx.onrender.com` (comma-separate if you
   later add a custom domain too).
3. Save — Render redeploys the backend automatically.

## 5. Verify

Open the frontend URL, register an account, and walk through: farm
registration -> dashboard weather -> soil report upload -> crop
recommendation -> fertilizer recommendation. Check the browser
console and the backend's Render logs tab for errors if anything
looks off.

## Notes / limitations of the free tier

- **Cold starts**: the free backend sleeps after 15 min idle; the
  first request after that can take 30-60s while it wakes up.
- **OCR speed on the free tier (0.1 CPU)**: reading a soil report takes
  roughly 2 minutes per page (measured in a container limited to 0.1 CPU /
  512 MB; ~10x faster on 1 CPU). Memory stays far inside 512 MB (peak
  ~365 MB measured). The Flutter app waits up to 15 minutes
  (`ocrTimeout` in `mobile/lib/config/app_config.dart`) and polls the
  report if the connection drops, so the frontend must be rebuilt and
  redeployed together with the backend. Only one report is OCR'd at a
  time; others queue (`OCR_QUEUE_TIMEOUT_SECONDS`, default 300 s).
- **Weather & farm location** use Open-Meteo (no key). Farms saved without
  GPS are located from district/state; rainfall given to the crop model is
  the last 30 days' total. See `docs/OCR_MEMORY_REPORT.md` §4b.
- **OCR settings** (all optional, safe defaults — none need to be set on
  Render): `OCR_MAX_PDF_PAGES` (5), `OCR_PDF_DPI` (200),
  `OCR_MAX_IMAGE_DIMENSION` (1600), `OCR_MAX_IMAGE_PIXELS` (60,000,000),
  `OCR_MAX_CONCURRENT` (1), `OCR_QUEUE_TIMEOUT_SECONDS` (300),
  `OCR_NUM_THREADS` (1), `OCR_USE_ANGLE_CLS` (true), `OCR_AUTO_ROTATE`
  (true), `OCR_BACKEND` (onnx), `OCR_MODEL_DIR` (set in the Dockerfile).
- **Database expiry**: Render's free Postgres expires after 30
  days. For a longer-lived public demo, consider a persistent free
  Postgres from Neon or Supabase instead, and point `DATABASE_URL` at
  that.
- **Uploaded files are not persistent** on the free web service —
  Render's free tier has no attached persistent disk, so anything
  written to `/app/storage/uploads` is lost on redeploy/restart. Fine
  for a demo; for anything longer-lived, add a paid persistent disk or
  move uploads to object storage (S3-compatible).
- **Secrets**: `JWT_SECRET` is auto-generated by Render
  (`generateValue: true` in `render.yaml`) — you never need to type it
  in. `OPENWEATHERMAP_API_KEY` is optional (only used as a weather
  fallback) and isn't set by default.
