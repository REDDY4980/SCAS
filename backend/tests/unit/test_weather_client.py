"""Client retry-logic tests — AIB v1.0 Vol 8.11 ('retry once on timeout')."""

import httpx
import pytest

from app.weather.client import (
    OpenMeteoClient,
    RawWeatherResponse,
    WeatherProviderClient,
    WeatherProviderError,
    fetch_with_retry,
)


class _CountingClient(WeatherProviderClient):
    """Fails N times then succeeds, to exercise fetch_with_retry."""

    name = "counting"

    def __init__(self, fail_times: int):
        self.fail_times = fail_times
        self.calls = 0

    def fetch(self, latitude: float, longitude: float) -> RawWeatherResponse:
        self.calls += 1
        if self.calls <= self.fail_times:
            raise WeatherProviderError("simulated failure")
        return RawWeatherResponse(provider=self.name, payload={"ok": True})


def test_fetch_with_retry_succeeds_after_one_failure():
    client = _CountingClient(fail_times=1)
    result = fetch_with_retry(client, 16.0, 75.0)
    assert result.payload == {"ok": True}
    assert client.calls == 2


def test_fetch_with_retry_gives_up_after_second_failure():
    client = _CountingClient(fail_times=2)
    with pytest.raises(WeatherProviderError):
        fetch_with_retry(client, 16.0, 75.0)
    assert client.calls == 2  # exactly one retry, not unlimited


def test_open_meteo_client_wraps_timeout(monkeypatch):
    def fake_get(*args, **kwargs):
        raise httpx.TimeoutException("simulated timeout")

    monkeypatch.setattr(httpx, "get", fake_get)
    client = OpenMeteoClient()
    with pytest.raises(WeatherProviderError, match="timed out"):
        client.fetch(16.0, 75.0)


def test_open_meteo_client_wraps_provider_error_response(monkeypatch):
    class FakeResponse:
        def raise_for_status(self):
            pass

        def json(self):
            return {"error": True, "reason": "Cannot initialize WeatherVariable"}

    monkeypatch.setattr(httpx, "get", lambda *a, **k: FakeResponse())
    client = OpenMeteoClient()
    with pytest.raises(WeatherProviderError, match="Cannot initialize"):
        client.fetch(16.0, 75.0)


def test_open_meteo_client_success(monkeypatch):
    class FakeResponse:
        def raise_for_status(self):
            pass

        def json(self):
            return {"current": {"temperature_2m": 30.0}}

    monkeypatch.setattr(httpx, "get", lambda *a, **k: FakeResponse())
    client = OpenMeteoClient()
    result = client.fetch(16.0, 75.0)
    assert result.provider == "open-meteo"
    assert result.payload["current"]["temperature_2m"] == 30.0
