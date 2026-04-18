from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select

from backend.api.deps import SessionDep
from backend.db.models import AgentLog

router = APIRouter()


class ActivityEntry(BaseModel):
    """Single agent log entry for the activity feed."""

    model_config = ConfigDict(extra="forbid")

    id: int
    agent_name: str
    event_type: str
    payload: dict[str, object]
    ts: datetime


@router.get("/feed")
async def get_activity_feed(
    session: SessionDep,
    limit: int = Query(50, ge=1, le=200, description="Max entries to return (1-200)"),
) -> list[ActivityEntry]:
    """Return recent agent activity from agent_log, sorted by ts DESC."""
    stmt = select(AgentLog).order_by(AgentLog.ts.desc()).limit(min(limit, 200))
    result = await session.execute(stmt)
    rows = result.scalars().all()
    return [
        ActivityEntry(
            id=r.id,
            agent_name=r.agent_name,
            event_type=r.event_type,
            payload=r.payload,
            ts=r.ts,
        )
        for r in rows
    ]
