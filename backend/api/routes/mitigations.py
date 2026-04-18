from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from backend.api._approval import ApprovalConflictError, approve_mitigation
from backend.api.deps import SessionDep, UserDep
from backend.db.models import MitigationOption
from backend.schemas import ApprovalRecord, ApprovalResponse, MitigationOptionRecord

router = APIRouter()


@router.post("/{mitigation_id}/approve", response_model=ApprovalResponse)
async def approve_route(
    mitigation_id: uuid.UUID,
    user: UserDep,
) -> ApprovalResponse:
    """Atomically approve a mitigation option.

    Flips all affected shipments to 'rerouting', writes an Approval audit row,
    flips the mitigation status to 'approved', then fires a pg_notify.

    All DB mutations are inside a single transaction; failure at any step
    leaves zero partial state.
    """
    try:
        result = await approve_mitigation(mitigation_id, user)
    except LookupError as exc:
        raise HTTPException(
            status_code=404, detail=f"mitigation {mitigation_id} not found"
        ) from exc
    except ApprovalConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"approval failed: {exc}") from exc

    return ApprovalResponse(
        approval=ApprovalRecord.model_validate(result["approval"]),
        shipments_flipped=result["shipments_flipped"],  # type: ignore[arg-type]
        drafts_saved=result["drafts_saved"],  # type: ignore[arg-type]
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
