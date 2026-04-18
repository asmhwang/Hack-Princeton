"""Idempotent, deterministic seed script for suppl.ai dev/demo database.

All entities are generated from a fixed seed (random.Random(42)), so running
this script any number of times against a clean or pre-seeded DB produces
identical row counts and identical PKs.  ON CONFLICT DO NOTHING ensures
re-runs are no-ops.
"""

from __future__ import annotations

import json
import random
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

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

_SEED_DATA_DIR = Path(__file__).parent / "seed_data"

# ---------------------------------------------------------------------------
# Per-table helpers — all receive the same rng so the sequence is stable.
# ---------------------------------------------------------------------------


async def _seed_ports(s: AsyncSession) -> list[str]:
    raw = json.loads((_SEED_DATA_DIR / "ports.json").read_text())
    stmt = pg_insert(Port).values(raw).on_conflict_do_nothing(index_elements=["id"])
    await s.execute(stmt)
    return [r["id"] for r in raw]


async def _seed_suppliers(s: AsyncSession, rng: random.Random) -> list[str]:
    specs = [
        # (industry, prefix, count, countries, lats, lngs)
        (
            "electronics",
            "E",
            15,
            ["CN", "TW", "JP", "KR"],
            [22.5, 22.6, 35.7, 35.1],
            [114.1, 120.3, 139.7, 129.1],
        ),
        (
            "apparel",
            "A",
            10,
            ["VN", "TH", "MY", "BD"],
            [10.8, 13.7, 3.0, 23.7],
            [106.7, 100.5, 101.4, 90.4],
        ),
        (
            "food",
            "F",
            10,
            ["TH", "PH", "IN", "ZA"],
            [13.7, 14.6, 13.1, -29.9],
            [100.5, 120.9, 80.3, 31.0],
        ),
        (
            "pharma",
            "P",
            8,
            ["IN", "SG", "CN", "JP"],
            [18.9, 1.3, 31.2, 35.7],
            [72.8, 103.8, 121.5, 139.7],
        ),
        (
            "industrial",
            "I",
            7,
            ["JP", "KR", "US", "CN"],
            [35.4, 35.1, 29.7, 31.2],
            [139.6, 129.1, -95.3, 121.5],
        ),
    ]

    rows: list[dict] = []
    supplier_ids: list[str] = []

    for industry, prefix, count, countries, lats, lngs in specs:
        for i in range(1, count + 1):
            sid = f"SUP-{prefix}-{i:03d}"
            idx = rng.randrange(len(countries))
            rows.append(
                {
                    "id": sid,
                    "name": f"{industry.title()} Supplier {prefix}{i:03d}",
                    "country": countries[idx],
                    "region": _region_for_country(countries[idx]),
                    "tier": rng.randint(1, 3),
                    "industry": industry,
                    "reliability_score": Decimal(str(round(rng.uniform(0.55, 0.98), 2))),
                    "categories": [industry],
                    "lat": Decimal(str(round(lats[idx] + rng.uniform(-2.0, 2.0), 4))),
                    "lng": Decimal(str(round(lngs[idx] + rng.uniform(-2.0, 2.0), 4))),
                }
            )
            supplier_ids.append(sid)

    stmt = pg_insert(Supplier).values(rows).on_conflict_do_nothing(index_elements=["id"])
    await s.execute(stmt)
    return supplier_ids


def _region_for_country(cc: str) -> str:
    mapping = {
        "CN": "Asia-Pacific",
        "TW": "Asia-Pacific",
        "JP": "Asia-Pacific",
        "KR": "Asia-Pacific",
        "HK": "Asia-Pacific",
        "SG": "Asia-Pacific",
        "MY": "Asia-Pacific",
        "VN": "Asia-Pacific",
        "TH": "Asia-Pacific",
        "PH": "Asia-Pacific",
        "LK": "Asia-Pacific",
        "BD": "Asia-Pacific",
        "IN": "South Asia",
        "AE": "Middle East",
        "NL": "Europe",
        "DE": "Europe",
        "BE": "Europe",
        "GB": "Europe",
        "US": "North America",
        "CA": "North America",
        "ZA": "Africa",
    }
    return mapping.get(cc, "Other")


async def _seed_skus(s: AsyncSession, rng: random.Random) -> list[str]:
    # 8 SKUs per industry × 5 industries = 40
    definitions = [
        # electronics (8)
        ("MCU-A", "Microcontroller Unit A", "electronics", 12.50, 18.00),
        ("MCU-B", "Microcontroller Unit B", "electronics", 15.00, 22.00),
        ("PMIC-A", "Power Management IC A", "electronics", 8.00, 12.00),
        ("PMIC-B", "Power Management IC B", "electronics", 9.50, 14.00),
        ("NAND-128", "NAND Flash 128GB", "electronics", 22.00, 32.00),
        ("DRAM-16", "DRAM 16GB Module", "electronics", 45.00, 65.00),
        ("DISP-OLED", "OLED Display Panel", "electronics", 35.00, 55.00),
        ("CAM-48MP", "48MP Camera Module", "electronics", 28.00, 42.00),
        # apparel (8)
        ("APPAREL-T01", "Cotton T-Shirt S-XL", "apparel", 4.50, 12.00),
        ("APPAREL-T02", "Polyester T-Shirt S-XL", "apparel", 3.80, 10.00),
        ("APPAREL-J01", "Denim Jeans Standard", "apparel", 11.00, 28.00),
        ("APPAREL-J02", "Slim-Fit Chino", "apparel", 9.50, 25.00),
        ("APPAREL-K01", "Knit Sweater Merino", "apparel", 18.00, 50.00),
        ("APPAREL-K02", "Hoodie Fleece", "apparel", 14.00, 38.00),
        ("APPAREL-S01", "Athletic Shorts", "apparel", 6.00, 16.00),
        ("APPAREL-S02", "Compression Leggings", "apparel", 8.00, 22.00),
        # food (8)
        ("RICE-50KG", "White Rice 50 kg Bag", "food", 28.00, 38.00),
        ("WHEAT-25KG", "Wheat Flour 25 kg Bag", "food", 14.00, 20.00),
        ("SOYA-OIL-20", "Soybean Oil 20 L", "food", 22.00, 30.00),
        ("SUGAR-25KG", "Refined Sugar 25 kg", "food", 16.00, 24.00),
        ("TUNA-CAN", "Canned Tuna 185g x 48", "food", 48.00, 72.00),
        ("COFFEE-10KG", "Green Coffee Beans 10 kg", "food", 60.00, 90.00),
        ("CORN-50KG", "Yellow Corn 50 kg", "food", 18.00, 26.00),
        ("PALM-OIL-20", "Palm Oil 20 L", "food", 20.00, 28.00),
        # pharma (8)
        ("VAX-COVID", "COVID-19 Vaccine 10-dose Vial", "pharma", 8.00, 15.00),
        ("VAX-FLU", "Influenza Vaccine 10-dose", "pharma", 6.00, 12.00),
        ("API-AMOX", "Amoxicillin API 1 kg", "pharma", 120.00, 200.00),
        ("API-PARA", "Paracetamol API 1 kg", "pharma", 35.00, 60.00),
        ("SYRINGE-1ML", "Syringe 1 mL x 1000", "pharma", 18.00, 30.00),
        ("VIAL-10ML", "Sterile Vial 10 mL x 500", "pharma", 45.00, 80.00),
        ("MASK-N95", "N95 Respirator x 50", "pharma", 22.00, 40.00),
        ("GLOVES-M", "Nitrile Gloves M x 100", "pharma", 12.00, 20.00),
        # industrial (8)
        ("BEARING-X", "Ball Bearing 6204-ZZ", "industrial", 2.20, 4.50),
        ("BEARING-Y", "Tapered Roller Bearing", "industrial", 8.50, 16.00),
        ("SEAL-V", "V-Ring Seal 40mm", "industrial", 1.50, 3.20),
        ("BOLT-M12", "Hex Bolt M12 x 50 (100pc)", "industrial", 12.00, 22.00),
        ("MOTOR-0.75", "AC Induction Motor 0.75kW", "industrial", 95.00, 160.00),
        ("PUMP-CENT", "Centrifugal Pump 50L/min", "industrial", 320.00, 520.00),
        ("VALVE-BALL", "Ball Valve DN25 SS", "industrial", 28.00, 50.00),
        ("FILTER-HYD", "Hydraulic Filter Element", "industrial", 35.00, 60.00),
    ]

    rows = [
        {
            "id": sku_id,
            "description": desc,
            "family": industry,
            "industry": industry,
            "unit_cost": Decimal(str(cost)),
            "unit_revenue": Decimal(str(rev)),
        }
        for sku_id, desc, industry, cost, rev in definitions
    ]

    stmt = pg_insert(Sku).values(rows).on_conflict_do_nothing(index_elements=["id"])
    await s.execute(stmt)
    return [r["id"] for r in rows]


_CUSTOMER_NAMES = [
    "ApexTech",
    "BlueCrest",
    "ClearPath",
    "DeltaOps",
    "EverFlow",
    "FrontEdge",
    "GlobalNex",
    "HighMark",
    "IronBridge",
    "JetStream",
    "KineticPro",
    "LumenCore",
    "MeridiaCo",
    "NorthAxis",
    "OpenValve",
    "PeakForce",
    "QuantumOps",
    "RioVerde",
    "SkyBridge",
    "TitanLink",
]

_TIERS = ["Strategic"] * 5 + ["Gold"] * 7 + ["Standard"] * 8

_SLA_DAYS_BY_TIER = {"Strategic": (30, 45), "Gold": (45, 75), "Standard": (75, 120)}


async def _seed_customers(s: AsyncSession, rng: random.Random) -> list[str]:
    rows = []
    customer_ids = []
    for i, name in enumerate(_CUSTOMER_NAMES, start=1):
        cid = f"CUST-{i:03d}"
        tier = _TIERS[i - 1]
        lo, hi = _SLA_DAYS_BY_TIER[tier]
        rows.append(
            {
                "id": cid,
                "name": name,
                "tier": tier,
                "sla_days": rng.randint(lo, hi),
                "contact_email": f"ops@{name.lower()}.example.com",
            }
        )
        customer_ids.append(cid)

    stmt = pg_insert(Customer).values(rows).on_conflict_do_nothing(index_elements=["id"])
    await s.execute(stmt)
    return customer_ids


async def _seed_purchase_orders(
    s: AsyncSession,
    rng: random.Random,
    customer_ids: list[str],
    sku_ids: list[str],
) -> list[str]:
    today = date(2026, 4, 18)  # fixed reference date for determinism
    rows = []
    po_ids = []

    for i in range(1, 201):
        po_id = f"PO-{i:05d}"
        cust = customer_ids[(i - 1) % len(customer_ids)]
        sku = sku_ids[(i - 1) % len(sku_ids)]
        qty = rng.randint(10, 2000)
        revenue = Decimal(str(round(rng.uniform(10_000, 300_000), 2)))
        penalty_pct = Decimal(str(round(rng.uniform(0.05, 0.15), 4)))
        due_offset = rng.randint(15, 180)
        rows.append(
            {
                "id": po_id,
                "customer_id": cust,
                "sku_id": sku,
                "qty": qty,
                "due_date": today + timedelta(days=due_offset),
                "revenue": revenue,
                "sla_breach_penalty": (revenue * penalty_pct).quantize(Decimal("0.01")),
            }
        )
        po_ids.append(po_id)

    stmt = pg_insert(PurchaseOrder).values(rows).on_conflict_do_nothing(index_elements=["id"])
    await s.execute(stmt)
    return po_ids


def _sku_industry(sku_id: str) -> str:
    prefixes = {
        "MCU": "electronics",
        "PMIC": "electronics",
        "NAND": "electronics",
        "DRAM": "electronics",
        "DISP": "electronics",
        "CAM": "electronics",
        "APPAREL": "apparel",
        "RICE": "food",
        "WHEAT": "food",
        "SOYA": "food",
        "SUGAR": "food",
        "TUNA": "food",
        "COFFEE": "food",
        "CORN": "food",
        "PALM": "food",
        "VAX": "pharma",
        "API": "pharma",
        "SYRINGE": "pharma",
        "VIAL": "pharma",
        "MASK": "pharma",
        "GLOVES": "pharma",
        "BEARING": "industrial",
        "SEAL": "industrial",
        "BOLT": "industrial",
        "MOTOR": "industrial",
        "PUMP": "industrial",
        "VALVE": "industrial",
        "FILTER": "industrial",
    }
    for prefix, ind in prefixes.items():
        if sku_id.startswith(prefix):
            return ind
    return "electronics"


async def _seed_shipments(
    s: AsyncSession,
    rng: random.Random,
    po_ids: list[str],
    supplier_ids: list[str],
    port_ids: list[str],
    sku_ids: list[str],
) -> None:
    today = date(2026, 4, 18)

    # Build industry → supplier index for coherent matching
    industry_suppliers: dict[str, list[str]] = {}
    # specs order: electronics(15), apparel(10), food(10), pharma(8), industrial(7)
    industry_order = ["electronics", "apparel", "food", "pharma", "industrial"]
    counts = [15, 10, 10, 8, 7]
    idx = 0
    for ind, cnt in zip(industry_order, counts, strict=True):
        industry_suppliers[ind] = supplier_ids[idx : idx + cnt]
        idx += cnt

    # PO index → sku_id (round-robin matches seed_purchase_orders)
    po_sku = {po_ids[i]: sku_ids[i % len(sku_ids)] for i in range(len(po_ids))}

    # Status thresholds: 1-300 → in_transit, 301-400 → planned, 401-500 → arrived
    IN_TRANSIT_THRESHOLD = 300
    PLANNED_THRESHOLD = 400
    TOTAL_SHIPMENTS = 500

    rows = []
    for i in range(1, TOTAL_SHIPMENTS + 1):
        shp_id = f"SHP-{i:05d}"
        if i <= IN_TRANSIT_THRESHOLD:
            status = "in_transit"
            eta_offset = rng.randint(1, 60)
        elif i <= PLANNED_THRESHOLD:
            status = "planned"
            eta_offset = rng.randint(30, 120)
        else:
            status = "arrived"
            eta_offset = -rng.randint(1, 30)

        po_id = po_ids[(i - 1) % len(po_ids)]
        sku_id = po_sku[po_id]
        industry = _sku_industry(sku_id)
        sup_candidates = industry_suppliers.get(industry, supplier_ids)
        supplier_id = rng.choice(sup_candidates)

        # Distinct origin / destination ports
        origin_idx, dest_idx = rng.sample(range(len(port_ids)), 2)

        rows.append(
            {
                "id": shp_id,
                "po_id": po_id,
                "supplier_id": supplier_id,
                "origin_port_id": port_ids[origin_idx],
                "dest_port_id": port_ids[dest_idx],
                "status": status,
                "mode": "sea",
                "eta": today + timedelta(days=eta_offset),
                "value": Decimal(str(round(rng.uniform(5_000, 150_000), 2))),
            }
        )

    stmt = pg_insert(Shipment).values(rows).on_conflict_do_nothing(index_elements=["id"])
    await s.execute(stmt)


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


async def seed_all(s: AsyncSession) -> None:
    """Insert all seed data idempotently.  Callers must commit the session."""
    rng = random.Random(42)

    port_ids = await _seed_ports(s)
    supplier_ids = await _seed_suppliers(s, rng)
    sku_ids = await _seed_skus(s, rng)
    customer_ids = await _seed_customers(s, rng)
    po_ids = await _seed_purchase_orders(s, rng, customer_ids, sku_ids)
    await _seed_shipments(s, rng, po_ids, supplier_ids, port_ids, sku_ids)


# ---------------------------------------------------------------------------
# CLI entry
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import asyncio

    from backend.db.session import session

    async def _main() -> None:
        async with session() as s:
            await seed_all(s)
            await s.commit()
        print("Seed complete.")

    asyncio.run(_main())
