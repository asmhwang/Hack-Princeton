"""TDD for the Analyst impact processor.

Per master plan §6.1 Step 2 + WORKTREE_PLAN.md Phase A:

- Seed the typhoon scenario (13 shipments around Shenzhen, $2.3M PO revenue).
- Mock ``LLMClient.with_tools`` to return a deterministic ``ImpactReport`` plus
  a 4-entry reasoning trace whose tool names line up with the canonical chain
  (``shipments_touching_region`` → ``purchase_orders_for_skus`` →
  ``customers_by_po`` → ``exposure_aggregate``).
- Run ``build_impact_report`` against a real ``AsyncSession`` + a fake event
  bus that captures NOTIFY payloads.
- Assert: row persisted, ``total_exposure`` within ±10% of $2.3M,
  ``reasoning_trace.tool_calls`` length == 4, all 13 ``affected_shipments``
  upserted, ``NOTIFY new_impact`` emitted exactly once after the transaction.
"""

from __future__ import annotations

import json
import uuid
from collections.abc import AsyncIterator
from decimal import Decimal
from typing import Any

import pytest
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.models import AffectedShipment
from backend.db.models import ImpactReport as ImpactReportRow
from backend.db.session import session
from backend.llm.client import Tool, ToolInvocation
from backend.schemas.impact import (
    AffectedShipmentEntry,
    ImpactReport,
    ReasoningTrace,
)
from backend.schemas.impact import ToolInvocation as SchemaToolInvocation
from backend.tests.fixtures.typhoon import (
    TYPHOON_EXPOSURE_USD,
    TYPHOON_SHIPMENT_COUNT,
    TyphoonSeed,
    seed_typhoon,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_EXPOSURE_LOWER = TYPHOON_EXPOSURE_USD * Decimal("0.90")
_EXPOSURE_UPPER = TYPHOON_EXPOSURE_USD * Decimal("1.10")
_EXPECTED_TOOL_CALL_COUNT = 4
_EXPECTED_CASCADE_DEPTH = 3


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
async def typhoon_session() -> AsyncIterator[AsyncSession]:
    """Yield a session with the typhoon scenario committed."""
    async with session() as s:
        seed = await seed_typhoon(s)
        await s.commit()
        s.info["typhoon_seed"] = seed  # hand-off so tests reuse UUIDs
        yield s


class _CapturingBus:
    """Minimal ``EventBus`` stand-in that records publishes."""

    def __init__(self) -> None:
        self.published: list[tuple[str, str]] = []

    async def publish(self, channel: str, payload: str) -> None:
        self.published.append((channel, payload))


class _StubLLM:
    """Stands in for ``LLMClient``; only ``with_tools`` is exercised here."""

    def __init__(
        self,
        final_report: ImpactReport,
        trace: list[ToolInvocation],
    ) -> None:
        self._final_report = final_report
        self._trace = trace
        self.call_count = 0

    async def with_tools(
        self,
        prompt: str,
        tools: list[Tool],
        *,
        final_schema: type[BaseModel],
        cache_key: str | None = None,
        max_iters: int = 6,
    ) -> tuple[BaseModel, list[ToolInvocation]]:
        self.call_count += 1
        assert final_schema is ImpactReport, "Analyst must request ImpactReport"
        assert tools, "tool set must not be empty"
        return self._final_report, list(self._trace)

    async def cached_context(self, key: str, content: str) -> str:
        return ""


def _build_mock_report(seed: TyphoonSeed) -> ImpactReport:
    """Fabricate the ImpactReport the (mocked) LLM would return."""
    affected = [
        AffectedShipmentEntry(
            shipment_id=shp_id,
            exposure=(seed.total_exposure / Decimal(TYPHOON_SHIPMENT_COUNT)).quantize(
                Decimal("0.01")
            ),
            days_to_sla_breach=4,
        )
        for shp_id in seed.shipment_ids
    ]
    return ImpactReport(
        disruption_id=seed.disruption_id,
        total_exposure=seed.total_exposure,
        units_at_risk=sum(1000 * i for i in range(1, TYPHOON_SHIPMENT_COUNT + 1)),
        cascade_depth=_EXPECTED_CASCADE_DEPTH,
        sql_executed="<overwritten-by-impl>",
        reasoning_trace=ReasoningTrace(
            tool_calls=[],  # impl rewrites this from llm trace
            final_reasoning="Typhoon Haikui closes SZX/HKG; 13 in_transit shipments exposed.",
        ),
        affected_shipments=affected,
    )


def _build_mock_trace(seed: TyphoonSeed) -> list[ToolInvocation]:
    """Fabricate a 4-step canonical tool chain matching prompt guidance."""
    shipments_result: dict[str, Any] = {
        "rows": [{"id": sid, "origin_port_id": "PORT-SZX"} for sid in seed.shipment_ids],
        "synthesized_sql": (
            "SELECT id, po_id, origin_port_id, status FROM shipments "
            "WHERE origin_port_id IN ('PORT-SZX', 'PORT-HKG') "
            "AND status IN ('in_transit', 'planned')"
        ),
        "row_count": len(seed.shipment_ids),
    }
    pos_result: dict[str, Any] = {
        "rows": [{"id": pid, "sku_id": "SKU-TYPHOON-MCU"} for pid in seed.po_ids],
        "synthesized_sql": (
            "SELECT id, customer_id, sku_id, revenue FROM purchase_orders "
            "WHERE sku_id IN ('SKU-TYPHOON-MCU')"
        ),
        "row_count": len(seed.po_ids),
    }
    customers_result: dict[str, Any] = {
        "rows": [
            {"id": "CUST-TYPHOON-A", "tier": "gold"},
            {"id": "CUST-TYPHOON-B", "tier": "silver"},
        ],
        "synthesized_sql": (
            "SELECT DISTINCT c.id, c.tier FROM customers c "
            "JOIN purchase_orders po ON c.id = po.customer_id "
            "WHERE po.id IN ('PO-T001', 'PO-T002')"
        ),
        "row_count": 2,
    }
    exposure_result: dict[str, Any] = {
        "rows": [
            {
                "shipments": len(seed.shipment_ids),
                "total_revenue": str(seed.total_exposure),
            }
        ],
        "synthesized_sql": (
            "SELECT COUNT(*) AS shipments, SUM(po.revenue) AS total_revenue "
            "FROM shipments s JOIN purchase_orders po ON s.po_id = po.id "
            "WHERE s.id IN ('SHP-T001')"
        ),
        "row_count": 1,
    }
    return [
        ToolInvocation(
            tool="shipments_touching_region",
            args={"radius_center": [22.5, 114.1], "radius_km": 400},
            result=shipments_result,
        ),
        ToolInvocation(
            tool="purchase_orders_for_skus",
            args={"sku_ids": ["SKU-TYPHOON-MCU"]},
            result=pos_result,
        ),
        ToolInvocation(
            tool="customers_by_po",
            args={"po_ids": seed.po_ids[:2]},
            result=customers_result,
        ),
        ToolInvocation(
            tool="exposure_aggregate",
            args={"shipment_ids": seed.shipment_ids},
            result=exposure_result,
        ),
    ]


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_build_impact_report_persists_row_and_emits_notify(
    typhoon_session: AsyncSession,
) -> None:
    from backend.agents.analyst.processors.impact import build_impact_report

    seed: TyphoonSeed = typhoon_session.info["typhoon_seed"]
    mock_report = _build_mock_report(seed)
    mock_trace = _build_mock_trace(seed)
    bus = _CapturingBus()
    llm = _StubLLM(final_report=mock_report, trace=mock_trace)

    # Commit a fresh session — build_impact_report opens its own.
    await typhoon_session.commit()

    impact_id = await build_impact_report(
        disruption_id=seed.disruption_id,
        llm=llm,
        bus=bus,
    )

    # Row persisted
    async with session() as s:
        ir_row = (
            await s.execute(select(ImpactReportRow).where(ImpactReportRow.id == impact_id))
        ).scalar_one()
        assert ir_row.disruption_id == seed.disruption_id
        assert _EXPOSURE_LOWER <= Decimal(ir_row.total_exposure) <= _EXPOSURE_UPPER
        assert ir_row.sql_executed is not None and ir_row.sql_executed.strip() != ""

        trace_json = ir_row.reasoning_trace
        assert isinstance(trace_json, dict)
        tool_calls = trace_json.get("tool_calls")
        assert isinstance(tool_calls, list)
        assert len(tool_calls) == _EXPECTED_TOOL_CALL_COUNT
        names = [tc["tool_name"] for tc in tool_calls]
        assert names == [
            "shipments_touching_region",
            "purchase_orders_for_skus",
            "customers_by_po",
            "exposure_aggregate",
        ]
        # Each persisted tool-call entry matches the ToolInvocation schema.
        for tc in tool_calls:
            SchemaToolInvocation.model_validate(tc)

        # All 13 affected_shipments upserted
        affected_rows = (
            (
                await s.execute(
                    select(AffectedShipment).where(AffectedShipment.impact_report_id == impact_id)
                )
            )
            .scalars()
            .all()
        )
        assert len(affected_rows) == TYPHOON_SHIPMENT_COUNT
        assert {a.shipment_id for a in affected_rows} == set(seed.shipment_ids)

    # NOTIFY new_impact emitted exactly once, payload well-formed
    assert len(bus.published) == 1
    channel, payload = bus.published[0]
    assert channel == "new_impact"
    parsed = json.loads(payload)
    assert parsed["id"] == str(impact_id)
    assert parsed["disruption_id"] == str(seed.disruption_id)
    assert Decimal(parsed["total_exposure"]) == seed.total_exposure

    assert llm.call_count == 1


@pytest.mark.asyncio
async def test_build_impact_report_is_idempotent_on_rerun(
    typhoon_session: AsyncSession,
) -> None:
    """Second invocation for the same disruption must not write a duplicate row."""
    from backend.agents.analyst.processors.impact import build_impact_report

    seed: TyphoonSeed = typhoon_session.info["typhoon_seed"]
    bus = _CapturingBus()
    llm = _StubLLM(_build_mock_report(seed), _build_mock_trace(seed))
    await typhoon_session.commit()

    first = await build_impact_report(
        disruption_id=seed.disruption_id,
        llm=llm,
        bus=bus,
    )
    second = await build_impact_report(
        disruption_id=seed.disruption_id,
        llm=llm,
        bus=bus,
    )

    assert first == second, "second run must return the existing impact_report id"

    async with session() as s:
        rows = (
            (
                await s.execute(
                    select(ImpactReportRow).where(
                        ImpactReportRow.disruption_id == seed.disruption_id
                    )
                )
            )
            .scalars()
            .all()
        )
        assert len(rows) == 1


@pytest.mark.asyncio
async def test_build_impact_report_missing_disruption_raises(
    typhoon_session: AsyncSession,
) -> None:
    from backend.agents.analyst.processors.impact import (
        DisruptionNotFoundError,
        build_impact_report,
    )

    bus = _CapturingBus()
    llm = _StubLLM(
        _build_mock_report(typhoon_session.info["typhoon_seed"]),
        _build_mock_trace(typhoon_session.info["typhoon_seed"]),
    )
    await typhoon_session.commit()

    with pytest.raises(DisruptionNotFoundError):
        await build_impact_report(
            disruption_id=uuid.uuid4(),
            llm=llm,
            bus=bus,
        )
    assert bus.published == [], "no NOTIFY must fire when disruption missing"
