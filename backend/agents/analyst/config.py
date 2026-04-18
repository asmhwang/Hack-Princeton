"""Runtime knobs for the Analyst agent.

Environment variables (read at process start via ``pydantic-settings``):

- ``ANALYST_DATABASE_URL`` — falls back to ``DATABASE_URL`` then the shared
  default in :mod:`backend.db.session` to keep local dev seamless.
- ``ANALYST_MODEL`` — Gemini alias (``pro`` by default; tool-loop complexity
  justifies the Pro tier, per WORKTREE_PLAN gotchas).
- ``ANALYST_MAX_TOOL_ITERS`` — hard cap before ``LLMClient.with_tools``
  raises; caller falls back.
- ``ANALYST_SCHEMA_CACHE_KEY`` — shared Gemini cached-content handle key for
  the DB schema summary (bumped when schema changes).
- ``ANALYST_STATE_PATH`` — checkpoint JSON location; Dedalus systemd unit
  sets ``StateDirectory=supplai`` → ``/var/lib/supplai``.
- ``ANALYST_HEALTH_PORT`` — bind port for the AgentBase health server; 0
  means "pick an ephemeral port" (integration tests rely on this).
- ``ANALYST_LLM_CACHE_PATH`` — SQLite offline cache for the LLM client.
"""

from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class AnalystSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="ANALYST_",
        extra="ignore",
    )

    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/supplai"
    model: str = "pro"
    max_tool_iters: int = 6
    schema_cache_key: str = "analyst_schema_v1"
    state_path: Path = Path("/var/lib/supplai/analyst-state.json")
    health_port: int = 0
    llm_cache_path: Path = Path("/var/lib/supplai/analyst-llm-cache.sqlite")
