from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Query
from sqlalchemy import case, func, select
from sqlalchemy.orm import aliased

from backend.api.deps import SessionDep
from backend.db.models import (
    AffectedShipment,
    Customer,
    Disruption,
    ImpactReport,
    PurchaseOrder,
    Shipment,
    Sku,
)
from backend.schemas.analytics import (
    AnalyticsPoint,
    AnalyticsSummary,
    ExposureBucket,
    ExposureSummary,
)

router = APIRouter()

GroupBy = Literal["quarter", "customer", "sku"]
TimeRange = Literal["24h", "7d", "30d", "QTD"]


def _range_cutoff(range_: TimeRange) -> datetime:
    """Return the inclusive lower bound for ImpactReport.generated_at."""
    now = datetime.now(UTC).replace(tzinfo=None)
    if range_ == "24h":
        return now - timedelta(hours=24)
    if range_ == "7d":
        return now - timedelta(days=7)
    if range_ == "30d":
        return now - timedelta(days=30)
    # QTD: start of current calendar quarter
    quarter_start_month = ((now.month - 1) // 3) * 3 + 1
    return datetime(now.year, quarter_start_month, 1)


@router.get("/exposure/summary")
async def get_exposure_summary(session: SessionDep) -> ExposureSummary:
    """Return (active_count, total_exposure) for the War Room status grid.

    - active_count: disruptions with status='active'
    - total_exposure: sum of most-recent impact_report.total_exposure per active
      disruption (approximation — one-to-one for now)
    """
    active_stmt = select(func.count()).select_from(Disruption).where(Disruption.status == "active")
    active_result = await session.execute(active_stmt)
    active_count = int(active_result.scalar() or 0)

    # Sum total_exposure across active disruptions' most-recent impact report.
    exposure_stmt = (
        select(func.sum(ImpactReport.total_exposure))
        .select_from(Disruption)
        .join(ImpactReport, ImpactReport.disruption_id == Disruption.id)
        .where(Disruption.status == "active")
    )
    exposure_result = await session.execute(exposure_stmt)
    total_exposure = exposure_result.scalar() or Decimal("0")

    return ExposureSummary(active_count=active_count, total_exposure=Decimal(str(total_exposure)))


@router.get("/exposure/breakdown")
async def get_exposure_breakdown(
    session: SessionDep,
    range: Annotated[TimeRange, Query(description="Time window")] = "7d",
) -> AnalyticsSummary:
    """Return exposure grouped three ways (customer / sku / quarter) in one shot.

    Filtered to impact reports whose ``generated_at`` falls within the requested
    time window so the Analytics screen's 24h / 7d / 30d / QTD tabs produce
    different aggregates.
    """
    cutoff = _range_cutoff(range)
    exposure_sum = func.sum(AffectedShipment.exposure).label("exposure")
    at_risk_sum = func.sum(
        case((Disruption.status != "resolved", AffectedShipment.exposure), else_=0)
    ).label("at_risk")
    mitigated_sum = func.sum(
        case((Disruption.status == "resolved", AffectedShipment.exposure), else_=0)
    ).label("mitigated")
    ship_count = func.count(func.distinct(AffectedShipment.shipment_id)).label("count")

    # by_customer
    cust_alias = aliased(Customer)
    cust_label = func.coalesce(cust_alias.name, PurchaseOrder.customer_id).label("label")
    cust_stmt = (
        select(cust_label, exposure_sum, at_risk_sum, mitigated_sum, ship_count)
        .select_from(ImpactReport)
        .join(Disruption, Disruption.id == ImpactReport.disruption_id)
        .join(AffectedShipment, AffectedShipment.impact_report_id == ImpactReport.id)
        .join(Shipment, Shipment.id == AffectedShipment.shipment_id)
        .join(PurchaseOrder, PurchaseOrder.id == Shipment.po_id)
        .outerjoin(cust_alias, cust_alias.id == PurchaseOrder.customer_id)
        .where(ImpactReport.generated_at >= cutoff)
        .group_by(cust_label)
        .order_by(cust_label)
    )

    # by_sku — label by human-readable description, falling back to sku_id
    sku_label = func.coalesce(Sku.description, PurchaseOrder.sku_id).label("label")
    sku_stmt = (
        select(sku_label, exposure_sum, at_risk_sum, mitigated_sum, ship_count)
        .select_from(ImpactReport)
        .join(Disruption, Disruption.id == ImpactReport.disruption_id)
        .join(AffectedShipment, AffectedShipment.impact_report_id == ImpactReport.id)
        .join(Shipment, Shipment.id == AffectedShipment.shipment_id)
        .join(PurchaseOrder, PurchaseOrder.id == Shipment.po_id)
        .outerjoin(Sku, Sku.id == PurchaseOrder.sku_id)
        .where(ImpactReport.generated_at >= cutoff)
        .group_by(sku_label)
        .order_by(sku_label)
    )

    # by_quarter
    quarter_label = func.to_char(Shipment.eta, 'YYYY-"Q"Q').label("label")
    quarter_stmt = (
        select(quarter_label, exposure_sum, at_risk_sum, mitigated_sum, ship_count)
        .select_from(ImpactReport)
        .join(Disruption, Disruption.id == ImpactReport.disruption_id)
        .join(AffectedShipment, AffectedShipment.impact_report_id == ImpactReport.id)
        .join(Shipment, Shipment.id == AffectedShipment.shipment_id)
        .join(PurchaseOrder, PurchaseOrder.id == Shipment.po_id)
        .where(ImpactReport.generated_at >= cutoff)
        .group_by(quarter_label)
        .order_by(quarter_label)
    )

    def _rows_to_points(rows: list[Any]) -> list[AnalyticsPoint]:
        return [
            AnalyticsPoint(
                label=str(r.label) if r.label is not None else "unknown",
                exposure=Decimal(str(r.exposure)) if r.exposure is not None else Decimal("0"),
                at_risk=Decimal(str(r.at_risk)) if r.at_risk is not None else Decimal("0"),
                mitigated=Decimal(str(r.mitigated)) if r.mitigated is not None else Decimal("0"),
                count=int(r.count) if r.count is not None else 0,
            )
            for r in rows
        ]

    cust_rows = (await session.execute(cust_stmt)).all()
    sku_rows = (await session.execute(sku_stmt)).all()
    quarter_rows = (await session.execute(quarter_stmt)).all()

    return AnalyticsSummary(
        by_customer=_rows_to_points(list(cust_rows)),
        by_sku=_rows_to_points(list(sku_rows)),
        by_quarter=_rows_to_points(list(quarter_rows)),
    )


@router.get("/exposure")
async def get_exposure(
    session: SessionDep,
    group_by: Annotated[
        GroupBy,
        Query(description="Dimension to group by: quarter, customer, or sku"),
    ],
) -> list[ExposureBucket]:
    """Return aggregated exposure bucketed by the requested dimension.

    Joins: impact_reports ⨝ affected_shipments ⨝ shipments ⨝ purchase_orders [⨝ customers].

    - quarter:  groups by TO_CHAR(shipments.eta, 'YYYY-"Q"Q'), e.g. "2026-Q2"
    - customer: groups by purchase_orders.customer_id, label is customers.name
    - sku:      groups by purchase_orders.sku_id
    """
    if group_by == "quarter":
        label_expr = func.to_char(Shipment.eta, 'YYYY-"Q"Q').label("label")

        stmt = (
            select(
                label_expr,
                func.sum(AffectedShipment.exposure).label("exposure"),
                func.sum(ImpactReport.units_at_risk).label("units"),
                func.count(func.distinct(PurchaseOrder.id)).label("pos"),
            )
            .select_from(ImpactReport)
            .join(AffectedShipment, AffectedShipment.impact_report_id == ImpactReport.id)
            .join(Shipment, Shipment.id == AffectedShipment.shipment_id)
            .join(PurchaseOrder, PurchaseOrder.id == Shipment.po_id)
            .group_by(label_expr)
            .order_by(label_expr)
        )

    elif group_by == "customer":
        cust_alias = aliased(Customer)
        label_expr = func.coalesce(cust_alias.name, PurchaseOrder.customer_id).label("label")

        stmt = (
            select(
                label_expr,
                func.sum(AffectedShipment.exposure).label("exposure"),
                func.sum(ImpactReport.units_at_risk).label("units"),
                func.count(func.distinct(PurchaseOrder.id)).label("pos"),
            )
            .select_from(ImpactReport)
            .join(AffectedShipment, AffectedShipment.impact_report_id == ImpactReport.id)
            .join(Shipment, Shipment.id == AffectedShipment.shipment_id)
            .join(PurchaseOrder, PurchaseOrder.id == Shipment.po_id)
            .outerjoin(cust_alias, cust_alias.id == PurchaseOrder.customer_id)
            .group_by(label_expr)
            .order_by(label_expr)
        )

    else:  # sku
        label_expr = PurchaseOrder.sku_id.label("label")

        stmt = (
            select(
                label_expr,
                func.sum(AffectedShipment.exposure).label("exposure"),
                func.sum(ImpactReport.units_at_risk).label("units"),
                func.count(func.distinct(PurchaseOrder.id)).label("pos"),
            )
            .select_from(ImpactReport)
            .join(AffectedShipment, AffectedShipment.impact_report_id == ImpactReport.id)
            .join(Shipment, Shipment.id == AffectedShipment.shipment_id)
            .join(PurchaseOrder, PurchaseOrder.id == Shipment.po_id)
            .group_by(label_expr)
            .order_by(label_expr)
        )

    db_result = await session.execute(stmt)
    rows = db_result.all()

    return [
        ExposureBucket(
            label=str(r.label) if r.label is not None else "unknown",
            exposure=Decimal(str(r.exposure)) if r.exposure is not None else Decimal("0"),
            units=int(r.units) if r.units is not None else 0,
            pos=int(r.pos) if r.pos is not None else 0,
        )
        for r in rows
    ]
