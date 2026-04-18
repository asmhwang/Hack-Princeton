"""Tiny SQLite wrapper for caching model outputs keyed on prompt/schema hashes.

Used by :class:`backend.llm.client.LLMClient` for two purposes:

1. Resilience — cache hits short-circuit Gemini calls (saves quota in dev).
2. Demo-day offline mode — when ``DEMO_OFFLINE_CACHE=true`` the client
   MUST NOT call Gemini; it reads from this cache only. Writes are disabled
   under the flag so a live demo cannot pollute the seed snapshot.
"""

from __future__ import annotations

import os
import sqlite3
from pathlib import Path

_SCHEMA = (
    "CREATE TABLE IF NOT EXISTS cache ("
    "key TEXT PRIMARY KEY, "
    "value TEXT NOT NULL, "
    "created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP"
    ")"
)


class PromptCache:
    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.execute(_SCHEMA)

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self._path, isolation_level=None)

    @property
    def offline_mode(self) -> bool:
        return os.environ.get("DEMO_OFFLINE_CACHE", "false").lower() == "true"

    def get(self, key: str) -> str | None:
        with self._connect() as conn:
            row = conn.execute("SELECT value FROM cache WHERE key = ?", (key,)).fetchone()
        return row[0] if row else None

    def put(self, key: str, value: str) -> None:
        if self.offline_mode:
            return
        with self._connect() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO cache (key, value) VALUES (?, ?)",
                (key, value),
            )
