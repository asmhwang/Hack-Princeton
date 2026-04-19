"""Per-scenario backstop seed chain.

Inserts a deterministic Port/Supplier/SKU/Customer/3 POs/3 Shipments row set
pinned to each scenario's disruption centroid. Shared by two callers:

1. ``scripts/prime_cache.py`` — when priming the offline cache, guarantees the
   Analyst tool loop sees FK-valid shipments near the disruption regardless of
   whether the general ``seed.py`` seed has been run.
2. ``backend/api/routes/dev.py`` (``/api/dev/simulate``) — before inserting
   the scenario's Signal + Disruption rows, so demo-time cache replay finds
   the same ``SHP-PRIME-*`` IDs that were persisted at prime-time. Without
   this, the cached ``affected_shipments`` FK refs would violate at demo.

All inserts are idempotent via ``ON CONFLICT DO NOTHING``.
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.models import (
    Customer,
    Port,
    PurchaseOrder,
    Shipment,
    Sku,
    Supplier,
)
from backend.scripts.scenarios._destinations import SCENARIO_DESTINATIONS
from backend.scripts.scenarios._types import Scenario


async def seed_prime_chain(s: AsyncSession, scenario: Scenario) -> None:
    """Insert the prime-chain rows for ``scenario``. Idempotent."""
    sid = scenario.id
    port_id = f"PORT-PRIME-{sid[:6].upper()}"
    supplier_id = f"SUP-PRIME-{sid[:6].upper()}"
    sku_id = f"SKU-PRIME-{sid[:6].upper()}"
    customer_id = f"CUST-PRIME-{sid[:6].upper()}"
    po_ids = [f"PO-PRIME-{sid[:4].upper()}-{i}" for i in range(1, 4)]
    shipment_ids = [f"SHP-PRIME-{sid[:4].upper()}-{i}" for i in range(1, 4)]
    today = date(2026, 4, 18)

    # Each shipment gets its own destination port so the three lanes render
    # as three distinct arcs on the globe instead of stacking into one.
    n_ships = len(shipment_ids)
    fallback = (f"Prime-{sid}-dest", scenario.disruption.lat, scenario.disruption.lng)
    dests = list(SCENARIO_DESTINATIONS.get(sid, [fallback] * n_ships))
    while len(dests) < n_ships:
        dests.append(fallback)
    dest_port_ids = [f"PORT-PRIME-{sid[:4].upper()}-DEST-{i + 1}" for i in range(n_ships)]

    await s.execute(
        pg_insert(Port)
        .values(
            id=port_id,
            name=f"Prime-{sid}",
            country="XX",
            lat=Decimal(str(scenario.disruption.lat)),
            lng=Decimal(str(scenario.disruption.lng)),
            modes=["sea"],
        )
        .on_conflict_do_nothing()
    )
    for (dest_name, dest_lat, dest_lng), dest_port_id in zip(dests, dest_port_ids, strict=True):
        stmt = pg_insert(Port).values(
            id=dest_port_id,
            name=dest_name,
            country="XX",
            lat=Decimal(str(dest_lat)),
            lng=Decimal(str(dest_lng)),
            modes=["sea"],
        )
        # Upsert name/lat/lng so that tweaking SCENARIO_DESTINATIONS rewrites
        # the existing Port rows instead of leaving stale coordinates from an
        # earlier seed run.
        await s.execute(
            stmt.on_conflict_do_update(
                index_elements=[Port.id],
                set_={
                    "name": stmt.excluded.name,
                    "lat": stmt.excluded.lat,
                    "lng": stmt.excluded.lng,
                },
            )
        )
    await s.execute(
        pg_insert(Supplier)
        .values(
            id=supplier_id,
            name=f"Prime Supplier {sid}",
            country="XX",
            region=scenario.disruption.region,
            tier=1,
            industry="electronics",
            reliability_score=Decimal("0.9"),
            categories=["electronics"],
            lat=Decimal(str(scenario.disruption.lat)),
            lng=Decimal(str(scenario.disruption.lng)),
        )
        .on_conflict_do_nothing()
    )
    await s.execute(
        pg_insert(Sku)
        .values(
            id=sku_id,
            description=f"Prime SKU {sid}",
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
            name=f"Prime Customer {sid}",
            tier="strategic",
            sla_days=14,
            contact_email=f"{sid}@example.com",
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
                due_date=today + timedelta(days=14 + i * 7),
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
                dest_port_id=dest_port_ids[i],
                status="in_transit",
                mode="sea",
                eta=today + timedelta(days=14 + i * 7),
                value=Decimal(str(150000 * (i + 1))),
            )
            .on_conflict_do_nothing()
        )
        # Backfill legacy rows whose dest_port_id still points at the old
        # single-dest port ("...-DEST" without an index suffix). Harmless on
        # fresh installs because the UPDATE matches zero rows.
        await s.execute(
            update(Shipment)
            .where(Shipment.id == ship_id, Shipment.dest_port_id != dest_port_ids[i])
            .values(dest_port_id=dest_port_ids[i])
        )
