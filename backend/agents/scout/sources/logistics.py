"""Logistics source loop — Tavily ``topic=general`` every 10 minutes.

Queries drawn from ``tavily_queries.md``. Logistics signals move intra-day
(port dwell, canal status, spot rates) so 10 min balances freshness and
Tavily quota.
"""

from __future__ import annotations

from typing import Any, Literal, Protocol

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from backend.agents.scout.sources.pipeline import ingest_tavily_result
from backend.llm.client import LLMClient

log = structlog.get_logger()

SOURCE_CATEGORY: Literal["logistics"] = "logistics"
SOURCE_NAME = "tavily.logistics"
CADENCE_SECONDS = 600
TOPIC = "general"
DAYS = 1

QUERIES: list[str] = [
    '"Panama Canal" draft restriction transits 2026',
    '"Suez Canal" traffic security restrictions 2026',
    '"Cape of Good Hope" rerouting carriers Asia Europe 2026',
    '"Shanghai" port congestion dwell time 2026',
    '"Los Angeles" OR "Long Beach" port dwell 2026',
    '"Rotterdam" OR "Antwerp" terminal delays 2026',
    '"drewry" world container index spike 2026',
    '"container spot rate" Asia US West Coast 2026',
    '"blank sailing" carrier alliance 2026',
    '"empty container" imbalance region 2026',
    '"rail ramp" intermodal dwell 2026',
    '"truck capacity" tightness market 2026',
    '"bunker fuel" IFO VLSFO price 2026',
    '"ULCV" ultra-large container vessel redeploy 2026',
    '"Ningbo-Zhoushan" port closure typhoon fog 2026',
    '"Houston" port Gulf Coast closure 2026',
    '"Chittagong" OR "Colombo" port strike closure 2026',
    '"air freight" rate index pharmaceuticals 2026',
    '"vessel sharing alliance" capacity adjustment 2026',
    '"ECDIS" navigational warning lane 2026',
]


class _Client(Protocol):
    async def search(self, query: str, *, topic: str, days: int = 1) -> list[dict[str, Any]]: ...


class _Bus(Protocol):
    async def publish(self, channel: str, payload: str) -> None: ...


async def poll_once(
    *,
    db_session: AsyncSession,
    llm: LLMClient,
    bus: _Bus,
    client: _Client,
) -> None:
    for query in QUERIES:
        try:
            results = await client.search(query, topic=TOPIC, days=DAYS)
        except Exception as err:
            log.warning(
                "scout.poll.search_failed",
                category=SOURCE_CATEGORY,
                query=query,
                error=str(err),
            )
            continue
        for raw in results:
            try:
                await ingest_tavily_result(
                    raw,
                    source_category=SOURCE_CATEGORY,
                    source_name=SOURCE_NAME,
                    db_session=db_session,
                    llm=llm,
                    bus=bus,
                )
            except Exception as err:
                log.warning(
                    "scout.poll.ingest_failed",
                    category=SOURCE_CATEGORY,
                    error=str(err),
                )
