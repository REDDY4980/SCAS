"""Weather snapshot repository — pure CRUD, no business logic (AIB v1.0 Vol 12.6)."""

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.weather import WeatherSnapshot


class WeatherRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_latest_for_farm(self, farm_id: uuid.UUID) -> WeatherSnapshot | None:
        return self.db.execute(
            select(WeatherSnapshot)
            .where(WeatherSnapshot.farm_id == farm_id)
            .order_by(WeatherSnapshot.captured_at.desc())
            .limit(1)
        ).scalar_one_or_none()

    def list_history(self, farm_id: uuid.UUID, limit: int = 30) -> list[WeatherSnapshot]:
        return list(
            self.db.execute(
                select(WeatherSnapshot)
                .where(WeatherSnapshot.farm_id == farm_id)
                .order_by(WeatherSnapshot.captured_at.desc())
                .limit(limit)
            ).scalars()
        )

    def create_snapshot(
        self,
        *,
        farm_id: uuid.UUID,
        temperature: float | None,
        humidity: float | None,
        rainfall: float | None,
        wind_speed: float | None,
        captured_at,
    ) -> WeatherSnapshot:
        snapshot = WeatherSnapshot(
            farm_id=farm_id,
            temperature=temperature,
            humidity=humidity,
            rainfall=rainfall,
            wind_speed=wind_speed,
            captured_at=captured_at,
        )
        self.db.add(snapshot)
        self.db.commit()
        self.db.refresh(snapshot)
        return snapshot
