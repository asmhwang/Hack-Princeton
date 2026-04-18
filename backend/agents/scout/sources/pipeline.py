"""Scout signal ingest pipeline.

Two entry points on a shared core:

- :func:`ingest_tavily_result` — runs classify → persist for every raw
  Tavily hit (news/policy/logistics/macro).
- :func:`ingest_prebuilt_signal` — skips the classifier and persists a
  pre-built :class:`SignalClassification`. Used by the weather loop where
  thresholds are deterministic.

Both funnel through :func:`_persist_and_notify`:

1. Compute :func:`dedupe_hash` from ``(region, source_category,
   dedupe_keywords)``. Region defaults to ``"unknown"`` when the input did
   not carry a location; the keyword set preserves uniqueness.
2. Skip if a signal with the same hash exists inside the 72h window — the DB
   also enforces uniqueness on ``dedupe_hash`` as defense in depth.
3. Insert a :class:`Signal` row, then ``NOTIFY new_signal`` with the payload
   shape ``{"id": "<uuid>", "source_category": "<cat>"}`` (matches the
   contract in ``api/routes/dev.py``).

The pipeline does NOT catch LLM errors — callers decide whether one failing
result should take down the whole poll. The poll loops wrap per-result calls
in a try/except and log, so one bad classification cannot stall the rest.
"""

from __future__ import annotations

import json
import uuid
from decimal import Decimal
from typing import Any, Literal, Protocol

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from backend.agents.scout.processors.classify import classify_raw_signal
from backend.agents.scout.processors.dedupe import dedupe_hash, is_duplicate
from backend.db.models import Signal
from backend.llm.client import LLMClient
from backend.schemas import SignalClassification

log = structlog.get_logger()


class _Bus(Protocol):
    async def publish(self, channel: str, payload: str) -> None: ...


SourceCategory = Literal["news", "weather", "policy", "logistics", "macro"]


def _extract_url(raw: dict[str, Any]) -> list[str]:
    url = raw.get("url")
    return [str(url)] if url else []


async def _persist_and_notify(
    *,
    classification: SignalClassification,
    source_category: SourceCategory,
    source_name: str,
    source_urls: list[str],
    raw_payload: dict[str, Any],
    db_session: AsyncSession,
    bus: _Bus,
) -> uuid.UUID | None:
    region = classification.region or "unknown"
    dh = dedupe_hash(region, source_category, list(classification.dedupe_keywords))

    if await is_duplicate(db_session, dh):
        log.debug(
            "scout.pipeline.dedupe_hit",
            source_category=source_category,
            dedupe_hash=dh,
        )
        return None

    signal = Signal(
        id=uuid.uuid4(),
        source_category=source_category,
        source_name=source_name,
        title=classification.title,
        summary=classification.summary,
        region=classification.region,
        lat=classification.lat,
        lng=classification.lng,
        radius_km=(
            Decimal(str(classification.radius_km)) if classification.radius_km is not None else None
        ),
        source_urls=source_urls,
        confidence=Decimal(str(classification.confidence)),
        raw_payload=raw_payload,
        dedupe_hash=dh,
    )
    db_session.add(signal)
    await db_session.flush()

    await bus.publish(
        "new_signal",
        json.dumps({"id": str(signal.id), "source_category": source_category}),
    )
    return signal.id


async def ingest_tavily_result(
    raw: dict[str, Any],
    *,
    source_category: SourceCategory,
    source_name: str,
    db_session: AsyncSession,
    llm: LLMClient,
    bus: _Bus,
) -> uuid.UUID | None:
    """Run one Tavily result through classify → persist → notify.

    Returns the new signal's UUID or ``None`` if the result was a duplicate.
    """
    classification = await classify_raw_signal(raw, llm)
    return await _persist_and_notify(
        classification=classification,
        source_category=source_category,
        source_name=source_name,
        source_urls=_extract_url(raw),
        raw_payload={"tavily": raw, "severity": classification.severity},
        db_session=db_session,
        bus=bus,
    )


async def ingest_prebuilt_signal(
    *,
    classification: SignalClassification,
    source_category: SourceCategory,
    source_name: str,
    source_urls: list[str],
    raw_payload: dict[str, Any],
    db_session: AsyncSession,
    bus: _Bus,
) -> uuid.UUID | None:
    """Persist a pre-classified signal (used by threshold-driven sources like weather)."""
    return await _persist_and_notify(
        classification=classification,
        source_category=source_category,
        source_name=source_name,
        source_urls=source_urls,
        raw_payload=raw_payload,
        db_session=db_session,
        bus=bus,
    )
