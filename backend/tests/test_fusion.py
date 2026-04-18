"""TDD for Scout fusion pass.

Two scenarios cover the spec's definition of done:

1. **Fuse** — two unpromoted signals in the same 0.5° bucket within the
   48h window produce one disruption; both signals' ``promoted_to_disruption_id``
   is populated.
2. **No fuse** — a single unpromoted signal on its own does not produce a
   disruption.

Tests require Postgres so they are skipped when the test DB is unreachable,
same pattern as the other DB-dependent tests in this package.
"""

from __future__ import annotations

import json
import re
import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import BaseModel
from sqlalchemy import select

from backend.agents.scout.processors.dedupe import dedupe_hash
from backend.agents.scout.processors.fusion import run_fusion_pass
from backend.db.models import Disruption, Signal
from backend.db.session import session
from backend.llm.client import LLMClient
from backend.tests.conftest import _pg


@pytest.fixture
def _require_pg() -> None:
    if not _pg["available"]:
        pytest.skip("Postgres not reachable; fusion tests skipped")


def _make_signal(
    *,
    region: str,
    category: str,
    keywords: list[str],
    lat: float,
    lng: float,
    age_minutes: int = 30,
) -> Signal:
    first_seen = datetime.now(UTC).replace(tzinfo=None) - timedelta(minutes=age_minutes)
    return Signal(
        id=uuid.uuid4(),
        source_category=category,
        source_name="test",
        title=f"{category} event in {region}",
        summary=f"Synthetic {category} signal for fusion test",
        region=region,
        lat=lat,
        lng=lng,
        radius_km=None,
        source_urls=[],
        confidence=Decimal("0.8"),
        raw_payload={"severity": 3},
        first_seen_at=first_seen,
        dedupe_hash=dedupe_hash(region, category, keywords),
    )


@pytest.fixture
def llm(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> LLMClient:
    """An LLMClient whose `_raw_structured` returns a canned DisruptionDraft.

    The canned payload echoes whatever ``source_signal_ids`` are referenced
    in the prompt — the caller is responsible for wiring them into the
    fusion prompt. We extract every UUID in the prompt so the returned
    DisruptionDraft references the same signals the fusion code clustered.
    """
    c = LLMClient(cache_path=tmp_path / "cache.sqlite", model="flash")

    uuid_re = re.compile(
        r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"
    )

    async def fake_raw(*, prompt: str, schema: type[BaseModel]) -> str:
        ids = uuid_re.findall(prompt)
        draft = {
            "title": "Fused disruption from fixture",
            "summary": "Synthesized disruption description.",
            "category": "weather",
            "severity": 4,
            "region": "Taiwan Strait",
            "lat": 24.0,
            "lng": 120.0,
            "radius_km": 300.0,
            "confidence": 0.85,
            "source_signal_ids": ids,
        }
        return json.dumps(draft)

    monkeypatch.setattr(c, "_raw_structured", fake_raw)
    return c


@pytest.mark.asyncio
async def test_fusion_produces_disruption_for_cluster(llm: LLMClient, _require_pg: None) -> None:
    s1 = _make_signal(
        region="Taiwan Strait",
        category="weather",
        keywords=["typhoon", "taiwan"],
        lat=24.0,
        lng=120.0,
    )
    s2 = _make_signal(
        region="Taiwan Strait",
        category="news",
        keywords=["port", "kaohsiung", "closure"],
        lat=24.2,
        lng=120.1,
    )

    async with session() as s:
        s.add(s1)
        s.add(s2)
        await s.commit()

        new_ids = await run_fusion_pass(s, llm)
        await s.commit()

        assert len(new_ids) == 1

        disruption = (
            await s.execute(select(Disruption).where(Disruption.id == new_ids[0]))
        ).scalar_one()
        assert set(disruption.source_signal_ids) == {s1.id, s2.id}

        refreshed = (
            (await s.execute(select(Signal).where(Signal.id.in_([s1.id, s2.id])))).scalars().all()
        )
        assert all(sig.promoted_to_disruption_id == disruption.id for sig in refreshed)


@pytest.mark.asyncio
async def test_fusion_skips_singleton(llm: LLMClient, _require_pg: None) -> None:
    solo = _make_signal(
        region="Rotterdam",
        category="logistics",
        keywords=["rotterdam", "crane"],
        lat=51.9,
        lng=4.5,
    )

    async with session() as s:
        s.add(solo)
        await s.commit()

        new_ids = await run_fusion_pass(s, llm)
        await s.commit()

        assert new_ids == []
        refreshed = (await s.execute(select(Signal).where(Signal.id == solo.id))).scalar_one()
        assert refreshed.promoted_to_disruption_id is None


@pytest.mark.asyncio
async def test_fusion_ignores_already_promoted(llm: LLMClient, _require_pg: None) -> None:
    """Signals with promoted_to_disruption_id already set must be excluded."""
    already = _make_signal(
        region="Taiwan Strait",
        category="weather",
        keywords=["typhoon", "old"],
        lat=24.0,
        lng=120.0,
    )
    already.promoted_to_disruption_id = uuid.uuid4()

    partner = _make_signal(
        region="Taiwan Strait",
        category="news",
        keywords=["port", "fresh"],
        lat=24.1,
        lng=120.2,
    )

    async with session() as s:
        s.add(already)
        s.add(partner)
        await s.commit()

        new_ids = await run_fusion_pass(s, llm)
        await s.commit()

        # Only one unpromoted signal in bucket → no fusion.
        assert new_ids == []
