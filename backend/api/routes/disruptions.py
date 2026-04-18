from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import select

from backend.api._pagination import apply_cursor
from backend.api.deps import SessionDep
from backend.db.models import (
    AffectedShipment,
    Disruption,
    DraftCommunication,
    ImpactReport,
    MitigationOption,
)
from backend.schemas import (
    AffectedShipmentEntry,
    DisruptionRecord,
    ImpactReportRecord,
    ImpactReportWithShipments,
    MitigationWithDrafts,
)
from backend.schemas.mitigation import DraftCommunicationRecord

router = APIRouter()


@router.get("")
async def list_disruptions(
    session: SessionDep,
    status: Annotated[
        str | None,
        Query(description="Filter by status: 'active' or 'resolved'"),
    ] = None,
    before: Annotated[
        datetime | None,
        Query(description="Cursor: return rows with last_seen_at < this ISO timestamp"),
    ] = None,
    limit: Annotated[
        int,
        Query(ge=1, le=200, description="Max rows to return (1-200)"),
    ] = 50,
) -> list[DisruptionRecord]:
    """List disruptions sorted by last_seen_at DESC with optional cursor pagination."""
    stmt = select(Disruption).order_by(Disruption.last_seen_at.desc())

    if status is not None:
        stmt = stmt.where(Disruption.status == status)

    stmt = apply_cursor(stmt, before_col=Disruption.last_seen_at, before=before, limit=limit)

    result = await session.execute(stmt)
    rows = result.scalars().all()
    return [DisruptionRecord.model_validate(r) for r in rows]


@router.get("/{disruption_id}")
async def get_disruption(
    disruption_id: uuid.UUID,
    session: SessionDep,
) -> DisruptionRecord:
    """Get a single disruption by ID."""
    stmt = select(Disruption).where(Disruption.id == disruption_id)
    result = await session.execute(stmt)
    row = result.scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail=f"Disruption {disruption_id} not found")
    return DisruptionRecord.model_validate(row)


@router.get("/{disruption_id}/impact")
async def get_disruption_impact(
    disruption_id: uuid.UUID,
    session: SessionDep,
) -> ImpactReportWithShipments:
    """Get the most recent impact report for a disruption, including affected shipments."""
    # Verify disruption exists
    d_stmt = select(Disruption).where(Disruption.id == disruption_id)
    d_result = await session.execute(d_stmt)
    if d_result.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail=f"Disruption {disruption_id} not found")

    # Get most recent impact report
    ir_stmt = (
        select(ImpactReport)
        .where(ImpactReport.disruption_id == disruption_id)
        .order_by(ImpactReport.generated_at.desc())
        .limit(1)
    )
    ir_result = await session.execute(ir_stmt)
    report = ir_result.scalar_one_or_none()
    if report is None:
        raise HTTPException(
            status_code=404,
            detail=f"No impact report found for disruption {disruption_id}",
        )

    # Fetch affected shipments for this report
    as_stmt = select(AffectedShipment).where(AffectedShipment.impact_report_id == report.id)
    as_result = await session.execute(as_stmt)
    shipment_rows = as_result.scalars().all()

    shipments = [
        AffectedShipmentEntry(
            shipment_id=s.shipment_id,
            exposure=s.exposure,
            days_to_sla_breach=s.days_to_sla_breach,
        )
        for s in shipment_rows
    ]

    base = ImpactReportRecord.model_validate(report)
    return ImpactReportWithShipments(
        id=base.id,
        disruption_id=base.disruption_id,
        total_exposure=base.total_exposure,
        units_at_risk=base.units_at_risk,
        cascade_depth=base.cascade_depth,
        sql_executed=base.sql_executed,
        reasoning_trace=base.reasoning_trace,
        generated_at=base.generated_at,
        affected_shipments=shipments,
    )


@router.get("/{disruption_id}/mitigations")
async def get_disruption_mitigations(
    disruption_id: uuid.UUID,
    session: SessionDep,
) -> list[MitigationWithDrafts]:
    """Get mitigation options for the latest impact report of a disruption, including drafts."""
    # Verify disruption exists
    d_stmt = select(Disruption).where(Disruption.id == disruption_id)
    d_result = await session.execute(d_stmt)
    if d_result.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail=f"Disruption {disruption_id} not found")

    # Get most recent impact report
    ir_stmt = (
        select(ImpactReport)
        .where(ImpactReport.disruption_id == disruption_id)
        .order_by(ImpactReport.generated_at.desc())
        .limit(1)
    )
    ir_result = await session.execute(ir_stmt)
    report = ir_result.scalar_one_or_none()
    if report is None:
        return []

    # Get mitigation options for this report
    mo_stmt = select(MitigationOption).where(MitigationOption.impact_report_id == report.id)
    mo_result = await session.execute(mo_stmt)
    mitigations = mo_result.scalars().all()

    result: list[MitigationWithDrafts] = []
    for m in mitigations:
        dc_stmt = select(DraftCommunication).where(DraftCommunication.mitigation_id == m.id)
        dc_result = await session.execute(dc_stmt)
        drafts = [DraftCommunicationRecord.model_validate(d) for d in dc_result.scalars().all()]

        result.append(
            MitigationWithDrafts(
                id=m.id,
                impact_report_id=m.impact_report_id,
                option_type=m.option_type,  # type: ignore[arg-type]
                description=m.description,
                delta_cost=m.delta_cost,
                delta_days=m.delta_days,
                confidence=float(m.confidence),
                rationale=m.rationale,
                status=m.status,  # type: ignore[arg-type]
                drafts=drafts,
            )
        )

    return result
