"""Policy source loop — Tavily ``topic=general`` every 15 minutes.

Queries are the 20 tuned policy searches from ``tavily_queries.md``. Policy
signals skew toward slower-moving regulatory action, so the cadence is
deliberately longer than news.
"""

from __future__ import annotations

from typing import Any, Literal, Protocol

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from backend.agents.scout.sources.pipeline import ingest_tavily_result
from backend.llm.client import LLMClient

log = structlog.get_logger()

SOURCE_CATEGORY: Literal["policy"] = "policy"
SOURCE_NAME = "tavily.policy"
CADENCE_SECONDS = 900
TOPIC = "general"
DAYS = 2

QUERIES: list[str] = [
    '"USTR" ("Section 301" OR tariff) determination 2026',
    '"Section 232" national security tariff 2026',
    '"OFAC" sanctions designation (entity OR vessel OR port) 2026',
    '"EU" "Carbon Border Adjustment Mechanism" CBAM 2026',
    '"export control" semiconductor advanced node 2026',
    '"Forced Labor" "Withhold Release Order" CBP 2026',
    '"customs" inspection intensified region 2026',
    '"export ban" food commodity country 2026',
    '"trade agreement" ratified signed 2026',
    '"anti-dumping duty" product country 2026',
    '"FDA" import alert 2026',
    '"USDA" APHIS import suspension country 2026',
    '"IMO" emissions regulation shipping compliance 2026',
    '"OECD" critical minerals policy 2026',
    '"UK" trade sanctions designation 2026',
    '"Japan" METI export license controls 2026',
    '"China" MOFCOM export license rare earths 2026',
    '"India" DGFT export notification 2026',
    '"Brazil" tariff change industry 2026',
    '"WTO" dispute ruling tariff 2026',
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
