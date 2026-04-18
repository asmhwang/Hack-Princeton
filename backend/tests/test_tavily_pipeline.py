"""TDD for the shared Tavily ingest pipeline.

The pipeline ties four things together for every Tavily-backed source (news,
policy, logistics, macro):

1. Classify raw result via :func:`classify_raw_signal` (LLM-mocked here).
2. Compute :func:`dedupe_hash` from the classification and skip if the signal
   already exists within the 72h window.
3. Insert a new :class:`Signal` row populated from the classification.
4. ``NOTIFY new_signal`` with a JSON payload ``{"id": str, "source_category":
   str}`` — matches the contract used by ``api/routes/dev.py``.

Tests require Postgres — skipped when unreachable, same pattern as the
existing DB-dependent Scout tests.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from pydantic import BaseModel
from sqlalchemy import select

from backend.agents.scout.processors.dedupe import dedupe_hash
from backend.agents.scout.sources.pipeline import ingest_tavily_result
from backend.db.models import Signal
from backend.db.session import session
from backend.llm.client import LLMClient
from backend.tests.conftest import _pg


@pytest.fixture
def _require_pg() -> None:
    if not _pg["available"]:
        pytest.skip("Postgres not reachable; pipeline tests skipped")


class _SpyBus:
    def __init__(self) -> None:
        self.events: list[tuple[str, str]] = []

    async def publish(self, channel: str, payload: str) -> None:
        self.events.append((channel, payload))


def _fake_classification_llm(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> LLMClient:
    """LLMClient whose ``_raw_structured`` returns a canned SignalClassification."""
    llm = LLMClient(cache_path=tmp_path / "cache.sqlite", model="flash")

    async def fake_raw(*, prompt: str, schema: type[BaseModel]) -> str:
        return json.dumps(
            {
                "source_category": "news",
                "title": "Port strike escalates at Kaohsiung",
                "summary": "Dockworker walkout enters third day affecting container throughput.",
                "region": "Taiwan Strait",
                "lat": 22.6,
                "lng": 120.3,
                "radius_km": 120.0,
                "severity": 3,
                "confidence": 0.82,
                "dedupe_keywords": ["port", "strike", "kaohsiung"],
            }
        )

    monkeypatch.setattr(llm, "_raw_structured", fake_raw)
    return llm


@pytest.mark.asyncio
async def test_ingest_inserts_signal_and_notifies(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    _require_pg: None,
) -> None:
    llm = _fake_classification_llm(tmp_path, monkeypatch)
    bus = _SpyBus()
    raw: dict[str, Any] = {
        "title": "Kaohsiung strike",
        "url": "https://example.com/kh",
        "content": "...",
    }

    async with session() as s:
        signal_id = await ingest_tavily_result(
            raw,
            source_category="news",
            source_name="tavily.news",
            db_session=s,
            llm=llm,
            bus=bus,
        )
        await s.commit()

    assert signal_id is not None

    async with session() as s:
        rows = (await s.execute(select(Signal).where(Signal.id == signal_id))).scalars().all()
    assert len(rows) == 1
    row = rows[0]
    assert row.source_category == "news"
    assert row.source_name == "tavily.news"
    assert row.title == "Port strike escalates at Kaohsiung"
    assert row.region == "Taiwan Strait"
    assert row.source_urls == ["https://example.com/kh"]

    assert len(bus.events) == 1
    channel, payload = bus.events[0]
    assert channel == "new_signal"
    parsed = json.loads(payload)
    assert parsed == {"id": str(signal_id), "source_category": "news"}


@pytest.mark.asyncio
async def test_ingest_skips_duplicate_within_window(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    _require_pg: None,
) -> None:
    llm = _fake_classification_llm(tmp_path, monkeypatch)
    bus = _SpyBus()
    raw: dict[str, Any] = {
        "title": "Kaohsiung strike",
        "url": "https://example.com/kh",
        "content": "...",
    }

    # First call writes the signal.
    async with session() as s:
        first_id = await ingest_tavily_result(
            raw,
            source_category="news",
            source_name="tavily.news",
            db_session=s,
            llm=llm,
            bus=bus,
        )
        await s.commit()
    assert first_id is not None
    assert len(bus.events) == 1

    # Second call with identical raw/classification must not insert nor notify.
    async with session() as s:
        dup_id = await ingest_tavily_result(
            raw,
            source_category="news",
            source_name="tavily.news",
            db_session=s,
            llm=llm,
            bus=bus,
        )
        await s.commit()
    assert dup_id is None
    assert len(bus.events) == 1

    # Hash must match what the classifier produced.
    expected_hash = dedupe_hash("Taiwan Strait", "news", ["port", "strike", "kaohsiung"])
    async with session() as s:
        row = (
            await s.execute(select(Signal).where(Signal.dedupe_hash == expected_hash))
        ).scalar_one()
        assert row.id == first_id


@pytest.mark.asyncio
async def test_ingest_handles_missing_region(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    _require_pg: None,
) -> None:
    """Classifier may return region=None; pipeline must still dedupe and insert."""
    llm = LLMClient(cache_path=tmp_path / "cache.sqlite", model="flash")

    async def fake_raw(*, prompt: str, schema: type[BaseModel]) -> str:
        return json.dumps(
            {
                "source_category": "macro",
                "title": "Baltic Dry Index surges 12%",
                "summary": "Capesize rates lead the move on China iron-ore restock.",
                "region": None,
                "lat": None,
                "lng": None,
                "radius_km": None,
                "severity": 2,
                "confidence": 0.7,
                "dedupe_keywords": ["baltic", "capesize", "iron ore"],
            }
        )

    monkeypatch.setattr(llm, "_raw_structured", fake_raw)
    bus = _SpyBus()
    raw: dict[str, Any] = {
        "title": "BDI move",
        "url": "https://example.com/bdi",
        "content": "...",
    }

    async with session() as s:
        signal_id = await ingest_tavily_result(
            raw,
            source_category="macro",
            source_name="tavily.macro",
            db_session=s,
            llm=llm,
            bus=bus,
        )
        await s.commit()

    assert signal_id is not None
    assert len(bus.events) == 1
