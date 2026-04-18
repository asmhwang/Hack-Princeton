"""Integration: ``ScoutAgent`` end-to-end with injected canned Tavily result.

Per master plan §5.11 Step 3: inject a canned Tavily result, run Scout for
a short window, assert a signal row was created and ``new_signal`` fired.

The canned path stubs three things so the test is hermetic:

- ``TavilyClient`` replaced with a spy returning one hit on the first
  ``news`` query then empty on everything else.
- ``LLMClient._raw_structured`` monkey-patched to return a fixed
  :class:`SignalClassification` JSON — bypasses Gemini entirely.
- Source cadences are module-level constants, so we drive the loop once
  via ``asyncio.wait_for`` on the ``new_signal`` watcher instead of
  sleeping for the full 60s news cadence.
"""

from __future__ import annotations

import asyncio
import json
import uuid
from pathlib import Path
from typing import Any

import pytest
from pydantic import BaseModel
from sqlalchemy import select

from backend.agents.scout.config import ScoutSettings
from backend.agents.scout.main import ScoutAgent
from backend.agents.scout.sources import news
from backend.db.bus import EventBus
from backend.db.models import Signal
from backend.db.session import session
from backend.llm.client import LLMClient
from backend.tests.conftest import _pg

_WAIT_TIMEOUT_S = 10.0
_POLL_INTERVAL_S = 0.1


@pytest.fixture
def _require_pg() -> None:
    if not _pg["available"]:
        pytest.skip("Postgres not reachable; scout main tests skipped")


class _FakeTavily:
    """Returns a single canned hit on the first call, empty afterwards."""

    def __init__(self, hit: dict[str, Any]) -> None:
        self._hit = hit
        self._served = False

    async def search(self, query: str, *, topic: str, days: int = 1) -> list[dict[str, Any]]:
        if self._served:
            return []
        self._served = True
        return [self._hit]


def _make_llm(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> LLMClient:
    """LLMClient whose `_raw_structured` short-circuits to a canned classification."""
    client = LLMClient(cache_path=tmp_path / "scout-llm.sqlite", model="flash")

    async def fake_raw(*, prompt: str, schema: type[BaseModel]) -> str:
        return json.dumps(
            {
                "source_category": "news",
                "title": "Port strike escalates at Kaohsiung",
                "summary": "Dockworkers extend walkout; terminal throughput halved.",
                "region": "Taiwan Strait",
                "lat": 22.6,
                "lng": 120.3,
                "radius_km": 150.0,
                "severity": 3,
                "confidence": 0.8,
                "dedupe_keywords": ["kaohsiung", "strike", "port"],
            }
        )

    monkeypatch.setattr(client, "_raw_structured", fake_raw)
    return client


class _NotifyWatcher:
    def __init__(self, dsn: str, channel: str) -> None:
        self._bus = EventBus(dsn)
        self._channel = channel
        self.payloads: list[str] = []

    async def start(self) -> None:
        await self._bus.start()
        await self._bus.subscribe(self._channel, self._on)

    async def stop(self) -> None:
        await self._bus.stop()

    async def _on(self, payload: str) -> None:
        self.payloads.append(payload)

    async def wait_any(self, timeout_s: float) -> str | None:
        deadline = asyncio.get_event_loop().time() + timeout_s
        while asyncio.get_event_loop().time() < deadline:
            if self.payloads:
                return self.payloads[0]
            await asyncio.sleep(_POLL_INTERVAL_S)
        return None


@pytest.mark.asyncio
async def test_canned_news_hit_yields_signal_and_notify(
    postgresql_url: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    _require_pg: None,
) -> None:
    # Short-circuit policy/logistics/macro loops to zero queries so we only
    # exercise the news path in the ≤10s window.
    monkeypatch.setattr("backend.agents.scout.sources.policy.QUERIES", [])
    monkeypatch.setattr("backend.agents.scout.sources.logistics.QUERIES", [])
    monkeypatch.setattr("backend.agents.scout.sources.macro.QUERIES", [])
    monkeypatch.setattr("backend.agents.scout.sources.news.QUERIES", [news.QUERIES[0]])

    settings = ScoutSettings(
        database_url=postgresql_url,
        state_path=tmp_path / "scout-state.json",
        health_port=0,
        llm_cache_path=tmp_path / "scout-llm.sqlite",
        tavily_cache_path=tmp_path / "scout-tavily.sqlite",
        fusion_cadence_s=3600,
        watch_points=[],
    )
    llm = _make_llm(tmp_path, monkeypatch)
    tavily = _FakeTavily(
        hit={
            "title": "Kaohsiung dockworkers strike",
            "url": "https://example.com/kh-strike",
            "content": "Workers extended strike into third day.",
        }
    )

    watcher = _NotifyWatcher(postgresql_url, "new_signal")
    await watcher.start()

    agent = ScoutAgent(settings=settings, llm=llm, tavily=tavily)
    await agent.start()
    try:
        payload = await watcher.wait_any(_WAIT_TIMEOUT_S)
    finally:
        await agent.stop()
        await watcher.stop()

    assert payload is not None, "new_signal NOTIFY did not arrive"
    parsed = json.loads(payload)
    assert parsed["source_category"] == "news"
    signal_id = uuid.UUID(parsed["id"])

    async with session() as s:
        row = (await s.execute(select(Signal).where(Signal.id == signal_id))).scalar_one()
        assert row.source_category == "news"
        assert row.title == "Port strike escalates at Kaohsiung"
        assert row.source_urls == ["https://example.com/kh-strike"]


@pytest.mark.asyncio
async def test_background_tasks_registered(tmp_path: Path) -> None:
    """Sanity: ``background_tasks`` returns 5 coroutines (4 tavily + fusion) when
    ``watch_points`` is empty, 6 otherwise."""
    empty = ScoutSettings(
        database_url="postgresql+asyncpg://x/x",
        state_path=tmp_path / "s.json",
        llm_cache_path=tmp_path / "l.sqlite",
        tavily_cache_path=tmp_path / "t.sqlite",
        watch_points=[],
    )
    agent = ScoutAgent(
        settings=empty,
        llm=LLMClient(cache_path=tmp_path / "l.sqlite", model="flash"),
        tavily=_FakeTavily(hit={}),
    )
    coros = agent.background_tasks()
    try:
        assert len(coros) == 5
    finally:
        for c in coros:
            c.close()

    from backend.agents.scout.sources.weather import WatchPoint

    with_pts = ScoutSettings(
        database_url="postgresql+asyncpg://x/x",
        state_path=tmp_path / "s.json",
        llm_cache_path=tmp_path / "l.sqlite",
        tavily_cache_path=tmp_path / "t.sqlite",
        watch_points=[WatchPoint(id="P1", name="P1", lat=0.0, lng=0.0)],
    )
    agent2 = ScoutAgent(
        settings=with_pts,
        llm=LLMClient(cache_path=tmp_path / "l.sqlite", model="flash"),
        tavily=_FakeTavily(hit={}),
    )
    coros2 = agent2.background_tasks()
    try:
        assert len(coros2) == 6
    finally:
        for c in coros2:
            c.close()
