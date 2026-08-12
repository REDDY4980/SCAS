"""Cache freshness tests — AIB v1.0 Vol 8.10 (30-minute TTL)."""

from datetime import datetime, timedelta, timezone

from app.weather.cache import is_fresh


def test_fresh_snapshot_within_ttl():
    captured_at = datetime.now(timezone.utc) - timedelta(minutes=10)
    assert is_fresh(captured_at, ttl_seconds=1800) is True


def test_stale_snapshot_beyond_ttl():
    captured_at = datetime.now(timezone.utc) - timedelta(minutes=45)
    assert is_fresh(captured_at, ttl_seconds=1800) is False


def test_just_inside_ttl_is_fresh():
    captured_at = datetime.now(timezone.utc) - timedelta(seconds=1750)
    assert is_fresh(captured_at, ttl_seconds=1800) is True


def test_just_outside_ttl_is_stale():
    captured_at = datetime.now(timezone.utc) - timedelta(seconds=1850)
    assert is_fresh(captured_at, ttl_seconds=1800) is False


def test_naive_datetime_is_treated_as_utc():
    # Construct a naive datetime the same way a legacy caller might,
    # without relying on the deprecated datetime.utcnow().
    captured_at = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(minutes=5)
    assert is_fresh(captured_at, ttl_seconds=1800) is True
