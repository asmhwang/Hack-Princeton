"""Runtime knobs for the Strategist agent.

Environment variables (read at process start via ``pydantic-settings``):

- ``STRATEGIST_DATABASE_URL`` — falls back to the shared default in
  :mod:`backend.db.session` when unset.
- ``STRATEGIST_MODEL`` — Gemini alias; defaults to ``pro`` — options +
  drafts are complex reasoning, not classification.
- ``STRATEGIST_MAX_TOOL_ITERS`` — hard cap for the ``with_tools`` loop on
  the options processor.
- ``STRATEGIST_SCHEMA_CACHE_KEY`` — shared cached-content handle key for
  the DB schema summary (bumped when schema changes).
- ``STRATEGIST_STATE_PATH`` — checkpoint JSON location; Dedalus systemd unit
  sets ``StateDirectory=supplai`` → ``/var/lib/supplai``.
- ``STRATEGIST_HEALTH_PORT`` — bind port for AgentBase health server.
- ``STRATEGIST_LLM_CACHE_PATH`` — SQLite offline cache for the LLM client.
"""

from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class StrategistSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="STRATEGIST_",
        extra="ignore",
    )

    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/supplai"
    model: str = "pro"
    max_tool_iters: int = 8
    schema_cache_key: str = "strategist_schema_v1"
    state_path: Path = Path("/var/lib/supplai/strategist-state.json")
    health_port: int = 0
    llm_cache_path: Path = Path("/var/lib/supplai/strategist-llm-cache.sqlite")
