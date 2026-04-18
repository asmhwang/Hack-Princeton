"""Core approval transaction logic — Task 9.1 / Plan C task C.7.

Structured as a standalone module with individually testable (monkey-patchable)
helpers to make the atomicity guarantees easy to verify and to enable a clean
swap to OpenClaw at Task 7.3.

Design decisions:
- Fresh session per approval (avoids nested-transaction savepoint subtleties).
- All mutations inside a single `async with s.begin()` — one atomic unit.
- pg_notify fires AFTER commit via a separate raw asyncpg connection (best-effort).
"""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime
from decimal import Decimal

import asyncpg
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.models import (
    AffectedShipment,
    Approval,
    DraftCommunication,
    ImpactReport,
    MitigationOption,
    Shipment,
)
from backend.db.session import DBSettings, session

_log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Internal helpers — all accept an AsyncSession so they can be monkey-patched
# in tests without affecting the session management layer.
# ---------------------------------------------------------------------------


async def _load_mitigation_with_context(
    s: AsyncSession,
    mitigation_id: uuid.UUID,
) -> tuple[MitigationOption, ImpactReport, list[str], list[uuid.UUID]]:
    """Load mitigation + linked impact report + affected shipment IDs + draft IDs.

    Raises LookupError if the mitigation is not found.
    """
    mit_row = (
        await s.execute(select(MitigationOption).where(MitigationOption.id == mitigation_id))
    ).scalar_one_or_none()
    if mit_row is None:
        raise LookupError(f"mitigation {mitigation_id} not found")

    impact_row = (
        await s.execute(select(ImpactReport).where(ImpactReport.id == mit_row.impact_report_id))
    ).scalar_one()

    # Affected shipment IDs (str PKs)
    affected_rows = (
        (
            await s.execute(
                select(AffectedShipment).where(AffectedShipment.impact_report_id == impact_row.id)
            )
        )
        .scalars()
        .all()
    )
    shipment_ids = [row.shipment_id for row in affected_rows]

    # Draft IDs linked to this mitigation
    draft_rows = (
        (
            await s.execute(
                select(DraftCommunication).where(DraftCommunication.mitigation_id == mitigation_id)
            )
        )
        .scalars()
        .all()
    )
    draft_ids = [row.id for row in draft_rows]

    return mit_row, impact_row, shipment_ids, draft_ids


async def _flip_shipments(s: AsyncSession, shipment_ids: list[str]) -> int:
    """Flip status of the given shipments to 'rerouting'. Returns count flipped."""
    if not shipment_ids:
        return 0
    result = await s.execute(
        update(Shipment).where(Shipment.id.in_(shipment_ids)).values(status="rerouting")
    )
    return result.rowcount  # type: ignore[return-value]


async def _write_audit(
    s: AsyncSession,
    mitigation_id: uuid.UUID,
    approved_by: str,
    state_snapshot: dict[str, object],
) -> Approval:
    """Insert the Approval row and return it (with server_default fields populated)."""
    # DB column is TIMESTAMP WITHOUT TIME ZONE — strip tzinfo after generating UTC time.
    approved_at = datetime.now(UTC).replace(tzinfo=None)
    approval = Approval(
        id=uuid.uuid4(),
        mitigation_id=mitigation_id,
        approved_by=approved_by,
        approved_at=approved_at,
        state_snapshot=state_snapshot,
    )
    s.add(approval)
    await s.flush()  # push INSERT so we can refresh
    await s.refresh(approval)
    return approval


async def _notify_approval(payload: str) -> None:
    """Send a pg_notify on the new_approval channel.

    Uses a fresh asyncpg connection OUTSIDE the approval transaction so the
    notification fires only after the transaction has committed (the caller
    must only invoke this after `s.begin()` exits cleanly).

    Best-effort: failure is logged but does NOT raise.
    """
    try:
        dsn = DBSettings().database_url.replace("+asyncpg", "", 1)
        conn = await asyncpg.connect(dsn)
        try:
            await conn.execute("SELECT pg_notify($1, $2)", "new_approval", payload)
        finally:
            await conn.close()
    except Exception as exc:  # noqa: BLE001
        # Notification is informational; durability is already guaranteed by the
        # committed transaction.
        _log.warning("pg_notify new_approval failed (best-effort): %s", exc)


# ---------------------------------------------------------------------------
# Public error type
# ---------------------------------------------------------------------------


class ApprovalConflictError(Exception):
    """Raised when the mitigation is already approved or dismissed."""


# ---------------------------------------------------------------------------
# Top-level transaction function
# ---------------------------------------------------------------------------


async def approve_mitigation(
    mitigation_id: uuid.UUID,
    approved_by: str,
) -> dict[str, object]:
    """Atomically approve a mitigation option.

    Opens a fresh session + transaction. All mutations (shipment flip, audit
    row, mitigation status) happen inside a single `async with s.begin()`.
    On any exception the transaction rolls back entirely — no partial state.

    pg_notify fires AFTER commit (outside the transaction block) and is
    best-effort.

    Returns a dict shaped for ApprovalResponse serialisation.
    """
    # Phase 1: pre-transaction load + validation (read-only).
    async with session() as s:
        mitigation, impact, shipment_ids, draft_ids = await _load_mitigation_with_context(
            s, mitigation_id
        )

    if mitigation.status != "pending":
        raise ApprovalConflictError(f"mitigation is already {mitigation.status}")

    total_exposure_avoided = Decimal(str(impact.total_exposure))

    state_snapshot: dict[str, object] = {
        "mitigation_id": str(mitigation_id),
        "shipment_ids_flipped": shipment_ids,
        "total_exposure_avoided": str(total_exposure_avoided),
        "drafts_saved": [str(did) for did in draft_ids],
    }

    # Phase 2: atomic transaction on a fresh session.
    approval: Approval
    async with session() as s, s.begin():
        flipped = await _flip_shipments(s, shipment_ids)
        approval = await _write_audit(s, mitigation_id, approved_by, state_snapshot)
        # Flip mitigation status inside the same transaction
        await s.execute(
            MitigationOption.__table__.update()
            .where(MitigationOption.id == mitigation_id)
            .values(status="approved")
        )
    # `s.begin()` context exited cleanly → transaction committed.

    # Phase 3: best-effort notify (outside transaction).
    await _notify_approval(f'{{"id":"{approval.id}","mitigation_id":"{mitigation_id}"}}')

    return {
        "approval": approval,
        "shipments_flipped": flipped,
        "drafts_saved": len(draft_ids),
    }
