"""Integration test for the Strategist agent end-to-end on the typhoon fixture.

Per master plan §7.4 Step 2:

1. Seed typhoon + an ``impact_reports`` row (the Strategist subscribes
   downstream of the Analyst — we bypass the Analyst here).
2. Start ``StrategistAgent`` with a stubbed LLM (no real Gemini).
3. Publish ``NOTIFY new_impact, <json>`` via a second ``EventBus``.
4. Subscribe a watcher to ``new_mitigation``; assert it fires with the
   mitigation ids and that the DB reflects ≥2 options + 3×options drafts.
"""

from __future__ import annotations

import asyncio
import json
import uuid
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from backend.agents.strategist.config import StrategistSettings
from backend.agents.strategist.main import StrategistAgent
from backend.db.bus import EventBus
from backend.db.models import (
    AffectedShipment,
)
from backend.db.models import (
    DraftCommunication as DraftCommunicationRow,
)
from backend.db.models import (
    ImpactReport as ImpactReportRow,
)
from backend.db.models import (
    MitigationOption as MitigationOptionRow,
)
from backend.db.session import session
from backend.llm.client import Tool, ToolInvocation
from backend.schemas.mitigation import (
    DraftCommunication,
    DraftCommunicationBundle,
    MitigationOption,
    MitigationOptionsBundle,
)
from backend.tests.fixtures.typhoon import (
    TYPHOON_EXPOSURE_USD,
    TYPHOON_SHIPMENT_COUNT,
    TyphoonSeed,
    seed_typhoon,
)

_WAIT_TIMEOUT_S = 30.0
_POLL_INTERVAL_S = 0.25


# ---------------------------------------------------------------------------
# Stubs
# ---------------------------------------------------------------------------


class _StubLLM:
    def __init__(
        self,
        bundle: MitigationOptionsBundle,
        drafts: DraftCommunicationBundle,
    ) -> None:
        self._bundle = bundle
        self._drafts = drafts

    async def with_tools(
        self,
        prompt: str,
        tools: list[Tool],
        *,
        final_schema: type[BaseModel],
        cache_key: str | None = None,
        max_iters: int = 6,
    ) -> tuple[BaseModel, list[ToolInvocation]]:
        assert final_schema is MitigationOptionsBundle
        return self._bundle, []

    async def structured(
        self,
        prompt: str,
        schema: type[BaseModel],
        *,
        cache_key: str | None = None,
    ) -> BaseModel:
        assert schema is DraftCommunicationBundle
        return self._drafts

    async def cached_context(self, key: str, content: str) -> str:
        return ""


def _options_bundle() -> MitigationOptionsBundle:
    return MitigationOptionsBundle(
        options=[
            MitigationOption(
                option_type="reroute",
                description="Shift origin port to PORT-NGB; 13 shipments re-lane.",
                delta_cost=Decimal("42000.00"),
                delta_days=2,
                confidence=0.78,
                rationale=(
                    "Typhoon berth closure at SZX confirmed; PORT-NGB at 1250km "
                    "feasible for all 13 shipments."
                ),
            ),
            MitigationOption(
                option_type="alternate_supplier",
                description="Second-source SUP-ELE-214 for SKU-TYPHOON-MCU.",
                delta_cost=Decimal("138000.00"),
                delta_days=7,
                confidence=0.64,
                rationale=(
                    "alternate_suppliers_for_sku surfaced 3 candidates with "
                    "acceptable reliability scores for second-sourcing."
                ),
            ),
        ]
    )


def _drafts_bundle() -> DraftCommunicationBundle:
    return DraftCommunicationBundle(
        supplier=DraftCommunication(
            recipient_type="supplier",
            recipient_contact="ops@sup.example",
            subject="Alternate routing required",
            body="Please confirm capacity at PORT-NGB for 13 containers within 24h.",
        ),
        customer=DraftCommunication(
            recipient_type="customer",
            recipient_contact="ops@cust.example",
            subject="Shipment ETA update",
            body="We are adjusting the route; new ETA is 2026-04-28.",
        ),
        internal=DraftCommunication(
            recipient_type="internal",
            recipient_contact="ops@suppl.ai",
            subject="Mitigation pending: reroute",
            body="- Option: reroute\n- Cost: $42,000\n- Owner: duty Strategist",
        ),
    )


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

    async def wait_for(self, predicate, timeout_s: float) -> str | None:  # type: ignore[no-untyped-def]
        deadline = asyncio.get_event_loop().time() + timeout_s
        while asyncio.get_event_loop().time() < deadline:
            for p in self.payloads:
                try:
                    if predicate(p):
                        return p
                except (ValueError, TypeError, json.JSONDecodeError):
                    continue
            await asyncio.sleep(_POLL_INTERVAL_S)
        return None


async def _seed_impact(seed: TyphoonSeed) -> uuid.UUID:
    """Create an impact report + affected_shipments rows for the typhoon seed."""
    impact_id = uuid.uuid4()
    per_shipment = (TYPHOON_EXPOSURE_USD / Decimal(TYPHOON_SHIPMENT_COUNT)).quantize(
        Decimal("0.01")
    )
    async with session() as s:
        s.add(
            ImpactReportRow(
                id=impact_id,
                disruption_id=seed.disruption_id,
                total_exposure=TYPHOON_EXPOSURE_USD,
                units_at_risk=TYPHOON_SHIPMENT_COUNT * 1000,
                cascade_depth=3,
                sql_executed="SELECT 1",
                reasoning_trace={"tool_calls": [], "final_reasoning": "fx"},
            )
        )
        await s.flush()
        rows = [
            {
                "impact_report_id": impact_id,
                "shipment_id": sid,
                "exposure": per_shipment,
                "days_to_sla_breach": 4,
            }
            for sid in seed.shipment_ids
        ]
        await s.execute(
            pg_insert(AffectedShipment)
            .values(rows)
            .on_conflict_do_nothing(index_elements=["impact_report_id", "shipment_id"])
        )
        await s.commit()
    return impact_id


# ---------------------------------------------------------------------------
# Test
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_strategist_processes_new_impact_end_to_end(
    postgresql_url: str, tmp_path: Path
) -> None:
    async with session() as s:
        seed = await seed_typhoon(s)
        await s.commit()
    impact_id = await _seed_impact(seed)

    settings = StrategistSettings(
        database_url=postgresql_url,
        state_path=tmp_path / "strategist-state.json",
        health_port=0,
        llm_cache_path=tmp_path / "strategist-llm.sqlite",
    )
    llm = _StubLLM(_options_bundle(), _drafts_bundle())
    agent = StrategistAgent(settings=settings, llm=llm)
    await agent.start()

    watcher = _NotifyWatcher(postgresql_url, "new_mitigation")
    await watcher.start()

    publisher = EventBus(postgresql_url)
    await publisher.start()
    notify_payload = json.dumps(
        {
            "id": str(impact_id),
            "disruption_id": str(seed.disruption_id),
            "total_exposure": str(TYPHOON_EXPOSURE_USD),
        }
    )
    try:
        await publisher.publish("new_impact", notify_payload)
        arrived = await watcher.wait_for(
            lambda p: json.loads(p).get("impact_report_id") == str(impact_id),
            timeout_s=_WAIT_TIMEOUT_S,
        )
    finally:
        await publisher.stop()
        await watcher.stop()
        await agent.stop()

    assert arrived is not None, "new_mitigation NOTIFY did not arrive within 30s"
    parsed = json.loads(arrived)
    assert parsed["impact_report_id"] == str(impact_id)
    assert len(parsed["mitigation_ids"]) == 2

    async with session() as s:
        options = (
            (
                await s.execute(
                    select(MitigationOptionRow).where(
                        MitigationOptionRow.impact_report_id == impact_id
                    )
                )
            )
            .scalars()
            .all()
        )
        assert len(options) == 2

        drafts = (
            (
                await s.execute(
                    select(DraftCommunicationRow).where(
                        DraftCommunicationRow.mitigation_id.in_([o.id for o in options])
                    )
                )
            )
            .scalars()
            .all()
        )
        # 3 drafts per option × 2 options = 6
        assert len(drafts) == 6
        for draft in drafts:
            assert draft.sent_at is None
