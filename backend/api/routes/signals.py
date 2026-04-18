from __future__ import annotations

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Query
from sqlalchemy import select

from backend.api._pagination import apply_cursor
from backend.api.deps import SessionDep
from backend.db.models import Signal
from backend.schemas import SignalRecord

router = APIRouter()


@router.get("")
async def list_signals(
    session: SessionDep,
    status: Annotated[
        str | None,
        Query(
            description=(
                "Filter by promotion status: 'active' (promoted) or 'pending' (not yet promoted)"
            )
        ),
    ] = None,
    before: Annotated[
        datetime | None,
        Query(description="Cursor: return rows with first_seen_at < this ISO timestamp"),
    ] = None,
    limit: Annotated[
        int,
        Query(ge=1, le=200, description="Max rows to return (1-200)"),
    ] = 50,
) -> list[SignalRecord]:
    """List signals sorted by first_seen_at DESC with optional cursor pagination.

    Use ?status=active to return only signals that have been promoted to a disruption.
    Use ?status=pending to return only signals that have not yet been promoted.
    """
    stmt = select(Signal).order_by(Signal.first_seen_at.desc())

    if status == "active":
        stmt = stmt.where(Signal.promoted_to_disruption_id.is_not(None))
    elif status == "pending":
        stmt = stmt.where(Signal.promoted_to_disruption_id.is_(None))

    stmt = apply_cursor(stmt, before_col=Signal.first_seen_at, before=before, limit=limit)

    result = await session.execute(stmt)
    rows = result.scalars().all()
    return [SignalRecord.model_validate(r) for r in rows]
