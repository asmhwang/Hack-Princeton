from __future__ import annotations

import dataclasses
import hashlib
import json
import uuid
from decimal import Decimal
from typing import Literal

import asyncpg
from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict
from sqlalchemy.dialects.postgresql import insert as pg_insert

from backend.api.deps import SessionDep
from backend.db.models import Disruption, Signal
from backend.db.session import DBSettings
from backend.scripts.scenarios import SCENARIOS
from backend.scripts.scenarios._types import Scenario
from backend.scripts.scenarios.prime_chain import seed_prime_chain

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
    """Insert a Signal and Disruption row for the given scenario and emit pg_notify.

    Pre-promotes the signal to a disruption immediately (bypassing the normal Scout
    agent promotion step) so Plan B's UI has a complete disruption to display without
    requiring the agents to be running.

    NOTE: Once Plan A's Scout agent is implemented, it will own the signal→disruption
    promotion step. This stub pre-promotes as a convenience for demo and e2e testing.
    Both notifies (new_signal + new_disruption) are emitted so that when the Analyst
    agent is wired up it will react to new_disruption and generate impact reports.
    """
    scenario: Scenario = SCENARIOS[body.scenario]
    sig = scenario.signal
    dis = scenario.disruption

    # Prime-chain backstop: seeds FK-valid Port/Supplier/SKU/Customer/POs/3 ships
    # pinned at the disruption centroid. Matches prime_cache.py's prime-time
    # seeding, so cached Analyst affected_shipments refs (SHP-PRIME-*) exist
    # at demo time. Idempotent via ON CONFLICT DO NOTHING.
    await seed_prime_chain(session, scenario)

    # Generate both IDs upfront so we can set up the bidirectional FK references
    # (signals.promoted_to_disruption_id ↔ disruptions.source_signal_ids) in a
    # single pass without a flush/update dance.
    signal_id = uuid.uuid4()
    disruption_id = uuid.uuid4()

    # Unique hash per invocation so re-simulating the same scenario produces fresh rows.
    # Including uuid4 entropy ensures two calls in the same millisecond differ.
    dedupe_hash = hashlib.sha256(f"{body.scenario}:{signal_id.hex}".encode()).hexdigest()

    # Insert Signal row — store dedupe_keywords in raw_payload (no dedicated column).
    signal_stmt = (
        pg_insert(Signal)
        .values(
            id=signal_id,
            source_category=sig.source_category,
            source_name=sig.source_name,
            title=sig.title,
            summary=sig.summary,
            region=sig.region,
            lat=sig.lat,
            lng=sig.lng,
            radius_km=Decimal(str(sig.radius_km)),
            source_urls=sig.source_urls,
            confidence=Decimal(str(sig.confidence)),
            raw_payload={"dedupe_keywords": sig.dedupe_keywords},
            dedupe_hash=dedupe_hash,
            promoted_to_disruption_id=disruption_id,
        )
        .on_conflict_do_nothing(index_elements=["dedupe_hash"])
    )
    await session.execute(signal_stmt)

    # Insert Disruption row linked back to the signal.
    disruption_stmt = (
        pg_insert(Disruption)
        .values(
            id=disruption_id,
            title=dis.title,
            summary=dis.summary,
            category=dis.category,
            severity=dis.severity,
            region=dis.region,
            lat=dis.lat,
            lng=dis.lng,
            radius_km=Decimal(str(dis.radius_km)),
            source_signal_ids=[signal_id],
            confidence=Decimal(str(dis.confidence)),
            status=dis.status,
        )
        .on_conflict_do_nothing(index_elements=["id"])
    )
    await session.execute(disruption_stmt)

    await session.commit()

    # Emit pg_notify on both channels so that when agents come online they react.
    await _notify(
        "new_signal",
        json.dumps({"id": str(signal_id), "source_category": sig.source_category}),
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
        signal_id=signal_id,
        disruption_id=disruption_id,
        scenario=body.scenario,
        expected=dataclasses.asdict(scenario.expected),
    )


async def _notify(channel: str, payload: str) -> None:
    """Emit a Postgres NOTIFY on channel with payload via raw asyncpg connection."""
    dsn = DBSettings().database_url.replace("postgresql+asyncpg://", "postgresql://")
    conn = await asyncpg.connect(dsn)
    try:
        await conn.execute("SELECT pg_notify($1, $2)", channel, payload)
    finally:
        await conn.close()
