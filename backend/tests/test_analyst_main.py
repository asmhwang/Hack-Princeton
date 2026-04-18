"""Integration: ``AnalystAgent`` end-to-end on the typhoon fixture.

Per master plan §6.3 Step 2 + WORKTREE_PLAN.md Phase C.

Timeline:

1. Seed the typhoon scenario; commit.
2. Start an ``AnalystAgent`` whose ``LLMClient`` is stubbed to short-circuit
   the tool loop — we are not exercising Gemini here, only the Postgres
   LISTEN/NOTIFY wiring + persistence path.
3. Publish ``NOTIFY new_disruption, <uuid>`` via a second ``EventBus``.
4. Subscribe a separate bus to ``new_impact`` and assert the payload arrives
   within 30 seconds with the expected disruption-id / total-exposure shape.

A second test forces ``LLMValidationError`` from the stub LLM and asserts
the fallback path still writes a row + fires ``new_impact``. This is the
"Strategist must not stall" guarantee.
"""

from __future__ import annotations

import asyncio
import json
import uuid
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
from pydantic import BaseModel
from sqlalchemy import select

from backend.agents.analyst.config import AnalystSettings
from backend.agents.analyst.main import AnalystAgent
from backend.db.bus import EventBus
from backend.db.models import ImpactReport as ImpactReportRow
from backend.db.session import session
from backend.llm.client import LLMValidationError, Tool, ToolInvocation
from backend.schemas.impact import (
    AffectedShipmentEntry,
    ImpactReport,
    ReasoningTrace,
)
from backend.tests.fixtures.typhoon import (
    TYPHOON_EXPOSURE_USD,
    TYPHOON_SHIPMENT_COUNT,
    TyphoonSeed,
    seed_typhoon,
)

_WAIT_TIMEOUT_S = 30.0


# ---------------------------------------------------------------------------
# Stub LLM — test local, skips the real Gemini transport entirely
# ---------------------------------------------------------------------------


class _StubLLM:
    def __init__(
        self,
        final_report: ImpactReport,
        trace: list[ToolInvocation],
        *,
        raise_on_call: Exception | None = None,
    ) -> None:
        self._final = final_report
        self._trace = trace
        self._raise = raise_on_call

    async def with_tools(
        self,
        prompt: str,
        tools: list[Tool],
        *,
        final_schema: type[BaseModel],
        cache_key: str | None = None,
        max_iters: int = 6,
    ) -> tuple[BaseModel, list[ToolInvocation]]:
        if self._raise is not None:
            raise self._raise
        return self._final, list(self._trace)

    async def cached_context(self, key: str, content: str) -> str:
        return ""


def _mock_report(seed: TyphoonSeed) -> ImpactReport:
    affected = [
        AffectedShipmentEntry(
            shipment_id=sid,
            exposure=(TYPHOON_EXPOSURE_USD / Decimal(TYPHOON_SHIPMENT_COUNT)).quantize(
                Decimal("0.01")
            ),
            days_to_sla_breach=3,
        )
        for sid in seed.shipment_ids
    ]
    return ImpactReport(
        disruption_id=seed.disruption_id,
        total_exposure=TYPHOON_EXPOSURE_USD,
        units_at_risk=1000 * TYPHOON_SHIPMENT_COUNT,
        cascade_depth=3,
        sql_executed="<overwritten>",
        reasoning_trace=ReasoningTrace(
            tool_calls=[],
            final_reasoning="stubbed",
        ),
        affected_shipments=affected,
    )


def _mock_trace(seed: TyphoonSeed) -> list[ToolInvocation]:
    sql = "SELECT id FROM shipments WHERE origin_port_id IN ('PORT-SZX')"
    return [
        ToolInvocation(
            tool="shipments_touching_region",
            args={"radius_center": [22.5, 114.1], "radius_km": 400},
            result={
                "rows": [{"id": sid} for sid in seed.shipment_ids],
                "synthesized_sql": sql,
                "row_count": len(seed.shipment_ids),
            },
        ),
        ToolInvocation(
            tool="exposure_aggregate",
            args={"shipment_ids": seed.shipment_ids},
            result={
                "rows": [{"shipments": len(seed.shipment_ids), "total_revenue": "2300000"}],
                "synthesized_sql": ("SELECT COUNT(*) FROM shipments WHERE id IN ('SHP-T001')"),
                "row_count": 1,
            },
        ),
    ]


# ---------------------------------------------------------------------------
# new_impact watcher
# ---------------------------------------------------------------------------


class _NotifyWatcher:
    """Subscribes to a channel and signals when a matching payload arrives.

    Uses a dedicated ``EventBus`` because the Analyst agent already holds the
    LISTEN connection for ``new_disruption``; mixing channels on the same
    connection is fine, but the watcher owning its own bus keeps the test
    plumbing symmetric with production (separate agents → separate conns).

    Event-driven instead of polled so slow CI never flakes on poll cadence.
    """

    def __init__(self, dsn: str, channel: str) -> None:
        self._bus = EventBus(dsn)
        self._channel = channel
        self.payloads: list[str] = []
        self._arrived = asyncio.Event()

    async def start(self) -> None:
        await self._bus.start()
        await self._bus.subscribe(self._channel, self._on)

    async def stop(self) -> None:
        await self._bus.stop()

    async def _on(self, payload: str) -> None:
        self.payloads.append(payload)
        self._arrived.set()

    async def wait_for(self, predicate: Any, timeout_s: float) -> str | None:
        """Return the first payload for which ``predicate`` is true, or None on timeout."""
        loop = asyncio.get_running_loop()
        deadline = loop.time() + timeout_s
        seen = 0
        while True:
            while seen < len(self.payloads):
                p = self.payloads[seen]
                seen += 1
                try:
                    if predicate(p):
                        return p
                except (ValueError, TypeError, json.JSONDecodeError):
                    continue
            remaining = deadline - loop.time()
            if remaining <= 0:
                return None
            self._arrived.clear()
            try:
                await asyncio.wait_for(self._arrived.wait(), timeout=remaining)
            except TimeoutError:
                return None


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_notify_new_disruption_triggers_impact_report(
    postgresql_url: str, tmp_path: Path
) -> None:
    async with session() as s:
        seed = await seed_typhoon(s)
        await s.commit()

    settings = AnalystSettings(
        database_url=postgresql_url,
        state_path=tmp_path / "analyst-state.json",
        health_port=0,
        llm_cache_path=tmp_path / "analyst-llm.sqlite",
    )
    llm = _StubLLM(_mock_report(seed), _mock_trace(seed))
    agent = AnalystAgent(settings=settings, llm=llm)
    await agent.start()

    watcher = _NotifyWatcher(postgresql_url, "new_impact")
    await watcher.start()

    publisher = EventBus(postgresql_url)
    await publisher.start()
    try:
        await publisher.publish("new_disruption", str(seed.disruption_id))

        payload = await watcher.wait_for(
            lambda p: json.loads(p).get("disruption_id") == str(seed.disruption_id),
            timeout_s=_WAIT_TIMEOUT_S,
        )
    finally:
        await publisher.stop()
        await watcher.stop()
        await agent.stop()

    assert payload is not None, "new_impact NOTIFY did not arrive within 30s"
    parsed = json.loads(payload)
    assert parsed["disruption_id"] == str(seed.disruption_id)
    assert Decimal(parsed["total_exposure"]) == TYPHOON_EXPOSURE_USD

    async with session() as s:
        row = (
            await s.execute(
                select(ImpactReportRow).where(ImpactReportRow.disruption_id == seed.disruption_id)
            )
        ).scalar_one()
        assert row.sql_executed is not None and row.sql_executed.strip() != ""


@pytest.mark.asyncio
async def test_llm_failure_falls_back_to_rules_path(postgresql_url: str, tmp_path: Path) -> None:
    async with session() as s:
        seed = await seed_typhoon(s)
        await s.commit()

    settings = AnalystSettings(
        database_url=postgresql_url,
        state_path=tmp_path / "analyst-state.json",
        health_port=0,
        llm_cache_path=tmp_path / "analyst-llm.sqlite",
    )
    llm = _StubLLM(
        _mock_report(seed),
        _mock_trace(seed),
        raise_on_call=LLMValidationError("forced for test"),
    )
    agent = AnalystAgent(settings=settings, llm=llm)
    await agent.start()

    watcher = _NotifyWatcher(postgresql_url, "new_impact")
    await watcher.start()

    publisher = EventBus(postgresql_url)
    await publisher.start()
    try:
        await publisher.publish("new_disruption", str(seed.disruption_id))
        payload = await watcher.wait_for(
            lambda p: json.loads(p).get("disruption_id") == str(seed.disruption_id),
            timeout_s=_WAIT_TIMEOUT_S,
        )
    finally:
        await publisher.stop()
        await watcher.stop()
        await agent.stop()

    assert payload is not None, "fallback path must still emit new_impact"
    parsed = json.loads(payload)
    assert parsed["disruption_id"] == str(seed.disruption_id)

    async with session() as s:
        row = (
            await s.execute(
                select(ImpactReportRow).where(ImpactReportRow.disruption_id == seed.disruption_id)
            )
        ).scalar_one()
        trace = row.reasoning_trace
        assert isinstance(trace, dict)
        assert "fallback" in trace["final_reasoning"]


@pytest.mark.asyncio
async def test_invalid_payload_does_not_crash_agent(postgresql_url: str, tmp_path: Path) -> None:
    """Bogus NOTIFY body must be logged-and-dropped, not propagate."""
    settings = AnalystSettings(
        database_url=postgresql_url,
        state_path=tmp_path / "analyst-state.json",
        health_port=0,
        llm_cache_path=tmp_path / "analyst-llm.sqlite",
    )
    dummy_seed = TyphoonSeed(
        disruption_id=uuid.uuid4(),
        shipment_ids=["SHP-DUMMY"],
        po_ids=["PO-DUMMY"],
        total_exposure=Decimal("0"),
        centroid=(0.0, 0.0),
        radius_km=Decimal("0"),
    )
    llm = _StubLLM(_mock_report(dummy_seed), [])
    agent = AnalystAgent(settings=settings, llm=llm)
    await agent.start()

    publisher = EventBus(postgresql_url)
    await publisher.start()
    try:
        await publisher.publish("new_disruption", "not-a-uuid")
        # allow the dispatcher to run; agent must survive
        for _ in range(10):
            await asyncio.sleep(0.05)
    finally:
        await publisher.stop()
        await agent.stop()
