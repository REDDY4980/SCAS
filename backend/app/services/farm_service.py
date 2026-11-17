"""
FarmService — business logic for farm CRUD and ownership enforcement.

AIB v1.0 Vol 6.10 — each farm belongs to exactly one user; recommendations
are generated only for owned farms.

Farmers never type latitude/longitude (a real product requirement, not
an AIB one) — coordinates arrive one of two ways: silently from the
device's GPS if the browser grants permission, or resolved automatically
here from the farm's district/state via Open-Meteo's geocoding API.
Explicit coordinates (when the client does supply them, e.g. from GPS)
always take precedence over auto-geocoding.
"""

import logging
import uuid

from fastapi import HTTPException, status

from app.models.farm import Farm
from app.models.user import User
from app.repositories.farm_repository import FarmRepository
from app.repositories.user_repository import UserRepository
from app.schemas.farm import FarmCreate, FarmOut, FarmUpdate
from app.weather.geocoding import GeocodingError, geocode_place

logger = logging.getLogger("scas.services.farm")


class FarmService:
    def __init__(self, repo: FarmRepository):
        self.repo = repo

    def _resolve_coordinates(self, *, district: str, state: str) -> tuple[float | None, float | None]:
        latitude, longitude, _ = self._geocode(district=district, state=state)
        return latitude, longitude

    def _geocode(self, *, district: str, state: str) -> tuple[float | None, float | None, str | None]:
        """
        Best-effort geocoding fallback — never raises. A farmer's ability
        to save a farm must not depend on a third-party geocoding service
        being up; a farm with no coordinates just falls back to the
        existing "no weather data yet" handling (WeatherService), which
        is the rare case, not a hard failure here.
        """
        try:
            location = geocode_place(district, state=state)
        except GeocodingError as exc:
            logger.warning("Geocoding failed for district=%r state=%r: %s", district, state, exc)
            return None, None, None
        if location is None:
            logger.info("Geocoding found no match for district=%r state=%r", district, state)
            return None, None, None
        if location.is_approximate:
            logger.info(
                "Geocoding fell back to state-level coordinates for district=%r state=%r", district, state
            )
        return location.latitude, location.longitude, ("state" if location.is_approximate else "district")

    def create_farm(self, user: User, payload: FarmCreate) -> FarmOut:
        fields = payload.model_dump()
        gps = fields.get("latitude") is not None and fields.get("longitude") is not None
        if gps:
            fields["location_source"] = "gps"
        else:
            fields["latitude"] = fields["longitude"] = fields["location_accuracy_m"] = None
            latitude, longitude, source = self._geocode(district=fields["district"], state=fields["state"])
            if latitude is not None and longitude is not None:
                fields.update(latitude=latitude, longitude=longitude, location_source=source)
        farm = self.repo.create(user_id=user.id, **fields)
        if gps:
            # The device position used for the farm is also the farmer's
            # current location, so keep the profile in step with it.
            UserRepository(self.repo.db).update_location(
                user, latitude=fields["latitude"], longitude=fields["longitude"],
                accuracy_m=fields.get("location_accuracy_m"), source="gps",
            )
        return FarmOut.model_validate(farm)

    def apply_device_location(self, user: User, farm_id: uuid.UUID, *, latitude: float,
                              longitude: float, accuracy_m: float | None) -> FarmOut:
        """Set a farm's coordinates from the device's GPS (farmer standing on the farm)."""
        farm = self._get_owned_farm_or_404(user, farm_id)
        updated = self.repo.update(farm, latitude=latitude, longitude=longitude,
                                   location_source="gps", location_accuracy_m=accuracy_m)
        return FarmOut.model_validate(updated)

    def list_farms(self, user: User) -> list[FarmOut]:
        farms = self.repo.list_for_user(user.id)
        return [FarmOut.model_validate(f) for f in farms]

    def _get_owned_farm_or_404(self, user: User, farm_id: uuid.UUID) -> Farm:
        farm = self.repo.get_by_id(farm_id)
        if farm is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Farm not found.")
        if farm.user_id != user.id:
            # AIB Vol 6.10: recommendations/farm access only for owned farms.
            # 404 (not 403) avoids confirming the farm's existence to a non-owner.
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Farm not found.")
        return farm

    def update_farm(self, user: User, farm_id: uuid.UUID, payload: FarmUpdate) -> FarmOut:
        farm = self._get_owned_farm_or_404(user, farm_id)
        fields = payload.model_dump()

        # Re-geocode when the farmer edits district/state without also
        # supplying explicit coordinates (e.g. fixing a farm's location
        # after weather failed) — this is how a farmer corrects bad/absent
        # coordinates without ever seeing the concept of coordinates.
        location_edited = fields.get("district") is not None or fields.get("state") is not None
        coords_given = fields.get("latitude") is not None and fields.get("longitude") is not None
        if coords_given:
            fields["location_source"] = "gps"
        elif location_edited and farm.location_source != "gps":
            # Never overwrite a GPS fix with a coarser geocoded point just
            # because the farmer corrected the spelling of the district.
            district = fields.get("district") or farm.district
            state = fields.get("state") or farm.state
            latitude, longitude, source = self._geocode(district=district, state=state)
            if latitude is not None and longitude is not None:
                fields.update(latitude=latitude, longitude=longitude, location_source=source)

        updated = self.repo.update(farm, **fields)
        return FarmOut.model_validate(updated)

    def delete_farm(self, user: User, farm_id: uuid.UUID) -> None:
        farm = self._get_owned_farm_or_404(user, farm_id)
        self.repo.delete(farm)

    def get_farm(self, user: User, farm_id: uuid.UUID) -> FarmOut:
        farm = self._get_owned_farm_or_404(user, farm_id)
        return FarmOut.model_validate(farm)
