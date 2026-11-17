"""Market outlook schemas (project Objective 3)."""

from pydantic import BaseModel


class MarketCropOut(BaseModel):
    crop: str
    has_current_price: bool
    seasonal_forecast_available: bool
    scope: str | None = None


class ForecastPointOut(BaseModel):
    month: str
    label: str
    expected_price: float
    change_pct: float


class MarketOutlookOut(BaseModel):
    crop: str
    unit: str
    current_price: float
    price_low: float
    price_high: float
    scope: str
    as_of: str
    n_records: int
    seasonal_forecast_available: bool
    forecast: list[ForecastPointOut]
    best_month: str | None
    expected_gain_pct: float | None
    trend: str
    action: str
    advice: str
    perishable: bool
    backtest_mape: float | None = None
    naive_mape: float | None = None
    sources: list[str]
    caveats: list[str]
