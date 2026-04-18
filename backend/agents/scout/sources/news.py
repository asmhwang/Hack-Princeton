"""News source loop — Tavily ``topic=news`` every 60 seconds.

Queries are the 20 tuned news searches from ``tavily_queries.md``. Keep this
list in lockstep with the judging artifact; a drift test in
``test_tavily_sources.py`` enforces the count.

``poll_once`` runs one fan-out pass: one Tavily call per query, every result
piped through :func:`ingest_tavily_result`. A per-result failure is logged and
swallowed so one bad classification does not stall the rest of the batch.
"""

from __future__ import annotations

from typing import Any, Literal, Protocol

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from backend.agents.scout.sources.pipeline import ingest_tavily_result
from backend.llm.client import LLMClient

log = structlog.get_logger()

SOURCE_CATEGORY: Literal["news"] = "news"
SOURCE_NAME = "tavily.news"
CADENCE_SECONDS = 60
TOPIC = "news"
DAYS = 1

QUERIES: list[str] = [
    '("port strike" OR "dockworker walkout") ("2026" OR "this week")',
    '("ILWU" OR "ILA") strike authorization vote',
    '"factory fire" (automotive OR semiconductor OR pharmaceutical) 2026',
    '"refinery outage" OR "refinery shutdown" 2026',
    '"container ship" (collision OR grounding OR fire) 2026',
    '"warehouse fire" logistics distribution center 2026',
    '"chemical leak" (plant OR facility) supply chain 2026',
    '"trucker strike" OR "haulier strike" Europe 2026',
    '"power outage" industrial park ("Shenzhen" OR "Kaohsiung" OR "Chennai")',
    '"earthquake" magnitude 6 industrial 2026',
    '"pipeline rupture" oil gas supply chain 2026',
    '"shipping lane" closed OR blocked OR diverted 2026',
    '"air cargo" disruption OR suspension airline 2026',
    '"rail strike" freight operator 2026',
    '"bridge collapse" freight OR cargo 2026',
    '"cyberattack" logistics OR port OR shipping 2026',
    '"airport closure" cargo hub 2026',
    '"civil unrest" OR "protests" (port OR factory) 2026',
    '"supplier bankruptcy" tier one automotive 2026',
    '"typhoon" OR "hurricane" port closure preemptive 2026',
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
