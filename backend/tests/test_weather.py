"""TDD for the Open-Meteo weather source loop.

Three thresholds trigger a signal (per PRD §5.7):

- Current or forecast wind speed ≥ 100 km/h.
- 24h precipitation sum ≥ 100 mm.
- Open-Meteo weather code reporting a tropical-system (range 95–99 severe
  thunderstorm / tropical family — Open-Meteo returns ``weather_code`` per
  WMO 4677).

All three are deterministic, so weather does NOT call the LLM; it fabricates
a :class:`SignalClassification` inline and hands it to
:func:`ingest_prebuilt_signal`.

The DB and httpx client are both mocked so the test suite stays loop-safe.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import httpx
import pytest

from backend.agents.scout.sources import weather


class _SpyBus:
    def __init__(self) -> None:
        self.events: list[tuple[str, str]] = []

    async def publish(self, channel: str, payload: str) -> None:
        self.events.append((channel, payload))


class _IngestRecorder:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    async def record(self, **kwargs: Any) -> Any:
        self.calls.append(kwargs)
        return kwargs["classification"]


def _build_response(
    *,
    current_wind: float,
    hourly_wind: list[float],
    hourly_precip: list[float],
    weather_codes: list[int] | None = None,
) -> dict[str, Any]:
    return {
        "latitude": 22.6,
        "longitude": 120.3,
        "current": {"wind_speed_10m": current_wind, "weather_code": 0},
        "hourly": {
            "time": [f"2026-04-18T{h:02d}:00" for h in range(len(hourly_wind))],
            "wind_speed_10m": hourly_wind,
            "precipitation": hourly_precip,
            "weather_code": weather_codes or [0] * len(hourly_wind),
        },
    }


def _transport(payload: dict[str, Any]) -> httpx.MockTransport:
    def _handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=payload)

    return httpx.MockTransport(_handler)


@pytest.mark.asyncio
async def test_wind_threshold_emits_signal(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    recorder = _IngestRecorder()
    monkeypatch.setattr(weather, "ingest_prebuilt_signal", recorder.record)

    payload = _build_response(
        current_wind=120.0,
        hourly_wind=[110.0] * 24,
        hourly_precip=[1.0] * 24,
    )
    bus = _SpyBus()

    await weather.poll_once(
        watch_points=[weather.WatchPoint(id="PORT:KHH", name="Kaohsiung", lat=22.6, lng=120.3)],
        db_session=None,
        bus=bus,
        transport=_transport(payload),
    )

    assert len(recorder.calls) == 1
    classification = recorder.calls[0]["classification"]
    assert classification.severity >= 3
    assert "wind_100kmh" in classification.dedupe_keywords
    assert recorder.calls[0]["source_category"] == "weather"
    assert recorder.calls[0]["source_name"] == "open-meteo"


@pytest.mark.asyncio
async def test_precipitation_threshold_emits_signal(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    recorder = _IngestRecorder()
    monkeypatch.setattr(weather, "ingest_prebuilt_signal", recorder.record)

    payload = _build_response(
        current_wind=20.0,
        hourly_wind=[25.0] * 24,
        hourly_precip=[6.0] * 24,  # 144 mm / 24h
    )

    await weather.poll_once(
        watch_points=[weather.WatchPoint(id="PORT:KHH", name="Kaohsiung", lat=22.6, lng=120.3)],
        db_session=None,
        bus=_SpyBus(),
        transport=_transport(payload),
    )

    assert len(recorder.calls) == 1
    classification = recorder.calls[0]["classification"]
    assert "precip_100mm" in classification.dedupe_keywords


@pytest.mark.asyncio
async def test_tropical_code_emits_signal(monkeypatch: pytest.MonkeyPatch) -> None:
    recorder = _IngestRecorder()
    monkeypatch.setattr(weather, "ingest_prebuilt_signal", recorder.record)

    # WMO code 95 — thunderstorm — falls inside the tropical-family trigger band.
    codes = [0] * 23 + [95]
    payload = _build_response(
        current_wind=40.0,
        hourly_wind=[40.0] * 24,
        hourly_precip=[0.5] * 24,
        weather_codes=codes,
    )

    await weather.poll_once(
        watch_points=[weather.WatchPoint(id="PORT:KHH", name="Kaohsiung", lat=22.6, lng=120.3)],
        db_session=None,
        bus=_SpyBus(),
        transport=_transport(payload),
    )

    assert len(recorder.calls) == 1
    classification = recorder.calls[0]["classification"]
    assert "tropical_system" in classification.dedupe_keywords


@pytest.mark.asyncio
async def test_calm_weather_emits_nothing(monkeypatch: pytest.MonkeyPatch) -> None:
    recorder = _IngestRecorder()
    monkeypatch.setattr(weather, "ingest_prebuilt_signal", recorder.record)

    payload = _build_response(
        current_wind=15.0,
        hourly_wind=[20.0] * 24,
        hourly_precip=[0.1] * 24,
    )

    await weather.poll_once(
        watch_points=[weather.WatchPoint(id="PORT:KHH", name="Kaohsiung", lat=22.6, lng=120.3)],
        db_session=None,
        bus=_SpyBus(),
        transport=_transport(payload),
    )

    assert recorder.calls == []


@pytest.mark.asyncio
async def test_http_failure_is_isolated(monkeypatch: pytest.MonkeyPatch) -> None:
    recorder = _IngestRecorder()
    monkeypatch.setattr(weather, "ingest_prebuilt_signal", recorder.record)

    # First point fails (500), second point succeeds with a wind trigger.
    call_count = {"n": 0}

    def _flaky_handler(_request: httpx.Request) -> httpx.Response:
        call_count["n"] += 1
        if call_count["n"] == 1:
            return httpx.Response(500, json={"error": "upstream"})
        return httpx.Response(
            200,
            json=_build_response(
                current_wind=120.0,
                hourly_wind=[110.0] * 24,
                hourly_precip=[1.0] * 24,
            ),
        )

    await weather.poll_once(
        watch_points=[
            weather.WatchPoint(id="PORT:KHH", name="Kaohsiung", lat=22.6, lng=120.3),
            weather.WatchPoint(id="PORT:YTN", name="Yantian", lat=22.6, lng=114.3),
        ],
        db_session=None,
        bus=_SpyBus(),
        transport=httpx.MockTransport(_flaky_handler),
    )

    assert len(recorder.calls) == 1
    watch_point_info = recorder.calls[0]["raw_payload"]["watch_point"]
    assert watch_point_info["id"] == "PORT:YTN"
