"""Thin async wrapper over the Tavily search REST endpoint.

:class:`TavilyClient.search` posts to ``POST /search`` with the documented
JSON body and returns the ``results`` list verbatim. Three pieces of
resilience wrap that call:

- **Tenacity retry** — transient network errors and 5xx responses retry with
  exponential backoff up to three attempts. 4xx responses bubble up as
  :class:`httpx.HTTPStatusError` without retry so misconfiguration fails loud.
- **SQLite cache** — successful responses are persisted so ``DEMO_OFFLINE_CACHE``
  mode (demo-day kill switch) can serve the last-known payload without the
  network. Cold cache in offline mode returns ``[]`` rather than raising.
- **Pluggable transport** — tests inject :class:`httpx.MockTransport` so no
  sockets open in unit tests.

``topic`` is restricted to the values Tavily accepts (``"news"``, ``"general"``)
but we do not re-enum the value here — the upstream will 400 on unknown topics
and the caller wants that to surface in dev.
"""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
from pathlib import Path
from typing import Any, cast

import httpx
import structlog
from tenacity import (
    AsyncRetrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential_jitter,
)

log = structlog.get_logger()

_TAVILY_URL = "https://api.tavily.com/search"
_MAX_RESULTS = 10
_HTTP_TIMEOUT_S = 15.0
_HTTP_5XX_MIN = 500
_HTTP_5XX_MAX = 600
_CACHE_SCHEMA = (
    "CREATE TABLE IF NOT EXISTS tavily_cache ("
    "key TEXT PRIMARY KEY, "
    "payload TEXT NOT NULL, "
    "created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP"
    ")"
)


def _cache_key(query: str, topic: str, days: int) -> str:
    material = f"{topic}::{days}::{query.strip().lower()}"
    return hashlib.sha256(material.encode()).hexdigest()


class _Cache:
    def __init__(self, path: Path) -> None:
        self._path = path
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.execute(_CACHE_SCHEMA)

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self._path, isolation_level=None)

    def get(self, key: str) -> list[dict[str, Any]] | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT payload FROM tavily_cache WHERE key = ?", (key,)
            ).fetchone()
        if row is None:
            return None
        try:
            return cast(list[dict[str, Any]], json.loads(row[0]))
        except json.JSONDecodeError:
            log.warning("tavily.cache.corrupt", key=key)
            return None

    def put(self, key: str, payload: list[dict[str, Any]]) -> None:
        with self._connect() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO tavily_cache (key, payload) VALUES (?, ?)",
                (key, json.dumps(payload)),
            )


class TavilyClient:
    def __init__(
        self,
        *,
        cache_path: str | Path,
        api_key: str | None = None,
        transport: httpx.AsyncBaseTransport | httpx.MockTransport | None = None,
    ) -> None:
        self._api_key = api_key or os.environ.get("TAVILY_API_KEY")
        self._cache = _Cache(Path(cache_path))
        self._transport = transport

    @property
    def offline_mode(self) -> bool:
        return os.environ.get("DEMO_OFFLINE_CACHE", "false").lower() == "true"

    async def search(
        self,
        query: str,
        *,
        topic: str,
        days: int = 1,
    ) -> list[dict[str, Any]]:
        key = _cache_key(query, topic, days)

        if self.offline_mode:
            cached = self._cache.get(key)
            if cached is None:
                log.warning("tavily.offline.cold_cache", key=key, query=query, topic=topic)
                return []
            return cached

        if not self._api_key:
            raise RuntimeError("TAVILY_API_KEY unset and DEMO_OFFLINE_CACHE not enabled")

        body = {
            "api_key": self._api_key,
            "query": query,
            "topic": topic,
            "days": days,
            "max_results": _MAX_RESULTS,
            "include_answer": False,
        }

        results = await self._post_with_retry(body)
        self._cache.put(key, results)
        return results

    async def _post_with_retry(self, body: dict[str, Any]) -> list[dict[str, Any]]:
        async for attempt in AsyncRetrying(
            stop=stop_after_attempt(3),
            wait=wait_exponential_jitter(initial=1, max=8),
            retry=retry_if_exception_type((httpx.TransportError, _RetryableStatus)),
            reraise=True,
        ):
            with attempt:
                async with httpx.AsyncClient(
                    transport=self._transport,
                    timeout=_HTTP_TIMEOUT_S,
                ) as client:
                    resp = await client.post(_TAVILY_URL, json=body)
                    if _HTTP_5XX_MIN <= resp.status_code < _HTTP_5XX_MAX:
                        raise _RetryableStatus(f"tavily {resp.status_code}")
                    resp.raise_for_status()
                    data = resp.json()
                    return cast(list[dict[str, Any]], data.get("results", []))
        raise RuntimeError("unreachable: tenacity did not raise or return")


class _RetryableStatus(RuntimeError):
    """Marker for 5xx responses so tenacity retries them without touching 4xx."""
