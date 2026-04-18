from __future__ import annotations

from decimal import Decimal
from typing import Annotated, Literal

from fastapi import APIRouter, Query
from sqlalchemy import func, select
from sqlalchemy.orm import aliased

from backend.api.deps import SessionDep
from backend.db.models import AffectedShipment, Customer, ImpactReport, PurchaseOrder, Shipment
from backend.schemas.analytics import ExposureBucket

router = APIRouter()

GroupBy = Literal["quarter", "customer", "sku"]


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
