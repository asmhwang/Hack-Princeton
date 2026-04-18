from __future__ import annotations

import json
import uuid
from decimal import Decimal
from typing import Literal

import asyncpg
from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict
from sqlalchemy.dialects.postgresql import insert as pg_insert

from backend.api.deps import SessionDep
from backend.db.models import Signal
from backend.db.session import DBSettings

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
    scenario: str
    note: str


@router.get("/scenarios")
async def list_scenarios() -> list[str]:
    """Return the 5 canonical demo scenario IDs."""
    return _SCENARIO_IDS


@router.post("/simulate")
async def simulate(
    body: SimulateRequest,
    session: SessionDep,
) -> SimulateResponse:
    """Insert a placeholder Signal row and emit pg_notify new_signal.

    Task 11 will wire the full scenario cascade. This stub gives Plan B a
    testable Simulate button today.
    """
    signal_id = uuid.uuid4()
    stmt = (
        pg_insert(Signal)
        .values(
            id=signal_id,
            source_category="news",
            source_name=f"simulate:{body.scenario}",
            title=f"Simulated {body.scenario}",
            summary=None,
            region=None,
            lat=None,
            lng=None,
            radius_km=None,
            source_urls=[],
            confidence=Decimal("0.5"),
            raw_payload={},
            dedupe_hash=uuid.uuid4().hex,  # always unique so inserts never collide
            promoted_to_disruption_id=None,
        )
        .on_conflict_do_nothing(index_elements=["dedupe_hash"])
    )
    await session.execute(stmt)
    await session.commit()

    # Emit pg_notify via raw asyncpg (SQLAlchemy has no NOTIFY primitive).
    await _notify("new_signal", json.dumps({"id": str(signal_id), "source_category": "news"}))

    return SimulateResponse(
        signal_id=signal_id,
        scenario=body.scenario,
        note="Task 11 will wire full cascade",
    )


async def _notify(channel: str, payload: str) -> None:
    """Emit a Postgres NOTIFY on channel with payload via raw asyncpg connection."""
    dsn = DBSettings().database_url.replace("postgresql+asyncpg://", "postgresql://")
    conn = await asyncpg.connect(dsn)
    try:
        await conn.execute("SELECT pg_notify($1, $2)", channel, payload)
    finally:
        await conn.close()
