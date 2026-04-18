"""Weather source loop — Open-Meteo poll with deterministic thresholds.

No auth required (Open-Meteo is free for non-commercial use). Weather does
not call the classifier LLM: triggers are a three-branch rubric on the
response.

Triggers (any one fires a signal):

- Current or next-24h forecast wind speed ≥ 100 km/h.
- 24h forecast precipitation sum ≥ 100 mm.
- Any hourly ``weather_code`` in the tropical-system band
  (WMO 4677 codes 95–99 thunderstorm / severe thunderstorm).

On trigger we build a :class:`SignalClassification` and hand it to
:func:`ingest_prebuilt_signal`. Dedupe (72h window) lives in the pipeline,
so repeated polls over a long-lived storm collapse to one signal row.
"""

from __future__ import annotations

from typing import Any, Literal, NamedTuple, Protocol

import httpx
import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from backend.agents.scout.sources.pipeline import ingest_prebuilt_signal
from backend.schemas import SignalClassification

log = structlog.get_logger()

SOURCE_CATEGORY: Literal["weather"] = "weather"
SOURCE_NAME = "open-meteo"
CADENCE_SECONDS = 300

_OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"
_HTTP_TIMEOUT_S = 15.0

_WIND_THRESHOLD_KMH = 100.0
_PRECIP_THRESHOLD_MM_24H = 100.0
_TROPICAL_CODE_MIN = 95
_TROPICAL_CODE_MAX = 99
_FORECAST_WINDOW_HOURS = 24
_IMPACT_RADIUS_KM = 150.0


class WatchPoint(NamedTuple):
    id: str
    name: str
    lat: float
    lng: float


class _Bus(Protocol):
    async def publish(self, channel: str, payload: str) -> None: ...


async def _fetch(
    point: WatchPoint,
    *,
    transport: httpx.AsyncBaseTransport | httpx.MockTransport | None,
) -> dict[str, Any]:
    params: dict[str, str | float] = {
        "latitude": point.lat,
        "longitude": point.lng,
        "current": "wind_speed_10m,weather_code",
        "hourly": "wind_speed_10m,precipitation,weather_code",
        "forecast_days": 2,
        "wind_speed_unit": "kmh",
    }
    async with httpx.AsyncClient(transport=transport, timeout=_HTTP_TIMEOUT_S) as client:
        resp = await client.get(_OPEN_METEO_URL, params=params)
        resp.raise_for_status()
        data: dict[str, Any] = resp.json()
        return data


def _detect_triggers(data: dict[str, Any]) -> tuple[list[str], dict[str, float]]:
    current_wind = float(data.get("current", {}).get("wind_speed_10m", 0.0) or 0.0)
    hourly = data.get("hourly", {}) or {}
    winds = [float(v or 0.0) for v in (hourly.get("wind_speed_10m") or [])][
        :_FORECAST_WINDOW_HOURS
    ]
    precip = [float(v or 0.0) for v in (hourly.get("precipitation") or [])][
        :_FORECAST_WINDOW_HOURS
    ]
    codes = [int(v or 0) for v in (hourly.get("weather_code") or [])][
        :_FORECAST_WINDOW_HOURS
    ]

    max_wind = max([current_wind, *winds]) if winds else current_wind
    precip_24h = sum(precip)

    triggers: list[str] = []
    if max_wind >= _WIND_THRESHOLD_KMH:
        triggers.append("wind_100kmh")
    if precip_24h >= _PRECIP_THRESHOLD_MM_24H:
        triggers.append("precip_100mm")
    if any(_TROPICAL_CODE_MIN <= c <= _TROPICAL_CODE_MAX for c in codes):
        triggers.append("tropical_system")

    metrics = {
        "max_wind_kmh": max_wind,
        "precip_24h_mm": precip_24h,
    }
    return triggers, metrics


def _build_classification(
    point: WatchPoint, triggers: list[str], metrics: dict[str, float]
) -> SignalClassification:
    severity = 3 if len(triggers) == 1 else 4
    title = f"Severe weather threshold at {point.name}"
    summary = (
        f"Open-Meteo thresholds triggered: {', '.join(triggers)}. "
        f"Max wind {metrics['max_wind_kmh']:.0f} km/h, "
        f"24h precipitation {metrics['precip_24h_mm']:.0f} mm."
    )
    return SignalClassification(
        source_category="weather",
        title=title,
        summary=summary,
        region=point.name,
        lat=point.lat,
        lng=point.lng,
        radius_km=_IMPACT_RADIUS_KM,
        severity=severity,
        confidence=0.9,
        dedupe_keywords=["weather", *triggers],
    )


async def poll_once(
    *,
    watch_points: list[WatchPoint],
    db_session: AsyncSession,
    bus: _Bus,
    transport: httpx.AsyncBaseTransport | httpx.MockTransport | None = None,
) -> None:
    for point in watch_points:
        try:
            data = await _fetch(point, transport=transport)
        except Exception as err:
            log.warning(
                "scout.weather.fetch_failed",
                point_id=point.id,
                error=str(err),
            )
            continue

        triggers, metrics = _detect_triggers(data)
        if not triggers:
            continue

        classification = _build_classification(point, triggers, metrics)
        try:
            await ingest_prebuilt_signal(
                classification=classification,
                source_category=SOURCE_CATEGORY,
                source_name=SOURCE_NAME,
                source_urls=[],
                raw_payload={
                    "watch_point": {"id": point.id, "name": point.name},
                    "metrics": metrics,
                    "triggers": triggers,
                },
                db_session=db_session,
                bus=bus,
            )
        except Exception as err:
            log.warning(
                "scout.weather.ingest_failed",
                point_id=point.id,
                error=str(err),
            )
