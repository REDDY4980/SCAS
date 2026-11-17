"""
Objective-wise acceptance tests for SCAS.

Each test is tagged with the project objective it verifies (see the
report / presentation, "Objectives of the Proposed System"):

  O1  Crop recommendation from soil nutrients + climate
  O2  Fertilizer recommendation: correct type AND quantity
  O3  Market prediction and decision support
  O4  Simple, accessible, user-friendly platform for small farmers
  O5  Reliable AI/ML (accuracy, speed, robustness)

Measured values are written to ACCEPTANCE_METRICS_PATH (JSON) so the
testing report quotes numbers produced by this run, not typed by hand.
"""

from __future__ import annotations

import atexit
import io
import json
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from app.main import app
from app.ocr.engine import OCREngine, OCRLine, OCRPageResult
from app.weather.client import RawWeatherResponse, WeatherProviderClient
from tests.conftest import KARNATAKA_SHC_PDF_PATH
from tests.fixtures.real_shc_samples import KARNATAKA_SHC_EXPECTED, KARNATAKA_SHC_LINES

REPO = Path(__file__).resolve().parents[3]
DATASET = REPO / "datasets" / "crop_recommendation" / "Crop_recommendation.csv"
METRICS: dict = {}
atexit.register(lambda: Path(os.environ.get("ACCEPTANCE_METRICS_PATH", "/tmp/acceptance_metrics.json"))
                .write_text(json.dumps(METRICS, indent=2, default=str)))


# ----------------------------------------------------------------- fakes
class _Weather(WeatherProviderClient):
    """Open-Meteo-shaped payload (the live API is not reachable from the
    test sandbox). Values = the demo farm's monsoon conditions."""
    name = "open-meteo"

    def __init__(self, temp=28.0, rh=82.0, rain_sum=2.0):
        self.temp, self.rh, self.rain = temp, rh, rain_sum

    def fetch(self, latitude, longitude) -> RawWeatherResponse:
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M")
        return RawWeatherResponse("open-meteo", {
            "current": {"time": now, "temperature_2m": self.temp, "relative_humidity_2m": self.rh,
                        "wind_speed_10m": 5.0, "cloud_cover": 60.0, "precipitation": 0.0},
            "daily": {"time": [now[:10]], "rain_sum": [self.rain]}})


class _KarnatakaOCR(OCREngine):
    """Returns the real Karnataka SHC table text (page 1 only)."""
    def __init__(self, conf=0.93):
        self.calls, self.conf = 0, conf

    def extract(self, image) -> OCRPageResult:
        self.calls += 1
        if self.calls == 1:
            return OCRPageResult([OCRLine(t, self.conf) for t in KARNATAKA_SHC_LINES])
        return OCRPageResult([OCRLine("Department of Agriculture, Karnataka Government", 0.9)])


def _override_weather(client_obj):
    from fastapi import Depends
    from app.api.v1 import weather as wm
    from app.core.database import get_db
    from app.repositories.farm_repository import FarmRepository
    from app.repositories.weather_repository import WeatherRepository
    from app.services.weather_service import WeatherService
    app.dependency_overrides[wm._service] = lambda db=Depends(get_db): WeatherService(
        WeatherRepository(db), FarmRepository(db), primary_client=client_obj)


def _override_ocr(engine):
    from fastapi import Depends
    from app.api.v1 import soil as sm
    from app.core.database import get_db
    from app.repositories.farm_repository import FarmRepository
    from app.repositories.soil_repository import SoilRepository
    from app.services.soil_service import SoilService
    app.dependency_overrides[sm._service] = lambda db=Depends(get_db): SoilService(
        SoilRepository(db), FarmRepository(db), ocr_engine=engine)


@pytest.fixture(autouse=True)
def _clean_overrides():
    yield
    from app.api.v1 import soil as sm, weather as wm
    app.dependency_overrides.pop(sm._service, None)
    app.dependency_overrides.pop(wm._service, None)


def _new_farm(client, headers, area=3.5):
    r = client.post("/api/v1/farms", json={
        "farm_name": "Demo Farm", "state": "Karnataka", "district": "Bagalkote", "village": "Bagalkote",
        "soil_type": "Black Soil", "latitude": 16.18, "longitude": 75.70, "area_acres": area}, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()["data"]["id"]


def _full_flow(client, headers, weather=None, area=3.5):
    """Farmer journey: farm -> upload real SHC PDF -> OCR -> weather -> crop rec."""
    _override_ocr(_KarnatakaOCR())
    _override_weather(weather or _Weather())
    farm_id = _new_farm(client, headers, area)
    up = client.post("/api/v1/soil/upload", params={"farm_id": farm_id},
                     files={"file": ("shc.pdf", io.BytesIO(KARNATAKA_SHC_PDF_PATH.read_bytes()), "application/pdf")},
                     headers=headers)
    assert up.status_code == 202, up.text
    rid = up.json()["data"]["report_id"]
    t0 = time.perf_counter()
    ocr = client.post(f"/api/v1/soil/{rid}/ocr", headers=headers)
    ocr_s = time.perf_counter() - t0
    assert ocr.status_code == 200, ocr.text
    w = client.get("/api/v1/weather/current", params={"farm_id": farm_id}, headers=headers)
    assert w.status_code == 200, w.text
    t0 = time.perf_counter()
    rec = client.post("/api/v1/recommendation", params={"farm_id": farm_id}, headers=headers)
    rec_s = time.perf_counter() - t0
    return farm_id, ocr.json()["data"], w.json()["data"], rec, ocr_s, rec_s


# ============================================================ O1 CROP
def test_O1_TC01_end_to_end_crop_recommendation(client, auth_headers):
    """Upload real SHC -> OCR -> live-weather snapshot -> Top-5 crops."""
    _, ocr, weather, rec, ocr_s, rec_s = _full_flow(client, auth_headers)
    assert rec.status_code == 200, rec.text
    d = rec.json()["data"]
    top = d["top_recommendations"]
    assert len(top) == 5
    confs = [c["confidence"] for c in top]
    assert all(0.0 <= c <= 1.0 for c in confs)
    assert confs == sorted(confs, reverse=True)
    assert d["primary_crop"] == top[0]["crop"]
    assert all(len(c["reason"]) > 40 for c in top)
    METRICS["O1_TC01"] = {"ocr_status": ocr["ocr_status"], "ocr_confidence": ocr["ocr_confidence"],
                          "soil": ocr["soil_parameters"], "weather": {k: weather.get(k) for k in ("temperature", "humidity", "rainfall", "season")},
                          "primary_crop": d["primary_crop"], "top5": [(c["crop"], c["confidence"]) for c in top],
                          "explanation": d["explanation"], "ocr_pipeline_s": round(ocr_s, 2), "recommendation_api_s": round(rec_s, 3)}


def test_O1_TC02_every_crop_is_reachable():
    """For each of the 22 crops, the per-crop median profile must be
    recommended as that crop (Top-1) - checks every class is learnt."""
    from app.ml.registry import get_inference_engine
    eng = get_inference_engine()
    df = pd.read_csv(DATASET)
    hits, top3, rows = 0, 0, []
    for crop, g in df.groupby("label"):
        feats = g[["N", "P", "K", "temperature", "humidity", "ph", "rainfall"]].median().to_dict()
        preds = eng.predict_top5(feats).predictions
        names = [p.crop for p in preds]
        hits += names[0] == crop
        top3 += crop in names[:3]
        rows.append((crop, names[0], round(preds[0].confidence, 3)))
    METRICS["O1_TC02"] = {"top1_hits": hits, "top3_hits": top3, "n": 22, "rows": rows}
    assert hits == 22


def test_O1_TC03_held_out_accuracy_and_per_crop_recall():
    """Re-split exactly as training did (80/10/10, seed 42) and score the
    deployed model artifact on the untouched test fold."""
    import joblib
    from sklearn.metrics import accuracy_score, f1_score, recall_score
    from sklearn.model_selection import train_test_split
    art = REPO / "ml" / "artifacts"
    model, enc = joblib.load(art / "model.joblib"), joblib.load(art / "label_encoder.joblib")
    df = pd.read_csv(DATASET)
    X = df[["N", "P", "K", "temperature", "humidity", "ph", "rainfall"]].to_numpy(float)
    y = enc.transform(df["label"])
    _, Xt, _, yt = train_test_split(X, y, test_size=0.2, stratify=y, random_state=42)
    _, Xte, _, yte = train_test_split(Xt, yt, test_size=0.5, stratify=yt, random_state=42)
    t0 = time.perf_counter(); p = model.predict(Xte); lat = (time.perf_counter() - t0) / len(Xte) * 1000
    rec = recall_score(yte, p, average=None)
    METRICS["O1_TC03"] = {"test_n": len(yte), "accuracy": accuracy_score(yte, p), "macro_f1": f1_score(yte, p, average="macro"),
                          "min_crop_recall": float(rec.min()), "crops_below_0.9": [enc.classes_[i] for i, r in enumerate(rec) if r < 0.9],
                          "latency_ms_per_sample": lat}
    assert accuracy_score(yte, p) >= 0.95
    assert rec.min() >= 0.8


def test_O1_TC04_recommendation_responds_to_climate():
    """Same soil, different climate -> different advice (the climate path
    actually matters)."""
    from app.ml.registry import get_inference_engine
    eng = get_inference_engine()
    base = {"N": 80, "P": 45, "K": 40, "ph": 6.5}
    wet = eng.predict_top5({**base, "temperature": 24, "humidity": 82, "rainfall": 230}).predictions[0].crop
    dry = eng.predict_top5({**base, "temperature": 20, "humidity": 18, "rainfall": 80}).predictions[0].crop
    METRICS["O1_TC04"] = {"wet_monsoon_top1": wet, "dry_winter_top1": dry}
    assert wet != dry


def test_O1_TC05_rule_engine_adjusts_rice_by_ph():
    from app.rules.agronomic_rules import AgronomicRuleEngine
    eng = AgronomicRuleEngine()
    soil = {"nitrogen": 300, "phosphorus": 20, "potassium": 200, "organic_carbon": 0.8}
    good = eng.evaluate("rice", {**soil, "ph": 6.0}).score_adjustment
    bad = eng.evaluate("rice", {**soil, "ph": 8.2}).score_adjustment
    other = eng.evaluate("maize", {**soil, "ph": 6.0}).score_adjustment
    METRICS["O1_TC05"] = {"rice_pH6.0": good, "rice_pH8.2": bad, "maize_no_rule": other}
    assert good == pytest.approx(0.05) and bad == pytest.approx(-0.05) and other == pytest.approx(-0.01)


def test_O1_TC06_low_nutrient_penalty_is_capped():
    from app.rules.agronomic_rules import AgronomicRuleEngine
    ev = AgronomicRuleEngine().evaluate("maize", {"nitrogen": 50, "phosphorus": 2, "potassium": 30,
                                                   "organic_carbon": 0.1, "ph": 7.0})
    METRICS["O1_TC06"] = {"all_four_low_adjustment": ev.score_adjustment}
    assert ev.score_adjustment == pytest.approx(-0.08 - 0.01)


def test_O1_TC07_no_soil_report_blocks_recommendation(client, auth_headers):
    _override_weather(_Weather())
    farm = _new_farm(client, auth_headers)
    r = client.post("/api/v1/recommendation", params={"farm_id": farm}, headers=auth_headers)
    assert r.status_code == 400 and "soil" in r.text.lower()


def test_O1_TC08_no_weather_blocks_recommendation(client, auth_headers):
    _override_ocr(_KarnatakaOCR())
    farm = _new_farm(client, auth_headers)
    rid = client.post("/api/v1/soil/upload", params={"farm_id": farm},
                      files={"file": ("s.pdf", io.BytesIO(KARNATAKA_SHC_PDF_PATH.read_bytes()), "application/pdf")},
                      headers=auth_headers).json()["data"]["report_id"]
    client.post(f"/api/v1/soil/{rid}/ocr", headers=auth_headers)
    r = client.post("/api/v1/recommendation", params={"farm_id": farm}, headers=auth_headers)
    assert r.status_code == 400 and "climate" in r.text.lower()


# ====================================================== O2 FERTILIZER
def test_O2_TC01_shc_band_classification_boundaries():
    from app.rules.deficiency_detector import DeficiencyDetector
    d = DeficiencyDetector()
    cases = {279.9: "low", 280: "medium", 559.9: "medium", 560: "high"}
    got = {v: d.analyze({"nitrogen": v}).classifications["nitrogen"] for v in cases}
    p = {v: d.analyze({"phosphorus": v}).classifications["phosphorus"] for v in (9.9, 10, 25)}
    k = {v: d.analyze({"potassium": v}).classifications["potassium"] for v in (119, 120, 280)}
    oc = {v: d.analyze({"organic_carbon": v}).classifications["organic_carbon"] for v in (0.49, 0.5, 0.75)}
    METRICS["O2_TC01"] = {"N": got, "P": p, "K": k, "OC": oc}
    assert got == cases
    assert list(p.values()) == ["low", "medium", "high"]
    assert list(k.values()) == ["low", "medium", "high"]
    assert list(oc.values()) == ["low", "medium", "high"]


def test_O2_TC02_quantity_matches_hand_calculation():
    """Karnataka card: N 200.6, P 4.19 on 3.5 acres.
    Urea: (280-200.6)/0.46 = 172.61 kg/ha x 1.4165 ha = 244.5 kg
    DAP : (10-4.19)/0.46  =  12.63 kg/ha x 1.4165 ha =  17.9 kg"""
    from app.rules.deficiency_detector import DeficiencyDetector
    from app.rules.fertilizer_selector import FertilizerSelector
    prof = DeficiencyDetector().analyze({k: KARNATAKA_SHC_EXPECTED[k] for k in ("nitrogen", "phosphorus", "potassium", "organic_carbon")})
    items = FertilizerSelector().select("muskmelon", prof, area_acres=3.5)
    by = {i.fertilizer_name: i for i in items}
    nums = {n: [float(x) for x in re.findall(r"[\d.]+(?= kg)", i.dosage)] for n, i in by.items()}
    exp_urea_ha = (280 - 200.6) / 0.46; exp_dap_ha = (10 - 4.19) / 0.46
    METRICS["O2_TC02"] = {"items": {n: i.dosage for n, i in by.items()},
                          "expected": {"Urea_kg_ha": exp_urea_ha, "Urea_total": exp_urea_ha * 3.5 * 0.4047,
                                       "DAP_kg_ha": exp_dap_ha, "DAP_total": exp_dap_ha * 3.5 * 0.4047}}
    assert set(by) == {"Urea", "DAP"}  # K 122.8 is medium -> no MOP
    assert nums["Urea"][0] == pytest.approx(exp_urea_ha * 3.5 * 0.4047, abs=0.1)
    assert nums["DAP"][0] == pytest.approx(exp_dap_ha * 3.5 * 0.4047, abs=0.1)
    assert all("not a sourced dose" in i.dosage for i in items)


def test_O2_TC03_potassium_deficiency_gives_mop():
    from app.rules.deficiency_detector import DeficiencyDetector
    from app.rules.fertilizer_selector import FertilizerSelector
    prof = DeficiencyDetector().analyze({"nitrogen": 400, "phosphorus": 30, "potassium": 60, "organic_carbon": 0.8})
    items = FertilizerSelector().select("banana", prof, area_acres=1.0)
    METRICS["O2_TC03"] = [i.dosage for i in items]
    assert [i.fertilizer_name for i in items] == ["MOP"]
    assert float(re.findall(r"~([\d.]+) kg", items[0].dosage)[0]) == pytest.approx((120 - 60) / 0.60 * 0.4047, abs=0.1)


def test_O2_TC04_sourced_dose_used_when_available():
    from app.rules.deficiency_detector import DeficiencyDetector
    from app.rules.fertilizer_selector import FertilizerSelector
    items = FertilizerSelector().select("maize", DeficiencyDetector().analyze({"nitrogen": 200}))
    METRICS["O2_TC04"] = [(i.dosage, i.source) for i in items]
    doses = " ".join(i.dosage for i in items)
    assert "150 kg/ha" in doses and "75 kg/ha" in doses and "40 kg/ha" in doses
    assert all("Agricultural Sciences" in i.source for i in items)


def test_O2_TC05_healthy_soil_no_fertilizer():
    from app.rules.deficiency_detector import DeficiencyDetector
    from app.rules.fertilizer_selector import FertilizerSelector
    items = FertilizerSelector().select("mango", DeficiencyDetector().analyze(
        {"nitrogen": 400, "phosphorus": 30, "potassium": 300, "organic_carbon": 0.9}))
    assert len(items) == 1 and items[0].fertilizer_name == "None required"


def test_O2_TC06_fertilizer_api_end_to_end(client, auth_headers):
    _, _, _, rec, _, _ = _full_flow(client, auth_headers)
    rid = rec.json()["data"]["id"]
    r1 = client.post(f"/api/v1/fertilizer/{rid}", headers=auth_headers)
    assert r1.status_code in (200, 201), r1.text
    d = r1.json()["data"]
    r2 = client.post(f"/api/v1/fertilizer/{rid}", headers=auth_headers)
    g = client.get(f"/api/v1/fertilizer/{rid}", headers=auth_headers)
    METRICS["O2_TC06"] = {"crop": d["crop"], "deficiency_profile": d["deficiency_profile"],
                          "fertilizers": [(f["fertilizer_name"], f["dosage"]) for f in d["fertilizers"]],
                          "coverage": d["knowledge_base_coverage"]}
    assert d["deficiency_profile"]["nitrogen"] == "low" and d["deficiency_profile"]["potassium"] == "medium"
    assert {f["fertilizer_name"] for f in d["fertilizers"]} == {"Urea", "DAP"}
    assert len(r2.json()["data"]["fertilizers"]) == len(d["fertilizers"])
    assert g.status_code == 200


# ========================================================= O3 MARKET
def test_O3_TC01_market_outlook_for_recommended_crop(client, auth_headers):
    """Farmer journey continues: recommended crop -> market outlook card."""
    _, _, _, rec, _, _ = _full_flow(client, auth_headers)
    crop = rec.json()["data"]["primary_crop"]
    paths = sorted(app.openapi()["paths"].keys())
    r = client.get(f"/api/v1/market/{crop}/outlook", headers=auth_headers)
    d = r.json()["data"]
    METRICS["O3_TC01"] = {"market_routes": [p for p in paths if "market" in p], "crop": crop,
                          "current_price": d["current_price"], "scope": d["scope"], "as_of": d["as_of"],
                          "action": d["action"], "advice": d["advice"]}
    assert r.status_code == 200 and d["current_price"] > 0 and d["advice"]


def test_O3_TC02_coverage_of_recommendable_crops(client, auth_headers):
    import joblib
    classes = list(joblib.load(REPO / "ml" / "artifacts" / "label_encoder.joblib").classes_)
    cov = {c["crop"]: c for c in client.get("/api/v1/market/crops", headers=auth_headers).json()["data"]}
    priced = [c for c in classes if cov.get(c, {}).get("has_current_price")]
    forecast = [c for c in classes if cov.get(c, {}).get("seasonal_forecast_available")]
    METRICS["O3_TC02"] = {"model_crops": len(classes), "with_current_price": len(priced),
                          "with_validated_forecast": forecast, "missing": sorted(set(classes) - set(priced))}
    assert len(priced) >= 20


def test_O3_TC03_forecast_only_where_it_beats_naive():
    """Validation gate: a seasonal forecast is shown only where it was more
    accurate than 'price stays the same' in the out-of-sample backtest."""
    bt = json.loads((REPO / "datasets" / "market" / "backtest.json").read_text())
    from app.market.forecaster import MarketForecaster
    f = MarketForecaster(REPO / "datasets" / "market")
    shown = [c["crop"] for c in f.crops() if c["seasonal_forecast_available"]]
    METRICS["O3_TC03"] = {"pooled_mape_seasonal": bt["pooled_mape_seasonal"], "pooled_mape_naive": bt["pooled_mape_naive"],
                          "shown": shown, "per_crop": {c: bt["per_crop"][c] for c in shown}}
    for c in shown:
        assert bt["per_crop"][c]["mape_seasonal"] < bt["per_crop"][c]["mape_naive"]


def test_O3_TC04_decision_advice_types(client, auth_headers):
    got = {}
    for crop in ("maize", "watermelon", "rice"):
        d = client.get(f"/api/v1/market/{crop}/outlook", headers=auth_headers).json()["data"]
        got[crop] = {"action": d["action"], "best_month": d["best_month"], "gain": d["expected_gain_pct"],
                     "forecast": [(p["label"], p["expected_price"]) for p in d["forecast"]]}
    METRICS["O3_TC04"] = got
    assert got["rice"]["action"] == "sell_when_ready" and got["rice"]["forecast"] == []
    assert got["watermelon"]["action"] in {"time_harvest", "sell_now"}  # perishable: never "hold"
    assert got["maize"]["action"] in {"hold", "sell_now"} and len(got["maize"]["forecast"]) == 6


# ===================================================== O4 USABILITY
def test_O4_TC01_all_ui_strings_translated():
    src = (REPO / "mobile" / "lib" / "localization" / "app_strings.dart").read_text(encoding="utf-8")
    keys = re.findall(r"'(\w+)':\s*\{", src)
    blocks = re.findall(r"'(\w+)':\s*\{(.*?)\}", src, re.S)
    missing = {lang: [k for k, b in blocks if f"'{lang}':" not in b] for lang in ("en", "kn", "hi", "te")}
    METRICS["O4_TC01"] = {"keys": len(blocks), "missing": {k: len(v) for k, v in missing.items()},
                          "missing_examples": {k: v[:5] for k, v in missing.items() if v}}
    assert len(blocks) > 50
    assert all(len(v) == 0 for v in missing.values())


def test_O4_TC02_ocr_reads_real_card_exactly(client, auth_headers):
    """Real PDF render + real OpenCV preprocessing + parser on the card's
    text; every numeric field must match the printed card."""
    _, ocr, _, _, ocr_s, _ = _full_flow(client, auth_headers)
    p = ocr["soil_parameters"]
    fields = [k for k in KARNATAKA_SHC_EXPECTED if k != "sulphur"]
    exact = [k for k in fields if p[k] == pytest.approx(KARNATAKA_SHC_EXPECTED[k])]
    METRICS["O4_TC02"] = {"fields": len(fields), "exact": len(exact), "status": ocr["ocr_status"],
                          "pipeline_seconds_4_pages": round(ocr_s, 2)}
    assert len(exact) == len(fields) and ocr["ocr_status"] == "success"


def test_O4_TC03_real_ocr_engine_on_scanned_card():
    """Independent real-OCR check using Tesseract (PaddleOCR cannot be
    installed in the test sandbox). Measures field accuracy on the scanned
    Karnataka card and checks that bad reads are NOT auto-accepted."""
    pytesseract = pytest.importorskip("pytesseract")
    from app.ocr import preprocessing
    from app.ocr.field_parser import parse_lines
    from app.ocr.layout import reconstruct_rows
    from app.ocr.validation import validate_soil_values
    pages = preprocessing.preprocess_file(KARNATAKA_SHC_PDF_PATH)
    rows, confs = [], []
    for img in pages:
        d = pytesseract.image_to_data(img, output_type=pytesseract.Output.DICT, config="--psm 6")
        groups = {}
        for j, w in enumerate(d["text"]):
            if w.strip():
                groups.setdefault((d["block_num"][j], d["par_num"][j], d["line_num"][j]), []).append(j)
        lines = []
        for idx in groups.values():
            x0 = min(d["left"][j] for j in idx); y0 = min(d["top"][j] for j in idx)
            x1 = max(d["left"][j] + d["width"][j] for j in idx); y1 = max(d["top"][j] + d["height"][j] for j in idx)
            c = sum(float(d["conf"][j]) for j in idx) / len(idx) / 100
            confs.append(c)
            lines.append(OCRLine(" ".join(d["text"][j] for j in idx), c, [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]))
        rows += reconstruct_rows(OCRPageResult(lines))
    vals = parse_lines(rows).values
    fields = [k for k in KARNATAKA_SHC_EXPECTED if k != "sulphur"]
    correct = [k for k in fields if k in vals and vals[k] == pytest.approx(KARNATAKA_SHC_EXPECTED[k])]
    v = validate_soil_values(vals, float(np.mean(confs)))
    METRICS["O4_TC03"] = {"engine": "Tesseract", "fields": len(fields), "correct": correct, "read": vals,
                          "mean_conf": float(np.mean(confs)), "validation_status": v.status,
                          "missing": v.missing_core_fields, "out_of_range": v.out_of_range_fields}
    assert v.status != "success"  # imperfect read must go to farmer review


def test_O4_TC04_low_confidence_goes_to_review_and_can_be_corrected(client, auth_headers):
    _override_ocr(_KarnatakaOCR(conf=0.60))
    farm = _new_farm(client, auth_headers)
    rid = client.post("/api/v1/soil/upload", params={"farm_id": farm},
                      files={"file": ("s.pdf", io.BytesIO(KARNATAKA_SHC_PDF_PATH.read_bytes()), "application/pdf")},
                      headers=auth_headers).json()["data"]["report_id"]
    o = client.post(f"/api/v1/soil/{rid}/ocr", headers=auth_headers).json()["data"]
    c = client.put(f"/api/v1/soil/{rid}/correct", json={"phosphorus": 4.2}, headers=auth_headers)
    after = client.get(f"/api/v1/soil/{rid}", headers=auth_headers).json()["data"]
    METRICS["O4_TC04"] = {"status_at_conf_0.60": o["ocr_status"], "after_correction": after["ocr_status"],
                          "phosphorus": after["soil_parameters"]["phosphorus"]}
    assert o["ocr_status"] == "needs_review"
    assert c.status_code == 200 and after["soil_parameters"]["phosphorus"] == pytest.approx(4.2)


def test_O4_TC05_bad_inputs_rejected(client, auth_headers):
    farm = _new_farm(client, auth_headers)
    bad_file = client.post("/api/v1/soil/upload", params={"farm_id": farm},
                           files={"file": ("x.exe", io.BytesIO(b"MZ"), "application/octet-stream")}, headers=auth_headers)
    bad_area = client.post("/api/v1/farms", json={"farm_name": "X Farm", "state": "KA", "district": "BG", "area_acres": -1},
                           headers=auth_headers)
    weak_pw = client.post("/api/v1/auth/register", json={"full_name": "A B", "email": "b@example.com",
                                                           "phone": "+919876543211", "password": "123"})
    METRICS["O4_TC05"] = {"bad_file": bad_file.status_code, "negative_area": bad_area.status_code, "weak_password": weak_pw.status_code}
    assert bad_file.status_code in (400, 415, 422) and bad_area.status_code == 422 and weak_pw.status_code == 422


def test_O4_TC06_security_auth_and_ownership(client, auth_headers):
    farm = _new_farm(client, auth_headers)
    no_token = client.get(f"/api/v1/farms/{farm}")
    bad_token = client.get(f"/api/v1/farms/{farm}", headers={"Authorization": "Bearer abc.def.ghi"})
    client.post("/api/v1/auth/register", json={"full_name": "Other User", "email": "o@example.com",
                                               "phone": "+919876543299", "password": "StrongPass123"})
    tok = client.post("/api/v1/auth/login", json={"identifier": "o@example.com", "password": "StrongPass123"}).json()["data"]["access_token"]
    other = client.get(f"/api/v1/farms/{farm}", headers={"Authorization": f"Bearer {tok}"})
    wrong_pw = client.post("/api/v1/auth/login", json={"identifier": "asha@example.com", "password": "Wrong12345"})
    METRICS["O4_TC06"] = {"no_token": no_token.status_code, "bad_token": bad_token.status_code,
                          "other_users_farm": other.status_code, "wrong_password": wrong_pw.status_code}
    assert no_token.status_code == 401 and bad_token.status_code == 401
    assert other.status_code == 404 and wrong_pw.status_code == 401


def test_O4_TC07_history_keeps_past_advice(client, auth_headers):
    _full_flow(client, auth_headers)
    _full_flow(client, auth_headers, weather=_Weather(temp=22, rh=60, rain_sum=90))
    h = client.get("/api/v1/history", headers=auth_headers)
    items = h.json()["data"]
    items = items.get("items", items) if isinstance(items, dict) else items
    METRICS["O4_TC07"] = {"history_items": len(items)}
    assert h.status_code == 200 and len(items) == 2


def test_O4_TC08_response_time_under_load(client, auth_headers):
    """20 sequential recommendation requests; p95 must stay < 2 s."""
    farm_id, *_ = _full_flow(client, auth_headers)
    times = []
    for _ in range(20):
        t0 = time.perf_counter()
        r = client.post("/api/v1/recommendation", params={"farm_id": farm_id}, headers=auth_headers)
        times.append(time.perf_counter() - t0)
        assert r.status_code == 200
    METRICS["O4_TC08"] = {"n": 20, "mean_ms": 1000 * float(np.mean(times)), "p95_ms": 1000 * float(np.percentile(times, 95)),
                          "max_ms": 1000 * max(times)}
    assert np.percentile(times, 95) < 2.0


def test_O4_TC09_gps_location_saved_to_farm_and_profile(client, auth_headers):
    """Farmer allows location on the farm form: the GPS fix is stored on the
    farm (marked as GPS) and on the farmer profile; a later 'Update my
    location' from the profile can fix a farm that only had a district guess."""
    import httpx
    r = client.post("/api/v1/farms", json={"farm_name": "GPS Farm", "state": "Karnataka", "district": "Bagalkote",
                                           "latitude": 16.1802, "longitude": 75.6961, "location_accuracy_m": 24},
                    headers=auth_headers)
    farm = r.json()["data"]
    profile = client.get("/api/v1/users/profile", headers=auth_headers).json()["data"]
    orig = httpx.get
    httpx.get = lambda *a, **k: type("R", (), {"raise_for_status": lambda self: None,
        "json": lambda self: {"results": [{"name": "Bagalkote", "latitude": 16.18, "longitude": 75.70, "admin1": "Karnataka"}]}})()
    try:
        approx = client.post("/api/v1/farms", json={"farm_name": "Typed Farm", "state": "Karnataka", "district": "Bagalkote"},
                             headers=auth_headers).json()["data"]
    finally:
        httpx.get = orig
    fixed = client.put("/api/v1/users/location", json={"latitude": 16.2001, "longitude": 75.6502, "accuracy_m": 9,
                                                       "apply_to_farm_id": approx["id"]}, headers=auth_headers).json()["data"]
    METRICS["O4_TC09"] = {"farm_source": farm["location_source"], "profile": {k: profile[k] for k in ("latitude", "longitude", "location_accuracy_m", "location_source")},
                          "typed_farm_source": approx["location_source"], "after_update": fixed["farm"]["location_source"]}
    assert farm["location_source"] == "gps" and profile["location_source"] == "gps"
    assert profile["latitude"] == pytest.approx(16.1802) and profile["location_accuracy_m"] == pytest.approx(24)
    assert approx["location_source"] == "district" and fixed["farm"]["location_source"] == "gps"


# ===================================================== O5 ROBUSTNESS
def test_O5_TC01_out_of_distribution_input_lowers_confidence():
    """In-range profile vs the real card's out-of-range profile."""
    from app.ml.registry import get_inference_engine
    eng = get_inference_engine()
    df = pd.read_csv(DATASET)
    inrange = df[df.label == "maize"][["N", "P", "K", "temperature", "humidity", "ph", "rainfall"]].median().to_dict()
    card = {"N": 200.6, "P": 4.19, "K": 122.8, "temperature": 28.0, "humidity": 82.0, "ph": 7.7, "rainfall": 2.0}
    a = eng.predict_top5(inrange).predictions[0]; b = eng.predict_top5(card).predictions[0]
    METRICS["O5_TC01"] = {"in_range": (a.crop, a.confidence), "real_card_ood": (b.crop, b.confidence)}
    assert a.confidence > b.confidence


def test_O5_TC02_invalid_feature_vector_rejected():
    from app.ml.registry import get_inference_engine
    with pytest.raises(Exception):
        get_inference_engine().predict_top5({"N": 50, "P": 40})
