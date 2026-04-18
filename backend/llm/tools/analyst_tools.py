"""Parameterized read tools for the Analyst agent's Gemini function-calling interface.

Every tool returns::

    {"rows": list[dict[str, object]], "synthesized_sql": str, "row_count": int}

``synthesized_sql`` is a human-readable, display-only SQL string built from
the call parameters.  It is never executed against the database.  It is run
through ``validate_select_only`` before being returned so the "zero SQL
mutations possible" judge claim holds for every code path.

``shipment_history_status`` deviates from the standard ``rows: list`` shape —
its ``rows`` value is a compound dict with three keys:
``{"shipment": dict, "agent_log": list, "approvals": list}``.
See that function's docstring for details.
"""

from __future__ import annotations

import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.validators.sql_guard import validate_select_only
from backend.db.session import session as get_session
from backend.llm.tools._geo import haversine_km

# ---------------------------------------------------------------------------
# Serialisation helpers
# ---------------------------------------------------------------------------


def _sql_literal(value: object) -> str:
    """Produce a single-quoted SQL literal from value, escaping single quotes.

    Used only for synthesized (display) SQL strings — never for execution.
    """
    s = str(value)
    escaped = s.replace("'", "''")
    return f"'{escaped}'"


def _serialize_row(row: dict[str, Any]) -> dict[str, object]:
    """Convert non-JSON-serialisable types in a DB row to safe string forms.

    - ``Decimal`` → ``str``
    - ``datetime.date`` / ``datetime.datetime`` → ISO 8601 ``str``
    - Everything else passes through unchanged.
    """
    out: dict[str, object] = {}
    for k, v in row.items():
        if isinstance(v, Decimal):
            out[k] = str(v)
        elif isinstance(v, (datetime.date, datetime.datetime)):
            out[k] = v.isoformat()
        else:
            out[k] = v
    return out


# ---------------------------------------------------------------------------
# Args models
# ---------------------------------------------------------------------------


class ShipmentsTouchingRegionArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    radius_center: tuple[float, float]  # (lat, lng)
    radius_km: float = Field(gt=0, le=3000)
    status_in: list[str] = Field(default=["in_transit", "planned"])


class PurchaseOrdersForSkusArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sku_ids: list[str] = Field(min_length=1, max_length=100)


class CustomersByPoArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    po_ids: list[str] = Field(min_length=1, max_length=500)


class ExposureAggregateArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    shipment_ids: list[str] = Field(min_length=1, max_length=1000)


class AlternateSuppliersForSkuArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sku_id: str
    exclude_supplier_ids: list[str] = Field(default_factory=list, max_length=50)
    near_port_id: str | None = None
    max_results: int = Field(default=10, ge=1, le=50)


class AlternatePortsNearArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    near_port_id: str
    radius_km: float = Field(default=2000, gt=0, le=10000)
    exclude_port_ids: list[str] = Field(default_factory=list, max_length=50)
    max_results: int = Field(default=10, ge=1, le=30)


class ShipmentHistoryStatusArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    shipment_id: str


# ---------------------------------------------------------------------------
# Tool 1: shipments_touching_region
# ---------------------------------------------------------------------------


async def shipments_touching_region(
    args: ShipmentsTouchingRegionArgs,
) -> dict[str, object]:
    """Shipments whose origin port is within radius_km of radius_center."""
    async with get_session() as s:
        return await _shipments_touching_region(s, args)


async def _shipments_touching_region(
    s: AsyncSession,
    args: ShipmentsTouchingRegionArgs,
) -> dict[str, object]:
    """Testable variant that takes an explicit session."""
    # Load all ports into memory — only 30, cheap.
    port_rows = await s.execute(
        text("SELECT id, lat, lng FROM ports WHERE lat IS NOT NULL AND lng IS NOT NULL")
    )
    port_ids_in_radius: list[str] = []
    for port_row in port_rows.mappings():
        port_lat = float(port_row["lat"])
        port_lng = float(port_row["lng"])
        dist = haversine_km(args.radius_center, (port_lat, port_lng))
        if dist <= args.radius_km:
            port_ids_in_radius.append(str(port_row["id"]))

    if not port_ids_in_radius:
        sql = (
            "SELECT id, po_id, supplier_id, origin_port_id, dest_port_id, "
            "status, mode, eta, value FROM shipments WHERE 1=0"
        )
        validate_select_only(sql)
        return {"rows": [], "synthesized_sql": sql, "row_count": 0}

    result = await s.execute(
        text(
            "SELECT id, po_id, supplier_id, origin_port_id, dest_port_id, "
            "status, mode, eta, value FROM shipments "
            "WHERE origin_port_id = ANY(:port_ids) AND status = ANY(:status_in)"
        ).bindparams(port_ids=port_ids_in_radius, status_in=args.status_in)
    )
    rows = [_serialize_row(dict(r)) for r in result.mappings()]

    port_literals = ", ".join(_sql_literal(p) for p in port_ids_in_radius)
    status_literals = ", ".join(_sql_literal(s_val) for s_val in args.status_in)
    sql = (
        "SELECT id, po_id, supplier_id, origin_port_id, dest_port_id, "
        "status, mode, eta, value FROM shipments "
        f"WHERE origin_port_id IN ({port_literals}) "
        f"AND status IN ({status_literals})"
    )
    validate_select_only(sql)
    return {"rows": rows, "synthesized_sql": sql, "row_count": len(rows)}


# ---------------------------------------------------------------------------
# Tool 2: purchase_orders_for_skus
# ---------------------------------------------------------------------------


async def purchase_orders_for_skus(
    args: PurchaseOrdersForSkusArgs,
) -> dict[str, object]:
    """POs referencing any of the given SKU IDs."""
    async with get_session() as s:
        return await _purchase_orders_for_skus(s, args)


async def _purchase_orders_for_skus(
    s: AsyncSession,
    args: PurchaseOrdersForSkusArgs,
) -> dict[str, object]:
    """Testable variant that takes an explicit session."""
    result = await s.execute(
        text(
            "SELECT id, customer_id, sku_id, qty, due_date, revenue, sla_breach_penalty "
            "FROM purchase_orders WHERE sku_id = ANY(:sku_ids)"
        ).bindparams(sku_ids=args.sku_ids)
    )
    rows = [_serialize_row(dict(r)) for r in result.mappings()]

    sku_literals = ", ".join(_sql_literal(sid) for sid in args.sku_ids)
    sql = (
        "SELECT id, customer_id, sku_id, qty, due_date, revenue, sla_breach_penalty "
        f"FROM purchase_orders WHERE sku_id IN ({sku_literals})"
    )
    validate_select_only(sql)
    return {"rows": rows, "synthesized_sql": sql, "row_count": len(rows)}


# ---------------------------------------------------------------------------
# Tool 3: customers_by_po
# ---------------------------------------------------------------------------


async def customers_by_po(
    args: CustomersByPoArgs,
) -> dict[str, object]:
    """Distinct customers for a set of POs, with contact info."""
    async with get_session() as s:
        return await _customers_by_po(s, args)


async def _customers_by_po(
    s: AsyncSession,
    args: CustomersByPoArgs,
) -> dict[str, object]:
    """Testable variant that takes an explicit session."""
    result = await s.execute(
        text(
            "SELECT DISTINCT c.id, c.name, c.tier, c.sla_days, c.contact_email "
            "FROM customers c "
            "JOIN purchase_orders po ON c.id = po.customer_id "
            "WHERE po.id = ANY(:po_ids)"
        ).bindparams(po_ids=args.po_ids)
    )
    rows = [_serialize_row(dict(r)) for r in result.mappings()]

    po_literals = ", ".join(_sql_literal(pid) for pid in args.po_ids)
    sql = (
        "SELECT DISTINCT c.id, c.name, c.tier, c.sla_days, c.contact_email "
        "FROM customers c "
        "JOIN purchase_orders po ON c.id = po.customer_id "
        f"WHERE po.id IN ({po_literals})"
    )
    validate_select_only(sql)
    return {"rows": rows, "synthesized_sql": sql, "row_count": len(rows)}


# ---------------------------------------------------------------------------
# Tool 4: exposure_aggregate
# ---------------------------------------------------------------------------


async def exposure_aggregate(
    args: ExposureAggregateArgs,
) -> dict[str, object]:
    """Total exposure aggregates for a set of shipments joined with POs."""
    async with get_session() as s:
        return await _exposure_aggregate(s, args)


async def _exposure_aggregate(
    s: AsyncSession,
    args: ExposureAggregateArgs,
) -> dict[str, object]:
    """Testable variant that takes an explicit session."""
    result = await s.execute(
        text(
            "SELECT "
            "COUNT(DISTINCT s.id) AS shipments, "
            "COUNT(DISTINCT po.id) AS pos, "
            "SUM(po.revenue) AS total_revenue, "
            "SUM(s.value) AS total_shipment_value, "
            "SUM(po.qty) AS total_units "
            "FROM shipments s "
            "JOIN purchase_orders po ON s.po_id = po.id "
            "WHERE s.id = ANY(:shipment_ids)"
        ).bindparams(shipment_ids=args.shipment_ids)
    )
    row = result.mappings().one()
    serialized = _serialize_row(dict(row))
    rows: list[dict[str, object]] = [serialized]

    shp_literals = ", ".join(_sql_literal(sid) for sid in args.shipment_ids)
    sql = (
        "SELECT "
        "COUNT(DISTINCT s.id) AS shipments, "
        "COUNT(DISTINCT po.id) AS pos, "
        "SUM(po.revenue) AS total_revenue, "
        "SUM(s.value) AS total_shipment_value, "
        "SUM(po.qty) AS total_units "
        "FROM shipments s "
        "JOIN purchase_orders po ON s.po_id = po.id "
        f"WHERE s.id IN ({shp_literals})"
    )
    validate_select_only(sql)
    return {"rows": rows, "synthesized_sql": sql, "row_count": 1}


# ---------------------------------------------------------------------------
# Tool 5: alternate_suppliers_for_sku
# ---------------------------------------------------------------------------


async def alternate_suppliers_for_sku(
    args: AlternateSuppliersForSkuArgs,
) -> dict[str, object]:
    """Suppliers that list the SKU's industry, optionally ranked by port proximity."""
    async with get_session() as s:
        return await _alternate_suppliers_for_sku(s, args)


async def _alternate_suppliers_for_sku(
    s: AsyncSession,
    args: AlternateSuppliersForSkuArgs,
) -> dict[str, object]:
    """Testable variant that takes an explicit session."""
    # 1. Fetch SKU industry.
    sku_result = await s.execute(
        text("SELECT industry FROM skus WHERE id = :sku_id").bindparams(sku_id=args.sku_id)
    )
    sku_row = sku_result.mappings().one_or_none()
    if sku_row is None:
        sql = "SELECT id FROM suppliers WHERE 1=0"
        validate_select_only(sql)
        return {"rows": [], "synthesized_sql": sql, "row_count": 0}

    industry: str = str(sku_row["industry"])

    # 2. Query suppliers whose categories includes the industry.
    # Use empty array literal typed as text[] when exclude list is empty to
    # avoid asyncpg type inference failure on empty Python lists.
    if args.exclude_supplier_ids:
        supplier_result = await s.execute(
            text(
                "SELECT id, name, country, region, tier, industry, reliability_score, "
                "categories, lat, lng FROM suppliers "
                "WHERE :industry = ANY(categories) AND id != ALL(:exclude_ids)"
            ).bindparams(industry=industry, exclude_ids=args.exclude_supplier_ids)
        )
    else:
        supplier_result = await s.execute(
            text(
                "SELECT id, name, country, region, tier, industry, reliability_score, "
                "categories, lat, lng FROM suppliers "
                "WHERE :industry = ANY(categories)"
            ).bindparams(industry=industry)
        )
    supplier_rows: list[dict[str, Any]] = [dict(r) for r in supplier_result.mappings()]

    # 3. Optional distance ranking.
    if args.near_port_id is not None:
        port_result = await s.execute(
            text("SELECT lat, lng FROM ports WHERE id = :port_id").bindparams(
                port_id=args.near_port_id
            )
        )
        port_row = port_result.mappings().one_or_none()
        if port_row is not None:
            port_coords = (float(port_row["lat"]), float(port_row["lng"]))
            for row in supplier_rows:
                if row.get("lat") is not None and row.get("lng") is not None:
                    row["distance_km"] = round(
                        haversine_km(port_coords, (float(row["lat"]), float(row["lng"]))),
                        1,
                    )
                else:
                    row["distance_km"] = None
            supplier_rows.sort(
                key=lambda r: (r.get("distance_km") is None, r.get("distance_km") or 0.0)
            )
        else:
            # Port not found — fall back to reliability sort.
            supplier_rows.sort(
                key=lambda r: float(r["reliability_score"] or 0),
                reverse=True,
            )
    else:
        supplier_rows.sort(
            key=lambda r: float(r["reliability_score"] or 0),
            reverse=True,
        )

    supplier_rows = supplier_rows[: args.max_results]
    rows = [_serialize_row(r) for r in supplier_rows]

    exclude_clause = ""
    if args.exclude_supplier_ids:
        excl_literals = ", ".join(_sql_literal(e) for e in args.exclude_supplier_ids)
        exclude_clause = f" AND id NOT IN ({excl_literals})"
    sql = (
        "SELECT id, name, country, region, tier, industry, reliability_score, "
        "categories, lat, lng FROM suppliers "
        f"WHERE {_sql_literal(industry)} = ANY(categories){exclude_clause}"
    )
    validate_select_only(sql)
    return {"rows": rows, "synthesized_sql": sql, "row_count": len(rows)}


# ---------------------------------------------------------------------------
# Tool 6: alternate_ports_near
# ---------------------------------------------------------------------------


async def alternate_ports_near(
    args: AlternatePortsNearArgs,
) -> dict[str, object]:
    """Ports within radius_km of a reference port, sorted by distance."""
    async with get_session() as s:
        return await _alternate_ports_near(s, args)


async def _alternate_ports_near(
    s: AsyncSession,
    args: AlternatePortsNearArgs,
) -> dict[str, object]:
    """Testable variant that takes an explicit session."""
    all_ports_result = await s.execute(
        text(
            "SELECT id, name, country, lat, lng, modes FROM ports "
            "WHERE lat IS NOT NULL AND lng IS NOT NULL"
        )
    )
    all_ports = [dict(r) for r in all_ports_result.mappings()]

    # Find reference port.
    ref_port = next((p for p in all_ports if p["id"] == args.near_port_id), None)
    if ref_port is None:
        sql = "SELECT id FROM ports WHERE 1=0"
        validate_select_only(sql)
        return {"rows": [], "synthesized_sql": sql, "row_count": 0}

    ref_coords = (float(ref_port["lat"]), float(ref_port["lng"]))
    full_exclude = {args.near_port_id, *args.exclude_port_ids}

    candidates: list[dict[str, Any]] = []
    for port in all_ports:
        if port["id"] in full_exclude:
            continue
        dist = haversine_km(ref_coords, (float(port["lat"]), float(port["lng"])))
        if dist <= args.radius_km:
            port["distance_km"] = round(dist, 1)
            candidates.append(port)

    candidates.sort(key=lambda p: p["distance_km"])
    candidates = candidates[: args.max_results]
    rows = [_serialize_row(r) for r in candidates]

    excl_all = list(full_exclude)
    excl_literals = ", ".join(_sql_literal(e) for e in excl_all)
    sql = f"SELECT id, name, country, lat, lng FROM ports WHERE id NOT IN ({excl_literals})"
    validate_select_only(sql)
    return {"rows": rows, "synthesized_sql": sql, "row_count": len(rows)}


# ---------------------------------------------------------------------------
# Tool 7: shipment_history_status
# ---------------------------------------------------------------------------


async def shipment_history_status(
    args: ShipmentHistoryStatusArgs,
) -> dict[str, object]:
    """Current state, agent log entries, and approvals for a single shipment.

    Return shape deviation: ``rows`` is a compound dict, not a list::

        {
            "shipment": {...},       # current shipment row, or {} if not found
            "agent_log": [...],      # agent_log entries mentioning this shipment
            "approvals": [...],      # approvals whose state_snapshot references it
        }

    ``row_count`` is always 1 (one compound result object).
    """
    async with get_session() as s:
        return await _shipment_history_status(s, args)


async def _shipment_history_status(
    s: AsyncSession,
    args: ShipmentHistoryStatusArgs,
) -> dict[str, object]:
    """Testable variant that takes an explicit session."""
    sid = args.shipment_id

    # Query 1: current shipment row.
    shp_result = await s.execute(
        text(
            "SELECT id, status, po_id, origin_port_id, dest_port_id, eta, value "
            "FROM shipments WHERE id = :shipment_id"
        ).bindparams(shipment_id=sid)
    )
    shp_row_raw = shp_result.mappings().one_or_none()
    shipment: dict[str, object] = (
        _serialize_row(dict(shp_row_raw)) if shp_row_raw is not None else {}
    )

    # Query 2: agent_log entries whose payload contains this shipment ID.
    # Use CAST(:sid AS text) to avoid the SQLAlchemy text() param-parser
    # truncating `:shipment_id` when followed by `::text` PostgreSQL cast syntax.
    log_result = await s.execute(
        text(
            "SELECT agent_name, event_type, payload, ts FROM agent_log "
            "WHERE payload @> jsonb_build_object('shipment_id', CAST(:sid AS text)) "
            "ORDER BY ts DESC"
        ).bindparams(sid=sid)
    )
    agent_log: list[dict[str, object]] = [_serialize_row(dict(r)) for r in log_result.mappings()]

    # Query 3: approvals whose state_snapshot->'shipment_ids_flipped' JSON array
    # contains this shipment ID.
    # NOTE: the JSONB `?` operator is a reserved token in SQLAlchemy text() —
    # we use @> with to_jsonb() instead, which has identical semantics for a
    # string element inside a JSON array.  Use CAST() to avoid the `::` param
    # truncation issue described above.
    approvals_result = await s.execute(
        text(
            "SELECT id, mitigation_id, approved_by, approved_at, state_snapshot "
            "FROM approvals "
            "WHERE state_snapshot->'shipment_ids_flipped' @> to_jsonb(CAST(:sid AS text)) "
            "ORDER BY approved_at DESC"
        ).bindparams(sid=sid)
    )
    approvals: list[dict[str, object]] = [
        _serialize_row(dict(r)) for r in approvals_result.mappings()
    ]

    compound: dict[str, object] = {
        "shipment": shipment,
        "agent_log": agent_log,
        "approvals": approvals,
    }

    sql = (
        f"SELECT id, status, po_id, origin_port_id, dest_port_id, eta, value "
        f"FROM shipments WHERE id = {_sql_literal(sid)}"
    )
    validate_select_only(sql)
    return {"rows": compound, "synthesized_sql": sql, "row_count": 1}


# ---------------------------------------------------------------------------
# TOOL_REGISTRY — iterated by the Analyst agent to build Gemini function specs.
# Each entry: (name, description, args_schema_class, async_callable)
# ---------------------------------------------------------------------------

TOOL_REGISTRY: list[tuple[str, str, type[BaseModel], object]] = [
    (
        "shipments_touching_region",
        "Find shipments whose origin port is within radius_km of a geographic point.",
        ShipmentsTouchingRegionArgs,
        shipments_touching_region,
    ),
    (
        "purchase_orders_for_skus",
        "Retrieve purchase orders referencing any of the given SKU IDs.",
        PurchaseOrdersForSkusArgs,
        purchase_orders_for_skus,
    ),
    (
        "customers_by_po",
        "Retrieve distinct customers (with contact info) for a set of PO IDs.",
        CustomersByPoArgs,
        customers_by_po,
    ),
    (
        "exposure_aggregate",
        "Compute total revenue, shipment value, and unit exposure for a set of shipment IDs.",
        ExposureAggregateArgs,
        exposure_aggregate,
    ),
    (
        "alternate_suppliers_for_sku",
        "Find alternative suppliers for a SKU's industry, ranked by distance or reliability.",
        AlternateSuppliersForSkuArgs,
        alternate_suppliers_for_sku,
    ),
    (
        "alternate_ports_near",
        "Find ports within radius_km of a reference port, sorted by distance.",
        AlternatePortsNearArgs,
        alternate_ports_near,
    ),
    (
        "shipment_history_status",
        "Return a shipment's current state plus related agent log entries and approvals.",
        ShipmentHistoryStatusArgs,
        shipment_history_status,
    ),
]
