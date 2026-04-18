"""Tests for backend/llm/tools/analyst_tools.py.

Seeding strategy: the conftest.py autouse fixture TRUNCATEs before every test,
so a module-scoped seed would be wiped by the second test.  We use a
function-scoped ``seeded_db`` fixture that re-seeds per test.  With 500 rows
seed_all takes < 100 ms, so the per-test cost is acceptable and isolation is
guaranteed.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.validators.sql_guard import validate_select_only
from backend.db.session import session
from backend.llm.tools._geo import haversine_km
from backend.llm.tools.analyst_tools import (
    AlternatePortsNearArgs,
    AlternateSuppliersForSkuArgs,
    CustomersByPoArgs,
    ExposureAggregateArgs,
    PurchaseOrdersForSkusArgs,
    ShipmentHistoryStatusArgs,
    ShipmentsTouchingRegionArgs,
    _alternate_ports_near,
    _alternate_suppliers_for_sku,
    _customers_by_po,
    _exposure_aggregate,
    _purchase_orders_for_skus,
    _shipment_history_status,
    _shipments_touching_region,
)
from backend.scripts.seed import seed_all

# ---------------------------------------------------------------------------
# Named constants (avoid PLR2004 magic-value lint warnings)
# ---------------------------------------------------------------------------

# Great-circle SHA→LAX bounds (km) — expected ~10,400 ± 200.
_SHA_LAX_KM_LO = 10_200
_SHA_LAX_KM_HI = 10_600

# Deterministic seed counts: SHA + NGB origins, in_transit/planned.
_SHA_500KM_COUNT = 28

# Max-results bound for alternate_suppliers test.
_ALT_SUPPLIERS_MAX = 10

# ---------------------------------------------------------------------------
# Seeded-DB fixture (function scope — see module docstring for rationale)
# ---------------------------------------------------------------------------


@pytest.fixture()
async def seeded(  # type: ignore[return]
) -> AsyncSession:
    """Yield a live async session with all seed data loaded and committed."""
    async with session() as s:
        await seed_all(s)
        await s.commit()
        yield s


# ---------------------------------------------------------------------------
# haversine_km accuracy
# ---------------------------------------------------------------------------


def test_haversine_shanghai_los_angeles() -> None:
    """Shanghai (31.2, 121.5) to Los Angeles (34.0, -118.2) ≈ 10,400 km ± 200."""
    dist = haversine_km((31.2, 121.5), (34.0, -118.2))
    assert _SHA_LAX_KM_LO <= dist <= _SHA_LAX_KM_HI, f"Unexpected distance: {dist:.1f} km"


# ---------------------------------------------------------------------------
# Tool 1 — shipments_touching_region
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_str_shanghai_500km_returns_seeded_shipments(seeded: AsyncSession) -> None:
    """Shanghai 500km radius covers PORT-SHA and PORT-NGB.
    Seed produces exactly 28 in_transit/planned shipments from those ports.
    """
    args = ShipmentsTouchingRegionArgs(radius_center=(31.2, 121.5), radius_km=500)
    result = await _shipments_touching_region(seeded, args)

    assert result["row_count"] == _SHA_500KM_COUNT
    assert len(result["rows"]) == _SHA_500KM_COUNT  # type: ignore[arg-type]
    # All returned shipments have the right status.
    rows = result["rows"]
    assert isinstance(rows, list)
    for row in rows:
        assert isinstance(row, dict)
        assert row["status"] in ("in_transit", "planned"), f"Unexpected status: {row['status']}"


@pytest.mark.asyncio
async def test_str_durban_10km_returns_only_durban_shipments(seeded: AsyncSession) -> None:
    """10 km radius around Durban (-29.9, 31.0) covers only PORT-DUR.

    Seed has exactly 13 Durban-origin in_transit/planned shipments
    (8 in_transit + 5 planned).
    """
    args = ShipmentsTouchingRegionArgs(radius_center=(-29.9, 31.0), radius_km=10)
    result = await _shipments_touching_region(seeded, args)

    rows = result["rows"]
    assert isinstance(rows, list)
    for row in rows:
        assert isinstance(row, dict)
        assert row["origin_port_id"] == "PORT-DUR"
        assert row["status"] in ("in_transit", "planned")

    # Ensure no non-Durban ports snuck in.
    port_ids = {row["origin_port_id"] for row in rows}  # type: ignore[index]
    assert port_ids == {"PORT-DUR"}


@pytest.mark.asyncio
async def test_str_radius_zero_raises_validation_error() -> None:
    """radius_km=0 violates gt=0 constraint."""
    with pytest.raises(ValidationError):
        ShipmentsTouchingRegionArgs(radius_center=(31.2, 121.5), radius_km=0)


@pytest.mark.asyncio
async def test_str_synthesized_sql_passes_guard(seeded: AsyncSession) -> None:
    """synthesized_sql must pass validate_select_only."""
    args = ShipmentsTouchingRegionArgs(radius_center=(31.2, 121.5), radius_km=500)
    result = await _shipments_touching_region(seeded, args)
    validate_select_only(str(result["synthesized_sql"]))


@pytest.mark.asyncio
async def test_str_row_count_matches_len_rows(seeded: AsyncSession) -> None:
    """row_count must equal len(rows)."""
    args = ShipmentsTouchingRegionArgs(radius_center=(31.2, 121.5), radius_km=500)
    result = await _shipments_touching_region(seeded, args)
    assert result["row_count"] == len(result["rows"])  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Tool 2 — purchase_orders_for_skus
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_po_for_existing_sku_returns_results(seeded: AsyncSession) -> None:
    """MCU-A is seeded — must return at least one PO."""
    args = PurchaseOrdersForSkusArgs(sku_ids=["MCU-A"])
    result = await _purchase_orders_for_skus(seeded, args)
    assert result["row_count"] >= 1
    rows = result["rows"]
    assert isinstance(rows, list)
    assert all(isinstance(r, dict) and r["sku_id"] == "MCU-A" for r in rows)


@pytest.mark.asyncio
async def test_po_empty_sku_ids_raises_validation_error() -> None:
    """Empty sku_ids violates min_length=1."""
    with pytest.raises(ValidationError):
        PurchaseOrdersForSkusArgs(sku_ids=[])


@pytest.mark.asyncio
async def test_po_synthesized_sql_passes_guard(seeded: AsyncSession) -> None:
    args = PurchaseOrdersForSkusArgs(sku_ids=["MCU-A", "DRAM-16"])
    result = await _purchase_orders_for_skus(seeded, args)
    validate_select_only(str(result["synthesized_sql"]))


@pytest.mark.asyncio
async def test_po_row_count_matches_len(seeded: AsyncSession) -> None:
    args = PurchaseOrdersForSkusArgs(sku_ids=["MCU-A"])
    result = await _purchase_orders_for_skus(seeded, args)
    assert result["row_count"] == len(result["rows"])  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Tool 3 — customers_by_po
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_customers_by_po_returns_distinct_rows(seeded: AsyncSession) -> None:
    """Multiple POs sharing a customer should yield that customer exactly once."""
    # Seed POs PO-00001..PO-00020 — they cycle through 20 customers.
    # Ask for the first 40 POs → guarantees each customer appears at least twice.
    po_ids = [f"PO-{i:05d}" for i in range(1, 41)]
    args = CustomersByPoArgs(po_ids=po_ids)
    result = await _customers_by_po(seeded, args)

    rows = result["rows"]
    assert isinstance(rows, list)
    # Verify distinct: no duplicate customer IDs.
    ids = [r["id"] for r in rows]  # type: ignore[index]
    assert len(ids) == len(set(ids)), "Duplicate customers returned"
    assert result["row_count"] == len(rows)


@pytest.mark.asyncio
async def test_customers_by_po_synthesized_sql_passes_guard(seeded: AsyncSession) -> None:
    args = CustomersByPoArgs(po_ids=["PO-00001", "PO-00002"])
    result = await _customers_by_po(seeded, args)
    validate_select_only(str(result["synthesized_sql"]))


# ---------------------------------------------------------------------------
# Tool 4 — exposure_aggregate
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_exposure_aggregate_returns_single_row(seeded: AsyncSession) -> None:
    """Result must be a one-element list with the 5 aggregate fields."""
    shipment_ids = [f"SHP-{i:05d}" for i in range(1, 11)]
    args = ExposureAggregateArgs(shipment_ids=shipment_ids)
    result = await _exposure_aggregate(seeded, args)

    rows = result["rows"]
    assert isinstance(rows, list)
    assert len(rows) == 1
    assert result["row_count"] == 1

    row = rows[0]
    assert isinstance(row, dict)
    for field in ("shipments", "pos", "total_revenue", "total_shipment_value", "total_units"):
        assert field in row, f"Missing aggregate field: {field}"
        assert row[field] is not None, f"Aggregate field is NULL: {field}"


@pytest.mark.asyncio
async def test_exposure_aggregate_total_revenue_positive(seeded: AsyncSession) -> None:
    shipment_ids = [f"SHP-{i:05d}" for i in range(1, 21)]
    args = ExposureAggregateArgs(shipment_ids=shipment_ids)
    result = await _exposure_aggregate(seeded, args)
    rows = result["rows"]
    assert isinstance(rows, list)
    total_revenue = float(str(rows[0]["total_revenue"]))  # type: ignore[index]
    assert total_revenue > 0


@pytest.mark.asyncio
async def test_exposure_aggregate_synthesized_sql_passes_guard(seeded: AsyncSession) -> None:
    args = ExposureAggregateArgs(shipment_ids=["SHP-00001"])
    result = await _exposure_aggregate(seeded, args)
    validate_select_only(str(result["synthesized_sql"]))


# ---------------------------------------------------------------------------
# Tool 5 — alternate_suppliers_for_sku
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_alt_suppliers_near_port_sorted_by_distance(seeded: AsyncSession) -> None:
    """With near_port_id=PORT-SHA, electronics suppliers sorted by distance_km ASC."""
    args = AlternateSuppliersForSkuArgs(
        sku_id="MCU-A",  # electronics SKU
        near_port_id="PORT-SHA",
        max_results=10,
    )
    result = await _alternate_suppliers_for_sku(seeded, args)

    rows = result["rows"]
    assert isinstance(rows, list)
    assert len(rows) <= _ALT_SUPPLIERS_MAX
    # All returned suppliers list 'electronics' in categories.
    for row in rows:
        assert isinstance(row, dict)
        cats = row.get("categories") or []
        assert "electronics" in cats, f"Non-electronics supplier returned: {row}"
    # distance_km present and sorted ASC.
    dists = [float(str(row["distance_km"])) for row in rows if row.get("distance_km") is not None]
    assert dists == sorted(dists), "Not sorted by distance ASC"


@pytest.mark.asyncio
async def test_alt_suppliers_no_port_sorted_by_reliability(seeded: AsyncSession) -> None:
    """Without near_port_id, sorted by reliability_score DESC."""
    args = AlternateSuppliersForSkuArgs(sku_id="MCU-A", max_results=15)
    result = await _alternate_suppliers_for_sku(seeded, args)

    rows = result["rows"]
    assert isinstance(rows, list)
    scores = [float(str(row["reliability_score"])) for row in rows]
    assert scores == sorted(scores, reverse=True), "Not sorted by reliability DESC"


@pytest.mark.asyncio
async def test_alt_suppliers_exclude_works(seeded: AsyncSession) -> None:
    """Excluded supplier IDs must not appear in results."""
    # Get the first result without exclusions to find a real ID to exclude.
    args_base = AlternateSuppliersForSkuArgs(sku_id="MCU-A", max_results=5)
    base_result = await _alternate_suppliers_for_sku(seeded, args_base)
    rows = base_result["rows"]
    assert isinstance(rows, list)
    assert len(rows) > 0
    exclude_id = str(rows[0]["id"])

    args_excl = AlternateSuppliersForSkuArgs(
        sku_id="MCU-A",
        exclude_supplier_ids=[exclude_id],
        max_results=15,
    )
    excl_result = await _alternate_suppliers_for_sku(seeded, args_excl)
    excl_rows = excl_result["rows"]
    assert isinstance(excl_rows, list)
    returned_ids = [r["id"] for r in excl_rows]
    assert exclude_id not in returned_ids, f"Excluded supplier {exclude_id} still in results"


@pytest.mark.asyncio
async def test_alt_suppliers_synthesized_sql_passes_guard(seeded: AsyncSession) -> None:
    args = AlternateSuppliersForSkuArgs(sku_id="MCU-A")
    result = await _alternate_suppliers_for_sku(seeded, args)
    validate_select_only(str(result["synthesized_sql"]))


# ---------------------------------------------------------------------------
# Tool 6 — alternate_ports_near
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_alt_ports_sha_2000km_returns_asian_ports(seeded: AsyncSession) -> None:
    """PORT-SHA, radius 2000 km — known Asian ports in range, LA/Rotterdam excluded."""
    args = AlternatePortsNearArgs(near_port_id="PORT-SHA", radius_km=2000)
    result = await _alternate_ports_near(seeded, args)

    rows = result["rows"]
    assert isinstance(rows, list)
    returned_ids = {r["id"] for r in rows}  # type: ignore[index]

    # Within 2000 km of SHA: NGB, PUS, ICN, KHH, SZX, HKG, YOK, TYO, MNL
    expected_nearby = {
        "PORT-NGB",
        "PORT-PUS",
        "PORT-ICN",
        "PORT-KHH",
        "PORT-SZX",
        "PORT-HKG",
        "PORT-YOK",
        "PORT-TYO",
        "PORT-MNL",
    }
    assert expected_nearby.issubset(returned_ids), (
        f"Missing expected nearby ports: {expected_nearby - returned_ids}"
    )

    # LA (~10,000 km) and Rotterdam (~9,200 km) must not appear.
    assert "PORT-LAX" not in returned_ids, "Los Angeles incorrectly included"
    assert "PORT-RTM" not in returned_ids, "Rotterdam incorrectly included"


@pytest.mark.asyncio
async def test_alt_ports_reference_not_in_results(seeded: AsyncSession) -> None:
    """Reference port itself must not appear in the results."""
    args = AlternatePortsNearArgs(near_port_id="PORT-SHA", radius_km=2000)
    result = await _alternate_ports_near(seeded, args)
    rows = result["rows"]
    assert isinstance(rows, list)
    returned_ids = [r["id"] for r in rows]
    assert "PORT-SHA" not in returned_ids, "Reference port incorrectly included in results"


@pytest.mark.asyncio
async def test_alt_ports_sorted_by_distance_asc(seeded: AsyncSession) -> None:
    """Results must be sorted by distance_km ascending."""
    args = AlternatePortsNearArgs(near_port_id="PORT-SHA", radius_km=2000)
    result = await _alternate_ports_near(seeded, args)
    rows = result["rows"]
    assert isinstance(rows, list)
    dists = [float(str(r["distance_km"])) for r in rows]
    assert dists == sorted(dists), "Not sorted by distance ASC"


@pytest.mark.asyncio
async def test_alt_ports_synthesized_sql_passes_guard(seeded: AsyncSession) -> None:
    args = AlternatePortsNearArgs(near_port_id="PORT-SHA", radius_km=500)
    result = await _alternate_ports_near(seeded, args)
    validate_select_only(str(result["synthesized_sql"]))


# ---------------------------------------------------------------------------
# Tool 7 — shipment_history_status
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_shipment_history_existing_shipment(seeded: AsyncSession) -> None:
    """Existing shipment returns compound dict with all 3 keys."""
    args = ShipmentHistoryStatusArgs(shipment_id="SHP-00001")
    result = await _shipment_history_status(seeded, args)

    rows = result["rows"]
    assert isinstance(rows, dict)
    assert "shipment" in rows
    assert "agent_log" in rows
    assert "approvals" in rows
    assert result["row_count"] == 1


@pytest.mark.asyncio
async def test_shipment_history_shipment_fields(seeded: AsyncSession) -> None:
    """Shipment sub-dict contains expected fields."""
    args = ShipmentHistoryStatusArgs(shipment_id="SHP-00001")
    result = await _shipment_history_status(seeded, args)

    rows = result["rows"]
    assert isinstance(rows, dict)
    shipment = rows["shipment"]
    assert isinstance(shipment, dict)
    assert shipment != {}, "Expected a non-empty shipment dict"
    for field in ("id", "status", "po_id", "origin_port_id", "dest_port_id"):
        assert field in shipment, f"Missing field: {field}"


@pytest.mark.asyncio
async def test_shipment_history_empty_log_in_fresh_seed(seeded: AsyncSession) -> None:
    """Fresh seeded DB has no agent_log rows — lists must be empty."""
    args = ShipmentHistoryStatusArgs(shipment_id="SHP-00001")
    result = await _shipment_history_status(seeded, args)
    rows = result["rows"]
    assert isinstance(rows, dict)
    assert isinstance(rows["agent_log"], list)
    assert isinstance(rows["approvals"], list)
    assert rows["agent_log"] == []
    assert rows["approvals"] == []


@pytest.mark.asyncio
async def test_shipment_history_synthesized_sql_passes_guard(seeded: AsyncSession) -> None:
    args = ShipmentHistoryStatusArgs(shipment_id="SHP-00001")
    result = await _shipment_history_status(seeded, args)
    validate_select_only(str(result["synthesized_sql"]))
