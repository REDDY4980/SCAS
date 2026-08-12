"""Weather schemas — AIB v1.0 Vol 14.2 (/weather/*), Vol 8.5 climate features."""

import uuid
from datetime import datetime

from pydantic import BaseModel


class WeatherSnapshotOut(BaseModel):
    id: uuid.UUID
    farm_id: uuid.UUID
    temperature: float | None
    humidity: float | None
    rainfall: float | None
    wind_speed: float | None
    # Season (Vol 8.5) is derived from captured_at rather than persisted —
    # weather_snapshots (Vol 5.3) has no season column, and deriving it
    # keeps a single source of truth instead of a value that could drift
    # out of sync with captured_at.
    season: str
    captured_at: datetime
    cache_hit: bool
    provider: str | None = None

    model_config = {"from_attributes": True}
