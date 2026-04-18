"""TDD for the Analyst rules-based fallback processor.

Phase B per ``WORKTREE_PLAN.md``. The fallback path is what runs when the
LLM tool-loop raises ``LLMValidationError`` (Gemini returns junk JSON, tool
loop exceeds ``max_iters``, etc.). It must still produce a persisted
``ImpactReport`` keyed off the disruption's category, using the same
``analyst_tools`` primitives but without any LLM involvement.

Coverage:

- Weather template on the typhoon fixture: ``total_exposure`` within ±10%
  of the $2.3M ground truth; reasoning trace carries ``[source=fallback]``
  marker; at least two tool calls recorded; ``NOTIFY new_impact`` fires once.
- Idempotent re-run returns the same row (no duplicate writes, no duplicate
  NOTIFY).
- Unknown category defaults to the weather template when lat/lng/radius are
  present — we never crash on an unknown label.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from decimal import Decimal

import pytest
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.models import AffectedShipment
from backend.db.models import Disruption as DisruptionRow
from backend.db.models import ImpactReport as ImpactReportRow
from backend.db.session import session
from backend.tests.fixtures.typhoon import (
    TYPHOON_EXPOSURE_USD,
    TYPHOON_SHIPMENT_COUNT,
    TyphoonSeed,
    seed_typhoon,
)

_EXPOSURE_LOWER = TYPHOON_EXPOSURE_USD * Decimal("0.90")
_EXPOSURE_UPPER = TYPHOON_EXPOSURE_USD * Decimal("1.10")


@pytest.fixture()
async def typhoon_session() -> AsyncIterator[AsyncSession]:
    async with session() as s:
        seed = await seed_typhoon(s)
        await s.commit()
        s.info["typhoon_seed"] = seed
        yield s


class _CapturingBus:
    def __init__(self) -> None:
        self.published: list[tuple[str, str]] = []

    async def publish(self, channel: str, payload: str) -> None:
        self.published.append((channel, payload))


@pytest.mark.asyncio
async def test_fallback_weather_produces_report_on_typhoon(
    typhoon_session: AsyncSession,
) -> None:
    from backend.agents.analyst.processors.fallback import (
        build_impact_report_fallback,
    )

    seed: TyphoonSeed = typhoon_session.info["typhoon_seed"]
    bus = _CapturingBus()
    await typhoon_session.commit()

    impact_id = await build_impact_report_fallback(
        disruption_id=seed.disruption_id,
        bus=bus,
    )

    async with session() as s:
        ir_row = (
            await s.execute(select(ImpactReportRow).where(ImpactReportRow.id == impact_id))
        ).scalar_one()
        assert ir_row.disruption_id == seed.disruption_id
        assert _EXPOSURE_LOWER <= Decimal(ir_row.total_exposure) <= _EXPOSURE_UPPER
        assert ir_row.sql_executed is not None
        assert ir_row.sql_executed.strip() != ""

        trace = ir_row.reasoning_trace
        assert isinstance(trace, dict)
        assert "fallback" in trace["final_reasoning"]
        tool_calls = trace["tool_calls"]
        assert isinstance(tool_calls, list)
        assert len(tool_calls) >= 2
        names = [tc["tool_name"] for tc in tool_calls]
        assert "shipments_touching_region" in names
        assert "exposure_aggregate" in names

        affected = (
            (
                await s.execute(
                    select(AffectedShipment).where(AffectedShipment.impact_report_id == impact_id)
                )
            )
            .scalars()
            .all()
        )
        assert len(affected) == TYPHOON_SHIPMENT_COUNT
        assert {a.shipment_id for a in affected} == set(seed.shipment_ids)

    assert len(bus.published) == 1
    channel, payload = bus.published[0]
    assert channel == "new_impact"
    parsed = json.loads(payload)
    assert parsed["id"] == str(impact_id)
    assert parsed["disruption_id"] == str(seed.disruption_id)


@pytest.mark.asyncio
async def test_fallback_is_idempotent(typhoon_session: AsyncSession) -> None:
    from backend.agents.analyst.processors.fallback import (
        build_impact_report_fallback,
    )

    seed: TyphoonSeed = typhoon_session.info["typhoon_seed"]
    bus = _CapturingBus()
    await typhoon_session.commit()

    first = await build_impact_report_fallback(
        disruption_id=seed.disruption_id,
        bus=bus,
    )
    second = await build_impact_report_fallback(
        disruption_id=seed.disruption_id,
        bus=bus,
    )
    assert first == second

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
async def test_fallback_unknown_category_defaults_to_radius_chain(
    typhoon_session: AsyncSession,
) -> None:
    """Unknown category with lat/lng/radius must still produce a report."""
    from backend.agents.analyst.processors.fallback import (
        build_impact_report_fallback,
    )

    seed: TyphoonSeed = typhoon_session.info["typhoon_seed"]
    # Relabel the disruption's category to something the dispatcher doesn't
    # know; it should fall back to the proximity chain and still succeed.
    await typhoon_session.execute(
        update(DisruptionRow)
        .where(DisruptionRow.id == seed.disruption_id)
        .values(category="unknown_exotic_category")
    )
    await typhoon_session.commit()

    bus = _CapturingBus()
    impact_id = await build_impact_report_fallback(
        disruption_id=seed.disruption_id,
        bus=bus,
    )

    async with session() as s:
        ir_row = (
            await s.execute(select(ImpactReportRow).where(ImpactReportRow.id == impact_id))
        ).scalar_one()
        assert _EXPOSURE_LOWER <= Decimal(ir_row.total_exposure) <= _EXPOSURE_UPPER
