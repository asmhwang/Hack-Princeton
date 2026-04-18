"""TDD for Scout dedupe processor.

Covers two concerns:

1. Pure hash stability — :func:`dedupe_hash` must be order/whitespace/case
   insensitive for keywords but preserve meaningful differences.
2. DB window check — :func:`is_duplicate` must recognize a prior signal with
   the same hash within ``window_hours`` and ignore anything older.

The DB tests only run when Postgres is available (see conftest fixture
``_ensure_test_db``); otherwise they are skipped so the pure-hash coverage
still runs in LLM-only environments.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from backend.agents.scout.processors.dedupe import dedupe_hash, is_duplicate
from backend.db.models import Signal
from backend.db.session import session
from backend.tests.conftest import _pg


@pytest.fixture
def _require_pg() -> None:
    if not _pg["available"]:
        pytest.skip("Postgres not reachable; DB tests skipped")


def test_hash_stable_across_keyword_order() -> None:
    a = dedupe_hash("Taiwan Strait", "weather", ["typhoon", "Kaohsiung"])
    b = dedupe_hash("Taiwan Strait", "weather", ["Kaohsiung", "typhoon"])
    assert a == b


def test_hash_stable_across_case_and_whitespace() -> None:
    a = dedupe_hash("  Taiwan Strait ", "Weather", [" Typhoon ", "KAOHSIUNG"])
    b = dedupe_hash("taiwan strait", "weather", ["typhoon", "kaohsiung"])
    assert a == b


def test_hash_distinguishes_region() -> None:
    a = dedupe_hash("Taiwan Strait", "weather", ["typhoon"])
    b = dedupe_hash("South China Sea", "weather", ["typhoon"])
    assert a != b


def test_hash_distinguishes_category() -> None:
    a = dedupe_hash("EU", "policy", ["tariff"])
    b = dedupe_hash("EU", "news", ["tariff"])
    assert a != b


def test_hash_distinguishes_keywords() -> None:
    a = dedupe_hash("EU", "policy", ["tariff"])
    b = dedupe_hash("EU", "policy", ["tariff", "steel"])
    assert a != b


# ---------------------------------------------------------------------------
# DB window tests — require Postgres.
# ---------------------------------------------------------------------------


def _signal_with_hash(h: str, first_seen_at: datetime) -> Signal:
    return Signal(
        source_category="weather",
        source_name="test",
        title="test",
        summary=None,
        region="Taiwan Strait",
        lat=24.0,
        lng=120.0,
        radius_km=None,
        source_urls=[],
        confidence=Decimal("0.8"),
        raw_payload={},
        first_seen_at=first_seen_at,
        dedupe_hash=h,
    )


@pytest.mark.asyncio
async def test_is_duplicate_hits_within_window(_require_pg: None) -> None:
    h = dedupe_hash("Taiwan Strait", "weather", ["typhoon"])
    async with session() as s:
        s.add(_signal_with_hash(h, datetime.now(UTC).replace(tzinfo=None) - timedelta(hours=1)))
        await s.commit()
        assert await is_duplicate(s, h) is True


@pytest.mark.asyncio
async def test_is_duplicate_ignores_expired_window(_require_pg: None) -> None:
    h = dedupe_hash("Taiwan Strait", "weather", ["typhoon"])
    async with session() as s:
        s.add(_signal_with_hash(h, datetime.now(UTC).replace(tzinfo=None) - timedelta(hours=80)))
        await s.commit()
        assert await is_duplicate(s, h) is False


@pytest.mark.asyncio
async def test_is_duplicate_false_on_empty_db(_require_pg: None) -> None:
    async with session() as s:
        assert await is_duplicate(s, dedupe_hash("EU", "policy", ["tariff"])) is False
