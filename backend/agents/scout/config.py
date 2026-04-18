"""Runtime knobs for the Scout agent.

Environment variables (read at process start via ``pydantic-settings``):

- ``SCOUT_DATABASE_URL`` — falls back to ``DATABASE_URL`` then the shared
  default in :mod:`backend.db.session`.
- ``SCOUT_MODEL`` — Gemini alias for the classifier (``flash`` by default;
  Scout is high-volume, Flash is the price/latency sweet spot).
- ``SCOUT_STATE_PATH`` — checkpoint JSON location. Dedalus systemd unit
  sets ``StateDirectory=supplai`` → ``/var/lib/supplai``.
- ``SCOUT_HEALTH_PORT`` — bind port for the AgentBase health server; 0
  means "pick an ephemeral port" (integration tests rely on this).
- ``SCOUT_LLM_CACHE_PATH`` — SQLite offline cache for the LLM client.
- ``SCOUT_TAVILY_CACHE_PATH`` — SQLite offline cache for Tavily.
- ``SCOUT_FUSION_CADENCE_S`` — fusion pass interval; shorter than the
  slowest source so a cluster gets picked up before the 72h window.
- ``SCOUT_WATCH_POINTS`` — JSON list of ``{id,name,lat,lng}`` for the
  weather loop. Empty list disables the weather loop entirely.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from backend.agents.scout.sources.weather import WatchPoint

_DEFAULT_WATCH_POINTS: list[dict[str, Any]] = [
    {"id": "PORT-SZX", "name": "Shenzhen", "lat": 22.5431, "lng": 114.0579},
    {"id": "PORT-KHH", "name": "Kaohsiung", "lat": 22.6273, "lng": 120.3014},
    {"id": "PORT-SIN", "name": "Singapore", "lat": 1.2644, "lng": 103.8200},
    {"id": "PORT-ROT", "name": "Rotterdam", "lat": 51.9500, "lng": 4.1400},
    {"id": "PORT-LAX", "name": "Los Angeles", "lat": 33.7300, "lng": -118.2600},
]


class ScoutSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="SCOUT_",
        extra="ignore",
    )

    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/supplai"
    model: str = "flash"
    state_path: Path = Path("/var/lib/supplai/scout-state.json")
    health_port: int = 0
    llm_cache_path: Path = Path("/var/lib/supplai/scout-llm-cache.sqlite")
    tavily_cache_path: Path = Path("/var/lib/supplai/scout-tavily-cache.sqlite")
    fusion_cadence_s: int = 120
    watch_points: list[WatchPoint] = Field(default_factory=list)

    @field_validator("watch_points", mode="before")
    @classmethod
    def _parse_watch_points(cls, v: Any) -> list[WatchPoint]:
        if v is None or v == "":
            raw = _DEFAULT_WATCH_POINTS
        elif isinstance(v, str):
            raw = json.loads(v)
        elif isinstance(v, list):
            raw = v
        else:
            raise TypeError(f"watch_points must be list or JSON string, got {type(v).__name__}")
        return [
            WatchPoint(
                id=str(p["id"]), name=str(p["name"]), lat=float(p["lat"]), lng=float(p["lng"])
            )
            if not isinstance(p, WatchPoint)
            else p
            for p in raw
        ]
