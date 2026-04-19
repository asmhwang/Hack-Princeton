from __future__ import annotations

import dataclasses
import hashlib
import json
import uuid
from datetime import UTC, datetime, timedelta
from typing import Literal

import asyncpg
from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict
from sqlalchemy import delete

from backend.api.deps import SessionDep
from backend.db.models import (
    AffectedShipment,
    AgentLog,
    Approval,
    Disruption,
    DraftCommunication,
    ImpactReport,
    MitigationOption,
    Signal,
)
from backend.db.session import DBSettings
from backend.scripts.scenarios import SCENARIOS
from backend.scripts.scenarios._types import Scenario
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

router = APIRouter()

_SCENARIO_IDS: list[str] = [
    "typhoon_kaia",
    "busan_strike",
    "cbam_tariff",
    "luxshare_fire",
    "redsea_advisory",
]

ScenarioId = Literal[
    "typhoon_kaia",
    "busan_strike",
    "cbam_tariff",
    "luxshare_fire",
    "redsea_advisory",
]


class SimulateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scenario: ScenarioId


class SimulateResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    signal_id: uuid.UUID
    disruption_id: uuid.UUID
    scenario: str
    expected: dict[str, object]


@router.get("/scenarios")
async def list_scenarios() -> list[str]:
    """Return the 5 canonical demo scenario IDs."""
    return _SCENARIO_IDS


@router.post("/simulate")
async def simulate(
    body: SimulateRequest,
    session: SessionDep,
) -> SimulateResponse:
    """Insert the full demo cascade for a scenario and emit pg_notify.

    Writes: prime_chain → Signal(s) → Disruption → ImpactReport
    → AffectedShipments → MitigationOption(s) → DraftCommunication(s)
    → AgentLog cascade. Mirrors backend/scripts/seed_scenario.py::seed_one_scenario
    so clicking "Simulate event" in the UI produces a complete disruption card
    (with exposure, affected shipments, mitigation options, drafts) even when
    the live Analyst + Strategist agents are not running.

    Notifies (new_signal + new_disruption) still fire so that when agents DO
    come online they react to the new disruption.
    """
    scenario: Scenario = SCENARIOS[body.scenario]
    sig = scenario.signal
    dis = scenario.disruption
    fx = ACTIVE_SCENARIO_FIXTURES[body.scenario]

    # Prime-chain backstop: seeds FK-valid Port/Supplier/SKU/Customer/POs/3 ships
    # pinned at the disruption centroid. Idempotent via ON CONFLICT DO NOTHING.
    await seed_prime_chain(session, scenario)

    disruption_id = uuid.uuid4()
    trace_id = uuid.uuid4()
    now = datetime.now(UTC).replace(tzinfo=None)
    disruption_first_seen = now - timedelta(
        hours=max(sfx.hours_before_disruption for sfx in fx.signals)
    )

    # Insert all fixture signals (multi-signal scenarios are common — e.g. a
    # typhoon has both a weather advisory and a port closure feed).
    signal_ids: list[uuid.UUID] = []
    for i, sfx in enumerate(fx.signals):
        sid = uuid.uuid4()
        signal_ids.append(sid)
        sig_seen = now - timedelta(hours=sfx.hours_before_disruption)
        # Unique per invocation: scenario + per-signal index + sid entropy.
        dedupe_hash = hashlib.sha256(f"simulate:{body.scenario}:{i}:{sid.hex}".encode()).hexdigest()
        await insert_signal(
            session,
            signal_id=sid,
            source_category=sfx.source_category,
            source_name=sfx.source_name,
            title=sfx.title,
            summary=sfx.summary,
            region=sfx.region,
            lat=sfx.lat,
            lng=sfx.lng,
            radius_km=sfx.radius_km,
            source_urls=list(sfx.source_urls),
            confidence=sfx.confidence,
            first_seen_at=sig_seen,
            dedupe_hash=dedupe_hash,
            promoted_to_disruption_id=disruption_id,
        )

    await insert_disruption(
        session,
        disruption_id=disruption_id,
        title=dis.title,
        summary=dis.summary,
        category=dis.category,
        severity=dis.severity,
        region=dis.region,
        lat=dis.lat,
        lng=dis.lng,
        radius_km=float(dis.radius_km) if dis.radius_km is not None else None,
        source_signal_ids=signal_ids,
        confidence=float(dis.confidence),
        first_seen_at=disruption_first_seen,
        last_seen_at=now,
        status="active",
    )

    impact_id = uuid.uuid4()
    impact_generated_at = disruption_first_seen + timedelta(seconds=14)
    await insert_impact_report(
        session,
        impact_id=impact_id,
        disruption_id=disruption_id,
        total_exposure=fx.total_exposure,
        units_at_risk=fx.units_at_risk,
        cascade_depth=fx.cascade_depth,
        reasoning_trace=fx.reasoning_trace,
        generated_at=impact_generated_at,
    )
    await insert_affected_shipments(
        session,
        impact_id=impact_id,
        shipments=[(a.shipment_id, a.exposure, a.days_to_sla_breach) for a in fx.affected],
    )

    mitigation_ids: list[uuid.UUID] = []
    for mfx in fx.mitigations:
        mid = uuid.uuid4()
        mitigation_ids.append(mid)
        await insert_mitigation(
            session,
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
                session,
                draft_id=uuid.uuid4(),
                mitigation_id=mid,
                recipient_type=d.recipient_type,
                recipient_contact=d.recipient_contact,
                subject=d.subject,
                body=d.body,
                created_at=impact_generated_at + timedelta(seconds=10 + j * 2),
            )

    await seed_cascade_agent_logs(
        session,
        trace_id=trace_id,
        disruption_id=disruption_id,
        impact_id=impact_id,
        mitigation_ids=mitigation_ids,
        first_seen_at=disruption_first_seen,
        total_exposure=fx.total_exposure,
    )

    await session.commit()

    primary_signal_id = signal_ids[0]
    await _notify(
        "new_signal",
        json.dumps({"id": str(primary_signal_id), "source_category": sig.source_category}),
    )
    await _notify(
        "new_disruption",
        json.dumps(
            {
                "id": str(disruption_id),
                "category": dis.category,
                "severity": dis.severity,
            }
        ),
    )

    return SimulateResponse(
        signal_id=primary_signal_id,
        disruption_id=disruption_id,
        scenario=body.scenario,
        expected=dataclasses.asdict(scenario.expected),
    )


class ClearResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    cleared: bool
    counts: dict[str, int]


@router.post("/clear")
async def clear_all(session: SessionDep) -> ClearResponse:
    """Wipe every disruption and everything downstream.

    Deletes in FK-safe order:
      draft_communications → approvals → affected_shipments → mitigation_options
      → impact_reports → disruptions → signals → agent_log

    Reference tables (ports, suppliers, SKUs, customers, purchase_orders,
    shipments) are intentionally preserved — prime_chain rows are shared
    across scenarios and re-created idempotently on next simulate.

    Single transaction. Returns per-table row counts removed.
    """
    counts: dict[str, int] = {}
    # Order matters — children first to avoid FK violations.
    for table in (
        DraftCommunication,
        Approval,
        AffectedShipment,
        MitigationOption,
        ImpactReport,
        Disruption,
        Signal,
        AgentLog,
    ):
        result = await session.execute(delete(table))
        counts[table.__tablename__] = result.rowcount or 0
    await session.commit()
    return ClearResponse(cleared=True, counts=counts)


async def _notify(channel: str, payload: str) -> None:
    """Emit a Postgres NOTIFY on channel with payload via raw asyncpg connection."""
    dsn = DBSettings().database_url.replace("postgresql+asyncpg://", "postgresql://")
    conn = await asyncpg.connect(dsn)
    try:
        await conn.execute("SELECT pg_notify($1, $2)", channel, payload)
    finally:
        await conn.close()
