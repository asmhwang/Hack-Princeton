"""Typhoon-scenario seed: known-exposure ground truth for Analyst tests.

Inserts the minimum chain needed by the Analyst impact-report flow:

- two ports near Shenzhen (``PORT-SZX``, ``PORT-HKG``),
- one electronics supplier colocated at Shenzhen,
- one SKU + two customers,
- 13 purchase orders whose revenue sums to exactly ``$2,300,000``,
- 13 ``in_transit`` shipments (``SHP-T001..SHP-T013``) all origin=PORT-SZX,
- one active ``weather`` disruption centred on Shenzhen with a 400km radius.

The disruption row + ground-truth exposure are returned via
:class:`TyphoonSeed` so tests can pass the disruption id directly into
``build_impact_report`` and assert totals without re-querying the DB.

The fixture is self-contained (no reliance on the global ``seed_all``) to
keep Analyst tests independent of seed-demo evolution: if the global seed
changes its random distribution, these tests must not regress.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.models import (
    Customer,
    Disruption,
    Port,
    PurchaseOrder,
    Shipment,
    Sku,
    Supplier,
)

# ---------------------------------------------------------------------------
# Ground-truth constants (frozen — adjusting requires re-deriving test asserts)
# ---------------------------------------------------------------------------

TYPHOON_EXPOSURE_USD = Decimal("2300000")
TYPHOON_SHIPMENT_COUNT = 13
TYPHOON_DISRUPTION_CATEGORY = "weather"
TYPHOON_CENTROID = (22.5, 114.1)  # Shenzhen
TYPHOON_RADIUS_KM = Decimal("400")

# PO revenue distribution (13 values) — sums to $2,300,000 exactly.
# Ordered high → low so ORDER BY revenue DESC produces a deterministic list.
_PO_REVENUES: list[Decimal] = [
    Decimal("250000"),
    Decimal("200000"),
    Decimal("200000"),
    Decimal("200000"),
    Decimal("180000"),
    Decimal("180000"),
    Decimal("175000"),
    Decimal("175000"),
    Decimal("165000"),
    Decimal("155000"),
    Decimal("150000"),
    Decimal("150000"),
    Decimal("120000"),
]

_SHIPMENT_ID_PREFIX = "SHP-T"
_PO_ID_PREFIX = "PO-T"
_SUPPLIER_ID = "SUP-TYPHOON-1"
_SKU_ID = "SKU-TYPHOON-MCU"
_CUSTOMER_A = "CUST-TYPHOON-A"
_CUSTOMER_B = "CUST-TYPHOON-B"
_PORT_SZX = "PORT-SZX"
_PORT_HKG = "PORT-HKG"

assert sum(_PO_REVENUES) == TYPHOON_EXPOSURE_USD, (
    f"_PO_REVENUES sums to {sum(_PO_REVENUES)}, expected {TYPHOON_EXPOSURE_USD}"
)
assert len(_PO_REVENUES) == TYPHOON_SHIPMENT_COUNT


@dataclass(frozen=True)
class TyphoonSeed:
    disruption_id: uuid.UUID
    shipment_ids: list[str]
    po_ids: list[str]
    total_exposure: Decimal
    centroid: tuple[float, float]
    radius_km: Decimal


async def seed_typhoon(s: AsyncSession) -> TyphoonSeed:
    """Seed the typhoon scenario into ``s`` and return a frozen handle.

    The caller commits the session. Idempotent via ``ON CONFLICT DO NOTHING``
    on every row, so repeat calls inside the same test are safe.
    """
    today = date(2026, 4, 18)

    # Ports
    port_rows = [
        {
            "id": _PORT_SZX,
            "name": "Shenzhen",
            "country": "CN",
            "lat": Decimal("22.5"),
            "lng": Decimal("114.1"),
            "modes": ["sea"],
        },
        {
            "id": _PORT_HKG,
            "name": "Hong Kong",
            "country": "HK",
            "lat": Decimal("22.3"),
            "lng": Decimal("114.2"),
            "modes": ["sea", "air"],
        },
    ]
    await s.execute(pg_insert(Port).values(port_rows).on_conflict_do_nothing(index_elements=["id"]))

    # Supplier (electronics, near Shenzhen)
    supplier_row = {
        "id": _SUPPLIER_ID,
        "name": "Typhoon Electronics Co.",
        "country": "CN",
        "region": "Asia",
        "tier": 1,
        "industry": "electronics",
        "reliability_score": Decimal("0.92"),
        "categories": ["electronics"],
        "lat": Decimal("22.5"),
        "lng": Decimal("114.1"),
    }
    await s.execute(
        pg_insert(Supplier).values([supplier_row]).on_conflict_do_nothing(index_elements=["id"])
    )

    # SKU
    sku_row = {
        "id": _SKU_ID,
        "description": "Microcontroller, 32-bit",
        "family": "mcu",
        "industry": "electronics",
        "unit_cost": Decimal("12.50"),
        "unit_revenue": Decimal("28.00"),
    }
    await s.execute(pg_insert(Sku).values([sku_row]).on_conflict_do_nothing(index_elements=["id"]))

    # Customers (two so cascade_depth > 1 is plausible)
    customer_rows = [
        {
            "id": _CUSTOMER_A,
            "name": "Gold Customer A",
            "tier": "gold",
            "sla_days": 14,
            "contact_email": "ops@gold-a.example",
        },
        {
            "id": _CUSTOMER_B,
            "name": "Silver Customer B",
            "tier": "silver",
            "sla_days": 21,
            "contact_email": "ops@silver-b.example",
        },
    ]
    await s.execute(
        pg_insert(Customer).values(customer_rows).on_conflict_do_nothing(index_elements=["id"])
    )

    # Purchase orders — 13, revenues fixed per _PO_REVENUES, alternating customers.
    po_rows: list[dict[str, object]] = []
    po_ids: list[str] = []
    for i, revenue in enumerate(_PO_REVENUES, start=1):
        po_id = f"{_PO_ID_PREFIX}{i:03d}"
        po_ids.append(po_id)
        po_rows.append(
            {
                "id": po_id,
                "customer_id": _CUSTOMER_A if i % 2 == 1 else _CUSTOMER_B,
                "sku_id": _SKU_ID,
                "qty": 1000 * i,
                "due_date": today + timedelta(days=14),
                "revenue": revenue,
                "sla_breach_penalty": revenue * Decimal("0.05"),
            }
        )
    await s.execute(
        pg_insert(PurchaseOrder).values(po_rows).on_conflict_do_nothing(index_elements=["id"])
    )

    # Shipments — 13, all origin=SZX, all in_transit, value set from PO revenue
    # scaled down (cost basis) so PO.revenue remains the primary exposure metric.
    shipment_rows: list[dict[str, object]] = []
    shipment_ids: list[str] = []
    for i, (po_id, revenue) in enumerate(zip(po_ids, _PO_REVENUES, strict=True), start=1):
        shp_id = f"{_SHIPMENT_ID_PREFIX}{i:03d}"
        shipment_ids.append(shp_id)
        shipment_rows.append(
            {
                "id": shp_id,
                "po_id": po_id,
                "supplier_id": _SUPPLIER_ID,
                "origin_port_id": _PORT_SZX,
                "dest_port_id": _PORT_HKG,
                "status": "in_transit",
                "mode": "sea",
                "eta": today + timedelta(days=10),
                "value": (revenue * Decimal("0.6")).quantize(Decimal("0.01")),
            }
        )
    await s.execute(
        pg_insert(Shipment).values(shipment_rows).on_conflict_do_nothing(index_elements=["id"])
    )

    # Disruption (weather, active)
    disruption_id = uuid.uuid4()
    disruption_row = {
        "id": disruption_id,
        "title": "Super Typhoon Haikui — Shenzhen/Hong Kong",
        "summary": "Category 4 typhoon; 48h berth closures expected at SZX, HKG.",
        "category": TYPHOON_DISRUPTION_CATEGORY,
        "severity": 4,
        "region": "South China",
        "lat": Decimal(str(TYPHOON_CENTROID[0])),
        "lng": Decimal(str(TYPHOON_CENTROID[1])),
        "radius_km": TYPHOON_RADIUS_KM,
        "source_signal_ids": [],
        "confidence": Decimal("0.9"),
        "status": "active",
    }
    await s.execute(
        pg_insert(Disruption).values([disruption_row]).on_conflict_do_nothing(index_elements=["id"])
    )

    return TyphoonSeed(
        disruption_id=disruption_id,
        shipment_ids=shipment_ids,
        po_ids=po_ids,
        total_exposure=TYPHOON_EXPOSURE_USD,
        centroid=TYPHOON_CENTROID,
        radius_km=TYPHOON_RADIUS_KM,
    )
