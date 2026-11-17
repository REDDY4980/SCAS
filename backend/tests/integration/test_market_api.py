"""Integration tests for /market (Objective 3)."""


def test_market_requires_auth(client):
    assert client.get("/api/v1/market/crops").status_code == 401


def test_market_crops_lists_coverage(client, auth_headers):
    r = client.get("/api/v1/market/crops", headers=auth_headers)
    assert r.status_code == 200
    crops = {c["crop"]: c for c in r.json()["data"]}
    assert crops["maize"]["has_current_price"] and crops["maize"]["seasonal_forecast_available"]


def test_outlook_with_forecast(client, auth_headers):
    r = client.get("/api/v1/market/maize/outlook", params={"months": 6}, headers=auth_headers)
    assert r.status_code == 200, r.text
    d = r.json()["data"]
    assert d["unit"] == "INR per quintal" and d["current_price"] > 0
    assert len(d["forecast"]) == 6 and d["action"] in {"hold", "sell_now", "time_harvest"}
    assert d["backtest_mape"] < d["naive_mape"]
    assert d["sources"] and d["advice"]


def test_outlook_without_forecast_is_honest(client, auth_headers):
    d = client.get("/api/v1/market/rice/outlook", headers=auth_headers).json()["data"]
    assert d["forecast"] == [] and d["action"] == "sell_when_ready" and d["price_low"] <= d["current_price"] <= d["price_high"]


def test_outlook_unknown_crop_404(client, auth_headers):
    assert client.get("/api/v1/market/mothbeans/outlook", headers=auth_headers).status_code == 404


def test_outlook_months_validated(client, auth_headers):
    assert client.get("/api/v1/market/maize/outlook", params={"months": 24}, headers=auth_headers).status_code == 422
