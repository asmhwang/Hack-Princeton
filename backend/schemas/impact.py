from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class AffectedShipmentEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    shipment_id: str
    exposure: Decimal
    days_to_sla_breach: int | None
    # Optional enrichments populated by the /disruptions/{id}/impact route by
    # JOINing shipments → purchase_orders → customers / skus / ports. The
    # Analyst's raw write path leaves these as None; read endpoints fill them.
    sku: str | None = None
    customer_name: str | None = None
    po_number: str | None = None
    origin: str | None = None
    destination: str | None = None
    status: str | None = None
    eta: str | None = None
    origin_lat: float | None = None
    origin_lng: float | None = None
    destination_lat: float | None = None
    destination_lng: float | None = None


class ToolInvocation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tool_name: str
    args: dict[str, object]
    row_count: int
    synthesized_sql: str


class ReasoningTrace(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tool_calls: list[ToolInvocation]
    final_reasoning: str


class ImpactReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    disruption_id: uuid.UUID
    total_exposure: Decimal
    units_at_risk: int
    cascade_depth: int = Field(ge=1, le=5)
    sql_executed: str
    reasoning_trace: ReasoningTrace
    affected_shipments: list[AffectedShipmentEntry] = Field(min_length=1)


class ImpactReportRecord(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid")

    id: uuid.UUID
    disruption_id: uuid.UUID
    total_exposure: Decimal
    units_at_risk: int
    cascade_depth: int
    sql_executed: str | None
    reasoning_trace: ReasoningTrace
    generated_at: datetime


class ImpactReportWithShipments(BaseModel):
    """ImpactReportRecord extended with its affected shipments list."""

    model_config = ConfigDict(extra="forbid")

    id: uuid.UUID
    disruption_id: uuid.UUID
    total_exposure: Decimal
    units_at_risk: int
    cascade_depth: int
    sql_executed: str | None
    reasoning_trace: ReasoningTrace
    generated_at: datetime
    affected_shipments: list[AffectedShipmentEntry]
