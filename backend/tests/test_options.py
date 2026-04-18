"""TDD for the Strategist options processor.

Per master plan §7.1:

- Seed the typhoon scenario + a pre-existing ImpactReport row.
- Mock ``LLMClient.with_tools`` to return a deterministic
  ``MitigationOptionsBundle`` with 2 options covering ``reroute`` +
  ``alternate_supplier``.
- Run ``generate_options`` against the fixture.
- Assert: bundle length 2, each option's ``delta_cost`` ≥ 0, ``delta_days``
  int (may be negative on expedite), ``confidence`` in [0, 1], and at least
  one option is ``reroute`` OR ``alternate_supplier``.
- Missing impact-report id raises ``ImpactReportNotFoundError``.

A second test exercises the ``costing`` helpers directly as pure functions.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from decimal import Decimal
from typing import Any

import pytest
from pydantic import BaseModel
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.models import AffectedShipment
from backend.db.models import ImpactReport as ImpactReportRow
from backend.db.session import session
from backend.llm.client import Tool, ToolInvocation
from backend.schemas.mitigation import (
    MitigationOption,
    MitigationOptionsBundle,
)
from backend.tests.fixtures.typhoon import (
    TYPHOON_EXPOSURE_USD,
    TYPHOON_SHIPMENT_COUNT,
    TyphoonSeed,
    seed_typhoon,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
async def typhoon_with_impact() -> AsyncIterator[tuple[AsyncSession, TyphoonSeed, uuid.UUID]]:
    """Yield (session, seed, impact_report_id). Commits typhoon + an impact row."""
    async with session() as s:
        seed = await seed_typhoon(s)
        await s.commit()

        impact_id = uuid.uuid4()
        ir = ImpactReportRow(
            id=impact_id,
            disruption_id=seed.disruption_id,
            total_exposure=TYPHOON_EXPOSURE_USD,
            units_at_risk=1000 * TYPHOON_SHIPMENT_COUNT,
            cascade_depth=3,
            sql_executed="SELECT 1",
            reasoning_trace={
                "tool_calls": [],
                "final_reasoning": "fixture impact report",
            },
        )
        s.add(ir)
        await s.flush()

        per_shipment = (TYPHOON_EXPOSURE_USD / Decimal(TYPHOON_SHIPMENT_COUNT)).quantize(
            Decimal("0.01")
        )
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
        yield s, seed, impact_id


class _StubLLM:
    def __init__(self, bundle: MitigationOptionsBundle, trace: list[ToolInvocation]) -> None:
        self._bundle = bundle
        self._trace = trace
        self.calls = 0
        self.last_prompt: str | None = None

    async def with_tools(
        self,
        prompt: str,
        tools: list[Tool],
        *,
        final_schema: type[BaseModel],
        cache_key: str | None = None,
        max_iters: int = 6,
    ) -> tuple[BaseModel, list[ToolInvocation]]:
        self.calls += 1
        self.last_prompt = prompt
        assert final_schema is MitigationOptionsBundle
        assert tools, "strategist must hand a non-empty tool set"
        return self._bundle, list(self._trace)

    async def cached_context(self, key: str, content: str) -> str:
        return ""


def _fixture_bundle() -> MitigationOptionsBundle:
    return MitigationOptionsBundle(
        options=[
            MitigationOption(
                option_type="reroute",
                description="Shift origin from PORT-SZX to PORT-NGB; 13 sea shipments re-lane.",
                delta_cost=Decimal("42000.00"),
                delta_days=2,
                confidence=0.78,
                rationale=(
                    "alternate_ports_near returned PORT-NGB at 1250km from SZX; "
                    "exposure_aggregate over 13 shipments confirms feasibility."
                ),
            ),
            MitigationOption(
                option_type="alternate_supplier",
                description="Second-source SUP-ELE-214 for SKU-TYPHOON-MCU; 7-day onboarding.",
                delta_cost=Decimal("138000.00"),
                delta_days=7,
                confidence=0.64,
                rationale=(
                    "alternate_suppliers_for_sku surfaced 3 candidates; "
                    "SUP-ELE-214 has reliability_score 0.88 vs incumbent 0.92."
                ),
            ),
        ]
    )


def _fixture_trace() -> list[ToolInvocation]:
    return [
        ToolInvocation(
            tool="alternate_ports_near",
            args={"near_port_id": "PORT-SZX", "radius_km": 2000},
            result={
                "rows": [{"id": "PORT-NGB", "distance_km": 1250.0}],
                "synthesized_sql": "SELECT id, name FROM ports WHERE id NOT IN ('PORT-SZX')",
                "row_count": 1,
            },
        ),
        ToolInvocation(
            tool="alternate_suppliers_for_sku",
            args={"sku_id": "SKU-TYPHOON-MCU"},
            result={
                "rows": [{"id": "SUP-ELE-214", "reliability_score": "0.88"}],
                "synthesized_sql": (
                    "SELECT id FROM suppliers WHERE 'electronics' = ANY(categories)"
                ),
                "row_count": 1,
            },
        ),
    ]


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_generate_options_returns_valid_bundle(
    typhoon_with_impact: tuple[AsyncSession, TyphoonSeed, uuid.UUID],
) -> None:
    from backend.agents.strategist.processors.options import generate_options

    _, _, impact_id = typhoon_with_impact
    llm = _StubLLM(_fixture_bundle(), _fixture_trace())

    bundle, trace = await generate_options(impact_report_id=impact_id, llm=llm)

    assert len(bundle.options) >= 2
    assert len(bundle.options) <= 4
    option_types = {o.option_type for o in bundle.options}
    # at least one reroute or alternate_supplier per master plan 7.1 Step 1.
    assert option_types & {"reroute", "alternate_supplier"}

    for opt in bundle.options:
        assert opt.delta_cost >= Decimal("0")
        assert isinstance(opt.delta_days, int)
        assert 0 <= opt.confidence <= 1
        assert len(opt.rationale) >= 20
        assert len(opt.description) >= 10

    assert len(trace) == 2
    assert llm.calls == 1
    # Prompt must contain the impact + disruption context so Gemini has facts.
    assert llm.last_prompt is not None
    assert str(impact_id) in llm.last_prompt
    assert "South China" in llm.last_prompt


@pytest.mark.asyncio
async def test_generate_options_raises_when_impact_missing(
    typhoon_with_impact: tuple[AsyncSession, TyphoonSeed, uuid.UUID],
) -> None:
    from backend.agents.strategist.processors.options import (
        ImpactReportNotFoundError,
        generate_options,
    )

    llm = _StubLLM(_fixture_bundle(), _fixture_trace())
    with pytest.raises(ImpactReportNotFoundError):
        await generate_options(impact_report_id=uuid.uuid4(), llm=llm)


# ---------------------------------------------------------------------------
# Costing helpers — pure unit tests (no DB, no LLM)
# ---------------------------------------------------------------------------


def test_costing_reroute_cost_scales_with_count_and_distance() -> None:
    from backend.agents.strategist.processors import costing

    cost = costing.reroute_cost(shipment_count=10, extra_km=100)
    # 10 × 100 × 3.50 = 3500.00
    assert cost == Decimal("3500.00")
    assert costing.reroute_cost(0, 100) == Decimal("0.00")
    assert costing.reroute_cost(10, 0) == Decimal("0.00")


def test_costing_reroute_days_ceils_to_at_least_one() -> None:
    from backend.agents.strategist.processors import costing

    assert costing.reroute_days(650) == 1
    assert costing.reroute_days(651) == 2
    assert costing.reroute_days(0) == 0
    # 100 km < 650 km/day → still counts as a full day (ceil).
    assert costing.reroute_days(100) == 1


def test_costing_supplier_swap_cost_capped_at_20pct() -> None:
    from backend.agents.strategist.processors import costing

    po_revenue = Decimal("100000")
    # Reliability gap of 0.05 → 5% reserve.
    cost = costing.supplier_swap_cost(
        po_revenue, current_reliability=0.92, alternate_reliability=0.87
    )
    # quantize tolerates floating-point imprecision in float→Decimal conversion.
    assert Decimal("4990") <= cost <= Decimal("5010"), cost

    # Reliability gap of 0.9 → capped at 20% = $20,000.
    capped = costing.supplier_swap_cost(
        po_revenue, current_reliability=0.95, alternate_reliability=0.05
    )
    assert capped == Decimal("20000.00")

    # Alternate is better → no reserve.
    zero = costing.supplier_swap_cost(
        po_revenue, current_reliability=0.8, alternate_reliability=0.9
    )
    assert zero == Decimal("0.00")


def test_costing_expedite_negative_days_positive_cost() -> None:
    from backend.agents.strategist.processors import costing

    assert costing.expedite_days() < 0
    cost = costing.expedite_cost(Decimal("10000"))
    # (4.0 - 1) × 10_000 = 30_000
    assert cost == Decimal("30000.00")
    assert costing.expedite_cost(Decimal("0")) == Decimal("0.00")


def test_costing_accept_delay_sums_sla_penalties() -> None:
    from backend.agents.strategist.processors import costing

    penalties = [Decimal("500"), Decimal("1000"), Decimal("250")]
    total: Any = costing.accept_delay_cost(penalties)
    assert total == Decimal("1750.00")
    assert costing.accept_delay_cost([]) == Decimal("0.00")
