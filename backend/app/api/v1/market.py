"""Market routes - price outlook and best-time-to-sell advice (Objective 3)."""

from dataclasses import asdict

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.dependencies.auth import get_current_user
from app.market.forecaster import MarketForecaster, UnknownCropError, get_market_forecaster
from app.models.user import User
from app.schemas.common import success_response
from app.schemas.market import MarketCropOut, MarketOutlookOut

router = APIRouter(prefix="/market", tags=["Market Intelligence"])


@router.get("/crops")
def list_market_crops(
    current_user: User = Depends(get_current_user),
    forecaster: MarketForecaster = Depends(get_market_forecaster),
):
    data = [MarketCropOut(**c).model_dump() for c in forecaster.crops()]
    return success_response("Market coverage retrieved.", data)


@router.get("/{crop}/outlook")
def get_market_outlook(
    crop: str,
    months: int = Query(default=6, ge=1, le=12),
    current_user: User = Depends(get_current_user),
    forecaster: MarketForecaster = Depends(get_market_forecaster),
):
    try:
        o = forecaster.outlook(crop, months)
    except UnknownCropError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"No mandi price data available for '{crop}'.")
    d = asdict(o)
    low, high = d.pop("price_range")
    bt = d.pop("backtest") or {}
    out = MarketOutlookOut(**d, price_low=low, price_high=high,
                           backtest_mape=bt.get("mape_seasonal"), naive_mape=bt.get("mape_naive"))
    return success_response("Market outlook generated.", out.model_dump(mode="json"))
