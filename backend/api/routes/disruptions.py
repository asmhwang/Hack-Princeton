from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, cast

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import aliased

from backend.api._pagination import apply_cursor
from backend.api.deps import SessionDep
from backend.db.models import (
    AffectedShipment,
    Customer,
    Disruption,
    DraftCommunication,
    ImpactReport,
    MitigationOption,
    Port,
    PurchaseOrder,
    Shipment,
    Sku,
    Supplier,
)
from backend.schemas import (
    ActiveRoute,
    AffectedShipmentEntry,
    DisruptionRecord,
    ImpactReportRecord,
    ImpactReportWithShipments,
    MitigationWithDrafts,
)
from backend.schemas.mitigation import DraftCommunicationRecord
from backend.schemas.route import RouteMode, RouteStatus

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
    """List disruptions sorted by last_seen_at DESC with optional cursor pagination.

    Enriches each row with ``total_exposure`` (sum of affected_shipments.exposure
    on the most-recent impact report) and ``affected_shipments_count``. The UI
    list views render $0 / 0 without this — the top-bar summary uses a separate
    aggregate so it's correct either way, but per-row numbers need the join.
    """
    # Subquery: one impact_report row per disruption (the most recent).
    latest_impact = select(
        ImpactReport.id.label("impact_id"),
        ImpactReport.disruption_id.label("disruption_id"),
        func.row_number()
        .over(
            partition_by=ImpactReport.disruption_id,
            order_by=ImpactReport.generated_at.desc(),
        )
        .label("rn"),
    ).subquery()

    agg = (
        select(
            latest_impact.c.disruption_id.label("disruption_id"),
            func.sum(AffectedShipment.exposure).label("total_exposure"),
            func.count(AffectedShipment.shipment_id).label("shipment_count"),
        )
        .select_from(latest_impact)
        .join(
            AffectedShipment,
            AffectedShipment.impact_report_id == latest_impact.c.impact_id,
        )
        .where(latest_impact.c.rn == 1)
        .group_by(latest_impact.c.disruption_id)
        .subquery()
    )

    stmt = (
        select(
            Disruption,
            agg.c.total_exposure,
            agg.c.shipment_count,
        )
        .select_from(Disruption)
        .outerjoin(agg, agg.c.disruption_id == Disruption.id)
        .order_by(Disruption.last_seen_at.desc())
    )

    if status is not None:
        stmt = stmt.where(Disruption.status == status)

    stmt = apply_cursor(stmt, before_col=Disruption.last_seen_at, before=before, limit=limit)

    result = await session.execute(stmt)
    out: list[DisruptionRecord] = []
    for row in result.all():
        rec = DisruptionRecord.model_validate(row[0])
        rec = rec.model_copy(
            update={
                "total_exposure": (Decimal(str(row[1])) if row[1] is not None else Decimal("0")),
                "affected_shipments_count": int(row[2]) if row[2] is not None else 0,
            }
        )
        out.append(rec)
    return out


_SEV_BLOCKED = 4
_SEV_WATCH = 3


def _route_status(severity: int) -> RouteStatus:
    if severity >= _SEV_BLOCKED:
        return "blocked"
    if severity == _SEV_WATCH:
        return "watch"
    return "good"


def _route_mode(shipment_mode: str | None) -> RouteMode:
    value = (shipment_mode or "").lower()
    if value == "sea":
        return "ocean"
    if value in {"ocean", "air", "rail", "truck"}:
        return cast(RouteMode, value)
    return "ocean"


@router.get("/active/routes", response_model=list[ActiveRoute], response_model_by_alias=True)
async def list_active_routes(session: SessionDep) -> list[ActiveRoute]:
    """Return one ActiveRoute per affected shipment across currently-active disruptions.

    Joins the most-recent impact report per active disruption through
    affected_shipments → shipments → ports (origin + dest) → suppliers. Used by
    the frontend globe to render arcs.
    """
    origin_port = aliased(Port)
    dest_port = aliased(Port)

    latest_ir = (
        select(ImpactReport.id)
        .where(ImpactReport.disruption_id == Disruption.id)
        .order_by(ImpactReport.generated_at.desc())
        .limit(1)
        .correlate(Disruption)
        .scalar_subquery()
    )

    stmt = (
        select(
            Shipment.id.label("shipment_id"),
            Disruption.id.label("disruption_id"),
            Disruption.category.label("disruption_category"),
            Disruption.severity.label("severity"),
            origin_port.lat.label("origin_lat"),
            origin_port.lng.label("origin_lng"),
            origin_port.name.label("origin_name"),
            dest_port.lat.label("dest_lat"),
            dest_port.lng.label("dest_lng"),
            dest_port.name.label("dest_name"),
            Shipment.mode.label("mode"),
            Shipment.eta.label("eta"),
            AffectedShipment.exposure.label("exposure"),
            Supplier.name.label("carrier"),
        )
        .select_from(Disruption)
        .join(ImpactReport, ImpactReport.id == latest_ir)
        .join(AffectedShipment, AffectedShipment.impact_report_id == ImpactReport.id)
        .join(Shipment, Shipment.id == AffectedShipment.shipment_id)
        .join(origin_port, origin_port.id == Shipment.origin_port_id)
        .join(dest_port, dest_port.id == Shipment.dest_port_id)
        .outerjoin(Supplier, Supplier.id == Shipment.supplier_id)
        .where(Disruption.status == "active")
    )

    result = await session.execute(stmt)
    today = date.today()
    routes: list[ActiveRoute] = []
    for row in result.all():
        if (
            row.origin_lat is None
            or row.origin_lng is None
            or row.dest_lat is None
            or row.dest_lng is None
        ):
            continue
        transit = (row.eta - today).days if row.eta is not None else 0
        routes.append(
            ActiveRoute.model_validate(
                {
                    "id": row.shipment_id,
                    "disruption_id": row.disruption_id,
                    "disruption_category": row.disruption_category,
                    "from": (float(row.origin_lat), float(row.origin_lng)),
                    "to": (float(row.dest_lat), float(row.dest_lng)),
                    "origin_name": row.origin_name,
                    "destination_name": row.dest_name,
                    "mode": _route_mode(row.mode),
                    "status": _route_status(row.severity),
                    "exposure": row.exposure if row.exposure is not None else Decimal("0"),
                    "transit_days": max(0, transit),
                    "carrier": row.carrier or "Unknown",
                }
            )
        )
    return routes


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

    # Fetch affected shipments for this report, enriched with shipment /
    # purchase-order / customer / SKU / origin+destination port info so the
    # detail table can render real labels instead of empty columns.
    origin_port = aliased(Port)
    dest_port = aliased(Port)
    as_stmt = (
        select(
            AffectedShipment.shipment_id,
            AffectedShipment.exposure,
            AffectedShipment.days_to_sla_breach,
            Shipment.status,
            Shipment.eta,
            PurchaseOrder.id.label("po_id"),
            PurchaseOrder.customer_id,
            Customer.name.label("customer_name"),
            Sku.description.label("sku_description"),
            origin_port.name.label("origin_name"),
            origin_port.lat.label("origin_lat"),
            origin_port.lng.label("origin_lng"),
            dest_port.name.label("destination_name"),
            dest_port.lat.label("destination_lat"),
            dest_port.lng.label("destination_lng"),
        )
        .select_from(AffectedShipment)
        .outerjoin(Shipment, Shipment.id == AffectedShipment.shipment_id)
        .outerjoin(PurchaseOrder, PurchaseOrder.id == Shipment.po_id)
        .outerjoin(Customer, Customer.id == PurchaseOrder.customer_id)
        .outerjoin(Sku, Sku.id == PurchaseOrder.sku_id)
        .outerjoin(origin_port, origin_port.id == Shipment.origin_port_id)
        .outerjoin(dest_port, dest_port.id == Shipment.dest_port_id)
        .where(AffectedShipment.impact_report_id == report.id)
    )
    as_result = await session.execute(as_stmt)
    shipments: list[AffectedShipmentEntry] = []
    for r in as_result.all():
        shipments.append(
            AffectedShipmentEntry(
                shipment_id=r.shipment_id,
                exposure=r.exposure,
                days_to_sla_breach=r.days_to_sla_breach,
                sku=r.sku_description,
                customer_name=r.customer_name,
                po_number=r.po_id,
                origin=r.origin_name,
                destination=r.destination_name,
                status=r.status,
                eta=r.eta.isoformat() if r.eta is not None else None,
                origin_lat=float(r.origin_lat) if r.origin_lat is not None else None,
                origin_lng=float(r.origin_lng) if r.origin_lng is not None else None,
                destination_lat=float(r.destination_lat) if r.destination_lat is not None else None,
                destination_lng=float(r.destination_lng) if r.destination_lng is not None else None,
            )
        )

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
