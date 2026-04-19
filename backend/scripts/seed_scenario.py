"""Deterministic, LLM-free seed for the 5 canonical demo scenarios.

For each scenario id, inserts the full cascade:

    prime_chain → Signal(s) → Disruption → ImpactReport (+ reasoning trace)
      → AffectedShipments → MitigationOption(s) → DraftCommunication(s)
      → AgentLog cascade timeline

This is the failsafe path: if live agents fail on stage, we can still
navigate /disruption/<id> and every section renders real data.

All inserts use ON CONFLICT DO NOTHING so re-runs are safe. UUIDs are
freshly generated each run — two runs produce two distinct disruption
rows for the same scenario (by design, so you can test the empty-state
cascade multiple times).

Usage:
    uv run python -m backend.scripts.seed_scenario --scenario typhoon_kaia
    uv run python -m backend.scripts.seed_scenario --all
    uv run python -m backend.scripts.seed_scenario --all --status resolved
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import sys
import uuid
from datetime import UTC, datetime, timedelta
from typing import Literal

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from backend.db.session import DBSettings
from backend.scripts.scenarios import SCENARIOS
from backend.scripts.scenarios.demo_fixtures import ACTIVE_SCENARIO_FIXTURES
from backend.scripts.scenarios.prime_chain import seed_prime_chain
from backend.scripts.seed_helpers import (
    insert_affected_shipments,
    insert_disruption,
    insert_draft,
    insert_impact_report,
    insert_mitigation,
    insert_signal,
    seed_cascade_agent_logs,
)

Status = Literal["active", "resolved"]


async def seed_one_scenario(
    s: AsyncSession,
    scenario_id: str,
    status: Status,
) -> uuid.UUID:
    """Seed a single scenario end-to-end. Returns the disruption_id."""
    if scenario_id not in SCENARIOS:
        raise ValueError(f"Unknown scenario {scenario_id!r}. Known: {sorted(SCENARIOS)}")
    if scenario_id not in ACTIVE_SCENARIO_FIXTURES:
        raise ValueError(
            f"No demo fixture for scenario {scenario_id!r}. "
            f"Update backend/scripts/scenarios/demo_fixtures.py."
        )

    scenario = SCENARIOS[scenario_id]
    fx = ACTIVE_SCENARIO_FIXTURES[scenario_id]
    disruption = scenario.disruption

    # 1. Prime chain (Port/Supplier/SKU/Customer/POs/Shipments).
    await seed_prime_chain(s, scenario)

    # 2. IDs + timestamps.
    disruption_id = uuid.uuid4()
    trace_id = uuid.uuid4()
    now = datetime.now(UTC).replace(tzinfo=None)
    disruption_first_seen = now - timedelta(
        hours=max(sig.hours_before_disruption for sig in fx.signals)
    )

    # 3. Signals (one per fixture signal).
    signal_ids: list[uuid.UUID] = []
    for i, sig in enumerate(fx.signals):
        sig_id = uuid.uuid4()
        signal_ids.append(sig_id)
        sig_seen = now - timedelta(hours=sig.hours_before_disruption)
        await insert_signal(
            s,
            signal_id=sig_id,
            source_category=sig.source_category,
            source_name=sig.source_name,
            title=sig.title,
            summary=sig.summary,
            region=sig.region,
            lat=sig.lat,
            lng=sig.lng,
            radius_km=sig.radius_km,
            source_urls=list(sig.source_urls),
            confidence=sig.confidence,
            first_seen_at=sig_seen,
            dedupe_hash=hashlib.sha256(
                f"seed_scenario:{scenario_id}:{i}:{sig_id.hex}".encode()
            ).hexdigest(),
            promoted_to_disruption_id=disruption_id,
        )

    # 4. Disruption row.
    await insert_disruption(
        s,
        disruption_id=disruption_id,
        title=disruption.title,
        summary=disruption.summary,
        category=disruption.category,
        severity=disruption.severity,
        region=disruption.region,
        lat=disruption.lat,
        lng=disruption.lng,
        radius_km=float(disruption.radius_km) if disruption.radius_km is not None else None,
        source_signal_ids=signal_ids,
        confidence=float(disruption.confidence),
        first_seen_at=disruption_first_seen,
        last_seen_at=now,
        status=status,
    )

    # 5. Impact report.
    impact_id = uuid.uuid4()
    impact_generated_at = disruption_first_seen + timedelta(seconds=14)
    await insert_impact_report(
        s,
        impact_id=impact_id,
        disruption_id=disruption_id,
        total_exposure=fx.total_exposure,
        units_at_risk=fx.units_at_risk,
        cascade_depth=fx.cascade_depth,
        reasoning_trace=fx.reasoning_trace,
        generated_at=impact_generated_at,
    )
    await insert_affected_shipments(
        s,
        impact_id=impact_id,
        shipments=[(a.shipment_id, a.exposure, a.days_to_sla_breach) for a in fx.affected],
    )

    # 6. Mitigations + drafts.
    mitigation_ids: list[uuid.UUID] = []
    for mfx in fx.mitigations:
        mid = uuid.uuid4()
        mitigation_ids.append(mid)
        await insert_mitigation(
            s,
            mitigation_id=mid,
            impact_report_id=impact_id,
            option_type=mfx.option_type,
            description=mfx.description,
            delta_cost=mfx.delta_cost,
            delta_days=mfx.delta_days,
            confidence=mfx.confidence,
            rationale=mfx.rationale,
            status="pending",
        )
        for j, d in enumerate(mfx.drafts):
            await insert_draft(
                s,
                draft_id=uuid.uuid4(),
                mitigation_id=mid,
                recipient_type=d.recipient_type,
                recipient_contact=d.recipient_contact,
                subject=d.subject,
                body=d.body,
                created_at=impact_generated_at + timedelta(seconds=10 + j * 2),
            )

    # 7. Agent log cascade.
    await seed_cascade_agent_logs(
        s,
        trace_id=trace_id,
        disruption_id=disruption_id,
        impact_id=impact_id,
        mitigation_ids=mitigation_ids,
        first_seen_at=disruption_first_seen,
        total_exposure=fx.total_exposure,
    )

    await s.commit()
    return disruption_id


async def _main(scenario_ids: list[str], status: Status) -> None:
    settings = DBSettings()
    engine = create_async_engine(settings.database_url, echo=False)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    seeded: list[tuple[str, uuid.UUID]] = []
    async with session_factory() as s:
        for sid in scenario_ids:
            disruption_id = await seed_one_scenario(s, sid, status)
            seeded.append((sid, disruption_id))
    await engine.dispose()

    print("─" * 72)
    print(f"  Seeded {len(seeded)} scenario{'s' if len(seeded) != 1 else ''} (status={status})")
    for sid, did in seeded:
        print(f"    {sid:20s}  http://localhost:3000/disruption/{did}")
    print("─" * 72)


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="seed_scenario",
        description=(
            "Insert a full cascade of demo fixture rows (signal → disruption → "
            "impact report → affected shipments → mitigations → drafts → agent log) "
            "for one or all 5 canonical demo scenarios."
        ),
    )
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument(
        "--scenario",
        action="append",
        choices=sorted(SCENARIOS.keys()),
        help="Scenario id to seed. Repeat the flag for multiples.",
    )
    g.add_argument(
        "--all",
        action="store_true",
        help="Seed all 5 canonical demo scenarios.",
    )
    p.add_argument(
        "--status",
        choices=("active", "resolved"),
        default="active",
        help="Disruption status to seed with. 'active' is the default (useful "
        "for dev + on-stage failsafe). Use 'resolved' if you want the "
        "rows in the DB but off the War Room.",
    )
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    ns = _parse_args(argv)
    scenario_ids = sorted(SCENARIOS.keys()) if ns.all else ns.scenario
    asyncio.run(_main(scenario_ids, ns.status))
    return 0


if __name__ == "__main__":
    sys.exit(main())
