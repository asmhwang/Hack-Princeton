from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from backend.api.deps import SessionDep
from backend.db.models import MitigationOption
from backend.schemas import MitigationOptionRecord

router = APIRouter()


@router.post("/{mitigation_id}/approve")
async def approve_mitigation(
    mitigation_id: uuid.UUID,
    session: SessionDep,
) -> None:
    """Stub — full atomic approval is implemented in Task 9.1 (C.7)."""
    raise HTTPException(
        status_code=501,
        detail="Task 9.1 implements atomic approval",
    )


@router.post("/{mitigation_id}/dismiss")
async def dismiss_mitigation(
    mitigation_id: uuid.UUID,
    session: SessionDep,
) -> MitigationOptionRecord:
    """Flip mitigation status to 'dismissed'.

    Single-table update; no transaction cascade required at this stage.
    """
    stmt = select(MitigationOption).where(MitigationOption.id == mitigation_id)
    result = await session.execute(stmt)
    row = result.scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail=f"Mitigation {mitigation_id} not found")

    row.status = "dismissed"
    await session.commit()
    await session.refresh(row)
    return MitigationOptionRecord.model_validate(row)
