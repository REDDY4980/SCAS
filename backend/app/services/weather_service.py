"""
WeatherService — orchestrates the Vol 8.4 pipeline:

    Farm -> Coordinate Validation -> Weather API -> Normalize -> Cache
    -> Weather Snapshot -> Feature Fusion -> Recommendation Engine

Vol 8.11 Failure Handling:
    "Retry once on timeout. Use cache if provider unavailable. Request
    user correction for invalid coordinates."
"""

from __future__ import annotations

import logging
import uuid

from fastapi import HTTPException, status

from app.models.farm import Farm
from app.models.user import User
from app.models.weather import WeatherSnapshot
from app.repositories.farm_repository import FarmRepository
from app.repositories.weather_repository import WeatherRepository
from app.schemas.weather import WeatherSnapshotOut
from app.weather import normalizer
from app.weather.cache import is_fresh
from app.weather.client import (
    OpenMeteoClient,
    OpenWeatherMapClient,
    WeatherProviderClient,
    WeatherProviderError,
    fetch_with_retry,
)

logger = logging.getLogger("scas.services.weather")


def _season_for(captured_at) -> str:
    return normalizer.season_for_month(captured_at.month)


def _to_out(snapshot: WeatherSnapshot, *, cache_hit: bool, provider: str | None) -> WeatherSnapshotOut:
    return WeatherSnapshotOut(
        id=snapshot.id,
        farm_id=snapshot.farm_id,
        temperature=snapshot.temperature,
        humidity=snapshot.humidity,
        rainfall=snapshot.rainfall,
        wind_speed=snapshot.wind_speed,
        season=_season_for(snapshot.captured_at),
        captured_at=snapshot.captured_at,
        cache_hit=cache_hit,
        provider=provider,
    )


class WeatherService:
    def __init__(
        self,
        weather_repo: WeatherRepository,
        farm_repo: FarmRepository,
        primary_client: WeatherProviderClient | None = None,
        fallback_client: WeatherProviderClient | None = None,
    ):
        self.weather_repo = weather_repo
        self.farm_repo = farm_repo
        self.primary_client = primary_client or OpenMeteoClient()
        self.fallback_client = fallback_client or OpenWeatherMapClient()

    def _get_owned_farm_or_404(self, user: User, farm_id: uuid.UUID) -> Farm:
        farm = self.farm_repo.get_by_id(farm_id)
        if farm is None or farm.user_id != user.id:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Farm not found.")
        return farm

    def _ensure_coordinates(self, farm: Farm) -> None:
        """A farm saved while geocoding was briefly unavailable has no
        coordinates; resolve them now (once — they are saved on the farm)
        instead of refusing weather until the farmer edits the farm."""
        if farm.latitude is not None and farm.longitude is not None:
            return
        from app.services.farm_service import FarmService  # local: avoid import cycle

        latitude, longitude, source = FarmService(self.farm_repo)._geocode(
            district=farm.district, state=farm.state
        )
        if latitude is not None and longitude is not None:
            self.farm_repo.update(farm, latitude=latitude, longitude=longitude, location_source=source)
            logger.info("Farm %s had no coordinates; resolved from district/state (%s).", farm.id, source)

    def _validate_coordinates(self, farm: Farm) -> None:
        self._ensure_coordinates(farm)
        if farm.latitude is None or farm.longitude is None:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                "This farm has no GPS coordinates on file. Please update the farm's "
                "location before requesting weather data.",
            )

    def _fetch_and_normalize(self, latitude: float, longitude: float) -> normalizer.NormalizedWeather:
        """
        Vol 8.11: retry once on the primary, then fall back to the
        secondary provider before giving up.
        """
        try:
            raw = fetch_with_retry(self.primary_client, latitude, longitude)
            return normalizer.normalize(raw)
        except WeatherProviderError as primary_error:
            logger.warning("Primary weather provider failed: %s", primary_error)
            try:
                raw = fetch_with_retry(self.fallback_client, latitude, longitude)
                return normalizer.normalize(raw)
            except WeatherProviderError as fallback_error:
                logger.error(
                    "Both weather providers failed. primary=%s fallback=%s",
                    primary_error,
                    fallback_error,
                )
                raise

    def get_current(self, user: User, farm_id: uuid.UUID, force_refresh: bool = False) -> WeatherSnapshotOut:
        farm = self._get_owned_farm_or_404(user, farm_id)
        self._validate_coordinates(farm)

        latest = self.weather_repo.get_latest_for_farm(farm.id)
        if not force_refresh and latest is not None and is_fresh(latest.captured_at):
            return _to_out(latest, cache_hit=True, provider=None)

        try:
            normalized = self._fetch_and_normalize(float(farm.latitude), float(farm.longitude))
        except WeatherProviderError:
            if latest is not None:
                # Vol 8.11: "Use cache if provider unavailable" — even a
                # stale cache beats a hard failure for the farmer.
                logger.warning(
                    "Weather providers unavailable for farm %s; serving stale cache from %s.",
                    farm.id,
                    latest.captured_at,
                )
                return _to_out(latest, cache_hit=True, provider=None)
            raise HTTPException(
                status.HTTP_503_SERVICE_UNAVAILABLE,
                "Weather data is temporarily unavailable and no cached data exists "
                "for this farm. Please try again shortly.",
            )

        snapshot = self.weather_repo.create_snapshot(
            farm_id=farm.id,
            temperature=normalized.temperature,
            humidity=normalized.humidity,
            rainfall=normalized.rainfall,
            wind_speed=normalized.wind_speed,
            captured_at=normalized.captured_at,
        )
        return _to_out(snapshot, cache_hit=False, provider=normalized.provider)

    def refresh(self, user: User, farm_id: uuid.UUID) -> WeatherSnapshotOut:
        """Vol 8.7: POST /weather/refresh — always bypasses the cache."""
        return self.get_current(user, farm_id, force_refresh=True)

    def get_history(self, user: User, farm_id: uuid.UUID, limit: int = 30) -> list[WeatherSnapshotOut]:
        self._get_owned_farm_or_404(user, farm_id)
        snapshots = self.weather_repo.list_history(farm_id, limit=limit)
        return [_to_out(s, cache_hit=True, provider=None) for s in snapshots]
