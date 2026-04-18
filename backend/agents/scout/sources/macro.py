"""Macro source loop — Tavily ``topic=general`` every 30 minutes.

Slow cadence reflects the signal domain: rates, FX, commodities move on
scheduled prints or central-bank decisions, so sub-hour polling wastes
Tavily quota without raising recall.
"""

from __future__ import annotations

from typing import Any, Literal, Protocol

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from backend.agents.scout.sources.pipeline import ingest_tavily_result
from backend.llm.client import LLMClient

log = structlog.get_logger()

SOURCE_CATEGORY: Literal["macro"] = "macro"
SOURCE_NAME = "tavily.macro"
CADENCE_SECONDS = 1800
TOPIC = "general"
DAYS = 2

QUERIES: list[str] = [
    '"Federal Reserve" rate decision FOMC 2026',
    '"ECB" deposit rate decision 2026',
    '"PBOC" ("MLF" OR "reserve ratio" OR "LPR") 2026',
    '"Bank of Japan" policy yield curve 2026',
    '"CPI" inflation print United States 2026',
    '"PPI" producer prices China 2026',
    '"PMI" manufacturing global 2026',
    '"Brent crude" price OPEC decision 2026',
    '"copper" LME price supply 2026',
    '"aluminum" LME price smelter curtailment 2026',
    '"steel" HRC price tariff impact 2026',
    '"lithium carbonate" price 2026',
    '"semiconductor" WSTS book-to-bill 2026',
    '"USD/CNY" OR "USD/JPY" move policy 2026',
    '"USD/EUR" OR "USD/GBP" move policy 2026',
    '"Baltic Dry Index" move 2026',
    '"LNG" spot price JKM Europe 2026',
    '"urea" fertilizer price 2026',
    '"cocoa" OR "coffee" price weather 2026',
    '"natural gas" TTF Henry Hub price 2026',
]


class _Client(Protocol):
    async def search(
        self, query: str, *, topic: str, days: int = 1
    ) -> list[dict[str, Any]]: ...


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
