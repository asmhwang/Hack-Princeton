from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    ARRAY,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Port(Base):
    __tablename__ = "ports"
    id: Mapped[str] = mapped_column(Text, primary_key=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    country: Mapped[str] = mapped_column(Text, nullable=False)
    lat: Mapped[float | None] = mapped_column(Numeric)
    lng: Mapped[float | None] = mapped_column(Numeric)
    modes: Mapped[list[str]] = mapped_column(ARRAY(Text), default=list)


class Supplier(Base):
    __tablename__ = "suppliers"
    id: Mapped[str] = mapped_column(Text, primary_key=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    country: Mapped[str | None] = mapped_column(Text)
    region: Mapped[str | None] = mapped_column(Text)
    tier: Mapped[int | None] = mapped_column(Integer)
    industry: Mapped[str | None] = mapped_column(Text)
    reliability_score: Mapped[Decimal | None] = mapped_column(Numeric)
    categories: Mapped[list[str]] = mapped_column(ARRAY(Text), default=list)
    lat: Mapped[float | None] = mapped_column(Numeric)
    lng: Mapped[float | None] = mapped_column(Numeric)


class Sku(Base):
    __tablename__ = "skus"
    id: Mapped[str] = mapped_column(Text, primary_key=True)
    description: Mapped[str | None] = mapped_column(Text)
    family: Mapped[str | None] = mapped_column(Text)
    industry: Mapped[str | None] = mapped_column(Text)
    unit_cost: Mapped[Decimal | None] = mapped_column(Numeric)
    unit_revenue: Mapped[Decimal | None] = mapped_column(Numeric)


class Customer(Base):
    __tablename__ = "customers"
    id: Mapped[str] = mapped_column(Text, primary_key=True)
    name: Mapped[str | None] = mapped_column(Text)
    tier: Mapped[str | None] = mapped_column(Text)
    sla_days: Mapped[int | None] = mapped_column(Integer)
    contact_email: Mapped[str | None] = mapped_column(Text)


class PurchaseOrder(Base):
    __tablename__ = "purchase_orders"
    id: Mapped[str] = mapped_column(Text, primary_key=True)
    customer_id: Mapped[str] = mapped_column(ForeignKey("customers.id"))
    sku_id: Mapped[str] = mapped_column(ForeignKey("skus.id"))
    qty: Mapped[int] = mapped_column(Integer)
    due_date: Mapped[date | None] = mapped_column(Date)
    revenue: Mapped[Decimal] = mapped_column(Numeric)
    sla_breach_penalty: Mapped[Decimal | None] = mapped_column(Numeric)


class Shipment(Base):
    __tablename__ = "shipments"
    id: Mapped[str] = mapped_column(Text, primary_key=True)
    po_id: Mapped[str] = mapped_column(ForeignKey("purchase_orders.id"))
    supplier_id: Mapped[str] = mapped_column(ForeignKey("suppliers.id"))
    origin_port_id: Mapped[str] = mapped_column(ForeignKey("ports.id"))
    dest_port_id: Mapped[str] = mapped_column(ForeignKey("ports.id"))
    status: Mapped[str] = mapped_column(Text)  # planned | in_transit | rerouting | arrived
    mode: Mapped[str | None] = mapped_column(Text)
    eta: Mapped[date | None] = mapped_column(Date)
    value: Mapped[Decimal | None] = mapped_column(Numeric)


class Signal(Base):
    __tablename__ = "signals"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source_category: Mapped[str] = mapped_column(Text)  # news|weather|policy|logistics|macro
    source_name: Mapped[str] = mapped_column(Text)
    title: Mapped[str] = mapped_column(Text)
    summary: Mapped[str | None] = mapped_column(Text)
    region: Mapped[str | None] = mapped_column(Text)
    lat: Mapped[float | None] = mapped_column(Numeric)
    lng: Mapped[float | None] = mapped_column(Numeric)
    radius_km: Mapped[Decimal | None] = mapped_column(Numeric)
    source_urls: Mapped[list[str]] = mapped_column(ARRAY(Text), default=list)
    confidence: Mapped[Decimal] = mapped_column(Numeric)
    raw_payload: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    dedupe_hash: Mapped[str] = mapped_column(Text, unique=True)
    promoted_to_disruption_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))


class Disruption(Base):
    __tablename__ = "disruptions"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title: Mapped[str] = mapped_column(Text)
    summary: Mapped[str | None] = mapped_column(Text)
    category: Mapped[str] = mapped_column(Text)
    severity: Mapped[int] = mapped_column(Integer)  # 1..5
    region: Mapped[str | None] = mapped_column(Text)
    lat: Mapped[float | None] = mapped_column(Numeric)
    lng: Mapped[float | None] = mapped_column(Numeric)
    radius_km: Mapped[Decimal | None] = mapped_column(Numeric)
    source_signal_ids: Mapped[list[uuid.UUID]] = mapped_column(ARRAY(UUID(as_uuid=True)))
    confidence: Mapped[Decimal] = mapped_column(Numeric)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    last_seen_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    status: Mapped[str] = mapped_column(Text)  # active | resolved


class ImpactReport(Base):
    __tablename__ = "impact_reports"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    disruption_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("disruptions.id"))
    total_exposure: Mapped[Decimal] = mapped_column(Numeric)
    units_at_risk: Mapped[int] = mapped_column(Integer)
    cascade_depth: Mapped[int] = mapped_column(Integer)
    sql_executed: Mapped[str | None] = mapped_column(Text)  # synthesized for explainability
    reasoning_trace: Mapped[dict[str, object]] = mapped_column(JSONB)
    generated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class AffectedShipment(Base):
    __tablename__ = "affected_shipments"
    impact_report_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("impact_reports.id"), primary_key=True
    )
    shipment_id: Mapped[str] = mapped_column(ForeignKey("shipments.id"), primary_key=True)
    exposure: Mapped[Decimal] = mapped_column(Numeric)
    days_to_sla_breach: Mapped[int | None] = mapped_column(Integer)


class MitigationOption(Base):
    __tablename__ = "mitigation_options"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    impact_report_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("impact_reports.id"))
    option_type: Mapped[str] = mapped_column(Text)  # reroute|alternate_supplier|expedite
    description: Mapped[str] = mapped_column(Text)
    delta_cost: Mapped[Decimal] = mapped_column(Numeric)
    delta_days: Mapped[int] = mapped_column(Integer)
    confidence: Mapped[Decimal] = mapped_column(Numeric)
    rationale: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text, default="pending")  # pending|approved|dismissed


class DraftCommunication(Base):
    __tablename__ = "draft_communications"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    mitigation_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("mitigation_options.id"))
    recipient_type: Mapped[str] = mapped_column(Text)  # supplier|customer|internal
    recipient_contact: Mapped[str] = mapped_column(Text)
    subject: Mapped[str] = mapped_column(Text)
    body: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    sent_at: Mapped[datetime | None] = mapped_column(DateTime)  # always NULL


class Approval(Base):
    __tablename__ = "approvals"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    mitigation_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("mitigation_options.id"))
    approved_by: Mapped[str] = mapped_column(Text)
    approved_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    state_snapshot: Mapped[dict[str, object]] = mapped_column(JSONB)


class AgentLog(Base):
    __tablename__ = "agent_log"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    agent_name: Mapped[str] = mapped_column(Text)
    trace_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    event_type: Mapped[str] = mapped_column(Text)
    payload: Mapped[dict[str, object]] = mapped_column(JSONB)
    ts: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
