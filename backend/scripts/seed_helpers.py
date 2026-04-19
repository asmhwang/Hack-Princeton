"""Shared insert helpers for deterministic demo-state seeding.

Both seed_scenario.py (active scenarios for the demo + failsafe) and
seed_history.py (resolved disruptions over the past month, so the
Analytics / Exec / Activity screens aren't empty) go through these. All
inserts use ON CONFLICT DO NOTHING so re-running is safe.

Nothing here talks to Gemini; every row is hand-tuned fixture data.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterable
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.models import (
    AffectedShipment,
    AgentLog,
    Approval,
    Customer,
    Disruption,
    DraftCommunication,
    ImpactReport,
    MitigationOption,
    Port,
    PurchaseOrder,
    Shipment,
    Signal,
    Sku,
    Supplier,
)

# ── historical prime chain (lightweight, per-slug) ───────────────────


async def seed_historical_prime_chain(
    s: AsyncSession,
    *,
    slug: str,
    region: str | None,
    lat: float,
    lng: float,
    base_date: date,
    destination_name: str,
    destination_lat: float,
    destination_lng: float,
) -> list[str]:
    """Insert a minimal Port/Supplier/SKU/Customer/3 POs/3 Shipments set for a
    historical disruption fixture. Returns the 3 shipment_ids.

    Mirrors backend/scripts/scenarios/prime_chain.py but keyed on ``slug`` (for
    historical fixtures that don't correspond to a Scenario object).
    """
    tag = slug[:6].upper()
    port_id = f"PORT-PRIME-HIST-{tag}"
    dest_port_id = f"PORT-PRIME-HIST-{tag}-DEST"
    supplier_id = f"SUP-PRIME-HIST-{tag}"
    sku_id = f"SKU-PRIME-HIST-{tag}"
    customer_id = f"CUST-PRIME-HIST-{tag}"
    po_ids = [f"PO-PRIME-HIST-{tag}-{i}" for i in range(1, 4)]
    shipment_ids = [f"SHP-PRIME-HIST-{tag}-{i}" for i in range(1, 4)]

    await s.execute(
        pg_insert(Port)
        .values(
            id=port_id,
            name=f"Prime historical {slug}",
            country="XX",
            lat=Decimal(str(lat)),
            lng=Decimal(str(lng)),
            modes=["sea"],
        )
        .on_conflict_do_nothing()
    )
    await s.execute(
        pg_insert(Port)
        .values(
            id=dest_port_id,
            name=destination_name,
            country="XX",
            lat=Decimal(str(destination_lat)),
            lng=Decimal(str(destination_lng)),
            modes=["sea"],
        )
        .on_conflict_do_nothing()
    )
    await s.execute(
        pg_insert(Supplier)
        .values(
            id=supplier_id,
            name=f"Prime historical supplier {slug}",
            country="XX",
            region=region,
            tier=1,
            industry="electronics",
            reliability_score=Decimal("0.9"),
            categories=["electronics"],
            lat=Decimal(str(lat)),
            lng=Decimal(str(lng)),
        )
        .on_conflict_do_nothing()
    )
    await s.execute(
        pg_insert(Sku)
        .values(
            id=sku_id,
            description=f"Prime historical SKU {slug}",
            family="electronics",
            industry="electronics",
            unit_cost=Decimal("10"),
            unit_revenue=Decimal("25"),
        )
        .on_conflict_do_nothing()
    )
    await s.execute(
        pg_insert(Customer)
        .values(
            id=customer_id,
            name=f"Prime historical customer {slug}",
            tier="strategic",
            sla_days=14,
            contact_email=f"hist-{slug}@example.com",
        )
        .on_conflict_do_nothing()
    )
    for i, po_id in enumerate(po_ids):
        await s.execute(
            pg_insert(PurchaseOrder)
            .values(
                id=po_id,
                customer_id=customer_id,
                sku_id=sku_id,
                qty=1000 * (i + 1),
                due_date=base_date + timedelta(days=14 + i * 7),
                revenue=Decimal(str(150000 * (i + 1))),
                sla_breach_penalty=Decimal("10000"),
            )
            .on_conflict_do_nothing()
        )
    for i, ship_id in enumerate(shipment_ids):
        await s.execute(
            pg_insert(Shipment)
            .values(
                id=ship_id,
                po_id=po_ids[i],
                supplier_id=supplier_id,
                origin_port_id=port_id,
                dest_port_id=dest_port_id,
                status="arrived",  # historical: already delivered
                mode="sea",
                eta=base_date + timedelta(days=14 + i * 7),
                value=Decimal(str(150000 * (i + 1))),
            )
            .on_conflict_do_nothing()
        )
    return shipment_ids


# ── signals + disruption ─────────────────────────────────────────────


async def insert_signal(
    s: AsyncSession,
    *,
    signal_id: uuid.UUID,
    source_category: str,
    source_name: str,
    title: str,
    summary: str | None,
    region: str | None,
    lat: float | None,
    lng: float | None,
    radius_km: float | None,
    source_urls: list[str],
    confidence: float,
    first_seen_at: datetime,
    dedupe_hash: str,
    promoted_to_disruption_id: uuid.UUID | None,
) -> None:
    await s.execute(
        pg_insert(Signal)
        .values(
            id=signal_id,
            source_category=source_category,
            source_name=source_name,
            title=title,
            summary=summary,
            region=region,
            lat=Decimal(str(lat)) if lat is not None else None,
            lng=Decimal(str(lng)) if lng is not None else None,
            radius_km=Decimal(str(radius_km)) if radius_km is not None else None,
            source_urls=source_urls,
            confidence=Decimal(str(confidence)),
            raw_payload={"seeded": True},
            first_seen_at=first_seen_at,
            dedupe_hash=dedupe_hash,
            promoted_to_disruption_id=promoted_to_disruption_id,
        )
        .on_conflict_do_nothing(index_elements=["dedupe_hash"])
    )


async def insert_disruption(
    s: AsyncSession,
    *,
    disruption_id: uuid.UUID,
    title: str,
    summary: str | None,
    category: str,
    severity: int,
    region: str | None,
    lat: float | None,
    lng: float | None,
    radius_km: float | None,
    source_signal_ids: list[uuid.UUID],
    confidence: float,
    first_seen_at: datetime,
    last_seen_at: datetime,
    status: str,
) -> None:
    await s.execute(
        pg_insert(Disruption)
        .values(
            id=disruption_id,
            title=title,
            summary=summary,
            category=category,
            severity=severity,
            region=region,
            lat=Decimal(str(lat)) if lat is not None else None,
            lng=Decimal(str(lng)) if lng is not None else None,
            radius_km=Decimal(str(radius_km)) if radius_km is not None else None,
            source_signal_ids=source_signal_ids,
            confidence=Decimal(str(confidence)),
            first_seen_at=first_seen_at,
            last_seen_at=last_seen_at,
            status=status,
        )
        .on_conflict_do_nothing(index_elements=["id"])
    )


# ── impact report + affected shipments ───────────────────────────────


async def insert_impact_report(
    s: AsyncSession,
    *,
    impact_id: uuid.UUID,
    disruption_id: uuid.UUID,
    total_exposure: Decimal,
    units_at_risk: int,
    cascade_depth: int,
    reasoning_trace: dict[str, Any],
    generated_at: datetime,
) -> None:
    sql_executed = "\n\n".join(
        str(c.get("synthesized_sql", ""))
        for c in reasoning_trace.get("tool_calls", [])
        if c.get("synthesized_sql")
    )
    await s.execute(
        pg_insert(ImpactReport)
        .values(
            id=impact_id,
            disruption_id=disruption_id,
            total_exposure=total_exposure,
            units_at_risk=units_at_risk,
            cascade_depth=cascade_depth,
            sql_executed=sql_executed,
            reasoning_trace=reasoning_trace,
            generated_at=generated_at,
        )
        .on_conflict_do_nothing(index_elements=["id"])
    )


async def insert_affected_shipments(
    s: AsyncSession,
    *,
    impact_id: uuid.UUID,
    shipments: Iterable[tuple[str, Decimal, int | None]],
) -> None:
    """Batch-insert affected_shipments rows.

    Each tuple is (shipment_id, exposure, days_to_sla_breach).
    """
    for shipment_id, exposure, days_to_sla in shipments:
        await s.execute(
            pg_insert(AffectedShipment)
            .values(
                impact_report_id=impact_id,
                shipment_id=shipment_id,
                exposure=exposure,
                days_to_sla_breach=days_to_sla,
            )
            .on_conflict_do_nothing(index_elements=["impact_report_id", "shipment_id"])
        )


# ── mitigations + drafts + approvals ─────────────────────────────────


async def insert_mitigation(
    s: AsyncSession,
    *,
    mitigation_id: uuid.UUID,
    impact_report_id: uuid.UUID,
    option_type: str,
    description: str,
    delta_cost: Decimal,
    delta_days: int,
    confidence: float,
    rationale: str,
    status: str = "pending",
) -> None:
    await s.execute(
        pg_insert(MitigationOption)
        .values(
            id=mitigation_id,
            impact_report_id=impact_report_id,
            option_type=option_type,
            description=description,
            delta_cost=delta_cost,
            delta_days=delta_days,
            confidence=Decimal(str(confidence)),
            rationale=rationale,
            status=status,
        )
        .on_conflict_do_nothing(index_elements=["id"])
    )


async def insert_draft(
    s: AsyncSession,
    *,
    draft_id: uuid.UUID,
    mitigation_id: uuid.UUID,
    recipient_type: str,
    recipient_contact: str,
    subject: str,
    body: str,
    created_at: datetime,
) -> None:
    await s.execute(
        pg_insert(DraftCommunication)
        .values(
            id=draft_id,
            mitigation_id=mitigation_id,
            recipient_type=recipient_type,
            recipient_contact=recipient_contact,
            subject=subject,
            body=body,
            created_at=created_at,
            sent_at=None,  # Always None — enforced elsewhere too.
        )
        .on_conflict_do_nothing(index_elements=["id"])
    )


async def insert_approval(
    s: AsyncSession,
    *,
    approval_id: uuid.UUID,
    mitigation_id: uuid.UUID,
    approved_by: str,
    approved_at: datetime,
    state_snapshot: dict[str, Any],
) -> None:
    await s.execute(
        pg_insert(Approval)
        .values(
            id=approval_id,
            mitigation_id=mitigation_id,
            approved_by=approved_by,
            approved_at=approved_at,
            state_snapshot=state_snapshot,
        )
        .on_conflict_do_nothing(index_elements=["id"])
    )


# ── agent log (activity feed source) ─────────────────────────────────


async def insert_agent_log(
    s: AsyncSession,
    *,
    agent_name: str,
    trace_id: uuid.UUID,
    event_type: str,
    payload: dict[str, Any],
    ts: datetime,
) -> None:
    await s.execute(
        pg_insert(AgentLog).values(
            agent_name=agent_name,
            trace_id=trace_id,
            event_type=event_type,
            payload=payload,
            ts=ts,
        )
        # id is autoincrement — no natural uniqueness to conflict on; safe to
        # re-insert duplicates across runs. If we need idempotency later, add
        # a unique (trace_id, event_type) constraint or a content-hash column.
    )


async def seed_cascade_agent_logs(
    s: AsyncSession,
    *,
    trace_id: uuid.UUID,
    disruption_id: uuid.UUID,
    impact_id: uuid.UUID,
    mitigation_ids: list[uuid.UUID],
    first_seen_at: datetime,
    total_exposure: Decimal,
) -> None:
    """Emit one realistic cascade of AgentLog entries for a disruption.

    Timeline (relative to first_seen_at):
      +0s    Scout     signal_classified
      +3s    Scout     signal_promoted_to_disruption
      +4s    Analyst   impact_analysis_started
      +14s   Analyst   impact_report_written
      +15s   Strategist option_generation_started
      +24s   Strategist options_written (N mitigations)
    """
    timeline: list[tuple[str, str, dict[str, Any], timedelta]] = [
        ("Scout", "signal_classified", {"disruption_id": str(disruption_id)}, timedelta(seconds=0)),
        (
            "Scout",
            "signal_promoted_to_disruption",
            {"disruption_id": str(disruption_id)},
            timedelta(seconds=3),
        ),
        (
            "Analyst",
            "impact_analysis_started",
            {"disruption_id": str(disruption_id)},
            timedelta(seconds=4),
        ),
        (
            "Analyst",
            "impact_report_written",
            {
                "impact_report_id": str(impact_id),
                "total_exposure": str(total_exposure),
            },
            timedelta(seconds=14),
        ),
        (
            "Strategist",
            "option_generation_started",
            {"impact_report_id": str(impact_id)},
            timedelta(seconds=15),
        ),
        (
            "Strategist",
            "options_written",
            {
                "impact_report_id": str(impact_id),
                "mitigation_ids": [str(m) for m in mitigation_ids],
                "count": len(mitigation_ids),
            },
            timedelta(seconds=24),
        ),
    ]
    for agent, event_type, payload, offset in timeline:
        await insert_agent_log(
            s,
            agent_name=agent,
            trace_id=trace_id,
            event_type=event_type,
            payload=payload,
            ts=first_seen_at + offset,
        )
