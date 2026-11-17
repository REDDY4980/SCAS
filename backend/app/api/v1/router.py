"""API v1 router aggregation — AIB v1.0 Vol 14.2 versioning (/api/v1)."""

from fastapi import APIRouter

from app.api.v1 import auth, farms, fertilizer, history, market, recommendation, soil, users, weather

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(farms.router)
api_router.include_router(soil.router)
api_router.include_router(weather.router)
api_router.include_router(recommendation.router)
api_router.include_router(fertilizer.router)
api_router.include_router(history.router)
api_router.include_router(market.router)
