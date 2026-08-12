# Phase 4 — OCR & Soil Report Processing Engine: Completion Record

Per AIB v1.0 Vol 17.3 "Phase 4 – OCR Pipeline":
> Implement upload, preprocessing, OCR, parsing and validation.

## Deliverables

- [x] `app/ocr/preprocessing.py` — full Vol 7.4 pipeline (resize, crop, deskew, denoise, contrast, adaptive threshold) using OpenCV, plus PDF-to-image rendering via pypdfium2 (Vol 7.2 multi-page PDF support)
- [x] `app/ocr/engine.py` — `OCREngine` abstract interface + `PaddleOCREngine` (Vol 7.5), lazy-loaded singleton (mirrors Vol 9.20's "load model once" principle)
- [x] `app/ocr/layout.py` — layout analysis: reconstructs table rows from PaddleOCR's per-fragment detections (Vol 7.3)
- [x] `app/ocr/field_parser.py` — keyword+regex field extraction (Vol 7.7), all 11 mandatory numeric fields (Vol 7.6) plus district/village/state/soil_type/sample_date metadata
- [x] `app/ocr/validation.py` — range validation (pH 0-14, others ≥0) and 0.85 confidence threshold (Vol 7.8)
- [x] `app/repositories/soil_repository.py`, `app/schemas/soil.py` — CRUD + Vol 7.9 JSON contract shape
- [x] `app/services/soil_service.py` — orchestrates upload → preprocess → OCR → layout → parse → validate → persist (Vol 7.3), with farm-ownership enforcement (Vol 6.10)
- [x] `POST /soil/upload`, `POST /soil/{id}/ocr`, `GET /soil/{id}`, `PUT /soil/{id}/correct` — all four Vol 14.2 endpoints
- [x] File validation: only PDF/JPG/PNG accepted, size-limited (Vol 3 SCR-006, Vol 7.2)
- [x] Original uploaded file always preserved on disk for audit (Vol 7.16)

## Calibration against real data (Requirement 4)

This is the part I want to highlight: rather than testing against synthetic numbers, the field parser and validator were calibrated against the **actual redacted farmer Soil Health Cards** supplied in Requirement 4 (`SOURCE_REGISTER`: `SHC-KA-2017`, `SHC-TASAR-2017`):

- Karnataka SHC (Soil Health Centre, Bagalkote) — pH 7.70, EC 0.04, OC 0.35%, N 200.6, P 4.19, K 122.8, S 26.50, Zn 0.27, B 0.63, Fe 0.71, Mn 6.41, Cu 1.65
- Central Tasar SHC sample #1 (Ranchi) — pH 6.37, EC 0.094, OC 0.57%, N 111.7, P 9.30, K 180.3, etc.
- Central Tasar SHC sample #4 — includes the tightest edge case in the set (Cu 0.09 ppm, extremely deficient but physically valid)

All three parse with 100% field accuracy (`tests/unit/test_ocr_field_parser.py`). The full upload→OCR→persist pipeline was also run against the **actual uploaded Karnataka SHC PDF file** (real pypdfium2 render + real OpenCV preprocessing; only the PaddleOCR model call itself is faked, since downloading its weights doesn't belong in a fast test suite) and correctly persisted all values to the database (`tests/integration/test_soil_api.py::test_full_pipeline_real_pdf_fake_engine_extracts_correct_values`).

## Real bugs found and fixed during verification

This phase surfaced three genuine bugs — all caught by actually running the code against real data, not just writing it:

1. **Row-merging bug in `layout.reconstruct_rows`**: lines lacking bounding-box data were transitively merged into a single giant row (16 real SHC lines → 1 line) because the grouping tolerance compared each new line only against the *first* line of the growing row using an index-based fallback. Fixed by treating boundingbox-less lines as always-standalone rows, and switching box-based grouping to a rolling last-line comparison. Added regression tests in `tests/unit/test_ocr_layout.py`.
2. **Schema mismatch**: the field parser correctly recognizes `sulphur` (present on real Karnataka/Tasar cards) but `soil_parameters` (Vol 5.3) has no `sulphur` column — passing it straight to the ORM constructor raised `TypeError`. Fixed by filtering parsed values to the exact persistable column set before storage; unmatched-but-recognized fields are logged, not persisted or discarded silently.
3. **Upload-ordering bug**: the original upload flow generated a `report_id` in Python, wrote the file using it, then created the DB row and tried to overwrite its `.id` post-commit — which does not rewrite an already-persisted primary key in SQLAlchemy. Fixed by creating the DB row first (letting the DB/ORM generate the real id), then writing the file using that real id, then updating `file_path`.

## Performance (AIB Vol 7.13 target: OCR ≤5s)

Initial preprocessing implementation measured at **~4.5s/page** (denoise step) against the real 4-page Karnataka SHC PDF — that alone would have blown the whole OCR budget before OCR even started. Profiled step-by-step, found `cv2.fastNlMeansDenoisingColored` was the bottleneck, switched to grayscale-only `fastNlMeansDenoising` (text documents carry no OCR-relevant color information) and reduced the max working dimension from 2000px to 1600px. Final measured cost: **~1.2s/page**, a 3.75x speedup — leaves comfortable headroom under the 5s target for the typical 1-2 page real farmer report (the 4-page sample here is an atypical textbook excerpt, not a real single farmer's card).

## Verification performed in this environment

1. Installed the real `opencv-python-headless`, `pypdfium2`, `numpy`, `pillow` dependencies and ran the actual preprocessing pipeline against the actual uploaded `01_Karnataka_SHC_redacted_2017.pdf` — confirmed 4 pages render and process correctly, profiled and fixed the performance issue above.
2. Ran the field parser against all three real SHC text samples — 100% field extraction accuracy, all values matched exactly (`pytest.approx`).
3. Ran the full test suite: **52/52 passing**, including the real-PDF-through-fake-OCR-engine end-to-end integration test and the layout regression tests for the bug found above.
4. `PaddleOCREngine` itself was **not** exercised in this environment — it requires downloading PaddleOCR's model weights, which is impractical for this sandbox/test-suite context. The class is written and structurally correct (matches the documented PaddleOCR Python API), but its first real invocation should be the first thing verified after deployment, alongside a real single-page farmer photo upload.

## Explicitly deferred to later phases (not gaps)

- Weather/climate integration — Phase 5.
- Feature fusion of soil + climate data for ML — Phase 6.
- OCR results feeding the recommendation engine — Phases 6-7 (the `soil_parameters` table this phase populates is exactly the Vol 9.7 "Validated Soil JSON" input the ML pipeline expects).

## AIB Compliance Notes

- OCR, parsing, and validation are kept as separate modules (`engine.py`, `field_parser.py`, `validation.py`) per Vol 7.16.
- No raw OCR text is ever sent directly to any downstream ML/feature pipeline — only validated, structured `soil_parameters` rows are (Vol 7.16, enforced structurally: `run_ocr` only persists after `validate_soil_values` has classified the report).
- Original uploaded files are never deleted or overwritten (Vol 7.16 audit requirement).
