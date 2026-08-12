"""
Weather cache freshness check.

AIB v1.0 Vol 8.10: "Cache weather for 30 minutes. Reuse valid cache.
Refresh only after expiry or explicit user request."

The `weather_snapshots` table (Vol 5.3) itself IS the cache — the most
recent snapshot for a farm is reused if still fresh, rather than
maintaining a separate cache store. This keeps persistence and caching
as one source of truth instead of two systems that could drift.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.core.config import get_settings


def is_fresh(captured_at: datetime, ttl_seconds: int | None = None) -> bool:
    ttl = ttl_seconds if ttl_seconds is not None else get_settings().weather_cache_ttl_seconds
    if captured_at.tzinfo is None:
        captured_at = captured_at.replace(tzinfo=timezone.utc)
    age = datetime.now(timezone.utc) - captured_at
    return age <= timedelta(seconds=ttl)
