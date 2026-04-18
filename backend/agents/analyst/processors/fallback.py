"""Rules-based fallback impact-report builder — no LLM in the hot path.

When the Gemini tool-call loop in
:func:`backend.agents.analyst.processors.impact.build_impact_report` raises
:class:`backend.llm.client.LLMValidationError` (bad JSON, exceeded
``max_iters``, etc.), the agent must still write an ``impact_reports`` row and
fire ``NOTIFY new_impact`` — the downstream Strategist subscribes to that
channel and would otherwise stall waiting on the dead disruption.

``build_impact_report_fallback`` dispatches by
``disruption.category``:

- ``weather``: proximity chain — ``shipments_touching_region`` →
  ``exposure_aggregate`` (optionally ``alternate_ports_near`` when the
  centroid matches a known port).
- ``policy``: no structured SKU-family hook on the disruption row yet →
  currently degrades to the weather radius chain; recoverability is
  annotated in ``final_reasoning`` so the UI surfaces lower confidence.
- ``logistics`` / ``labor``: proximity chain (the disruption centroid is the
  port's coordinates) — identical shape to ``weather``.
- ``macro``: freight-rate proxy — flag all ``in_transit`` shipments as
  exposed to a generic delta and emit a low-confidence ``cascade_depth=1``
  report.
- anything else: weather radius chain if lat/lng/radius are present; empty
  report otherwise.

Every path produces the same ``ImpactReport`` pydantic shape and persists via
the shared helpers in :mod:`backend.agents.analyst.processors.impact` so the
row layout, NOTIFY payload, and SQL-guard defense-in-depth are identical to
the LLM path.
"""

from __future__ import annotations

import json
import uuid
from decimal import Decimal
from typing import Any, Protocol

import structlog
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from backend.agents.analyst.processors.impact import (
    DisruptionNotFoundError,
    _as_decimal,
    _concat_sql,
    _existing_impact_id,
    _load_disruption,
    _persist,
    _trace_to_schema,
)
from backend.db.models import Disruption
from backend.db.session import session as default_session
from backend.llm.client import ToolInvocation
from backend.llm.tools.analyst_tools import (
    ExposureAggregateArgs,
    ShipmentsTouchingRegionArgs,
    _exposure_aggregate,
    _shipments_touching_region,
)
from backend.schemas.impact import (
    AffectedShipmentEntry,
    ImpactReport,
    ReasoningTrace,
)

log = structlog.get_logger()

_FALLBACK_MARKER = "[source=fallback]"
_DEFAULT_RADIUS_KM = 500.0
_MACRO_CASCADE_DEPTH = 1
_PROXIMITY_CASCADE_DEPTH = 2


class _Bus(Protocol):
    async def publish(self, channel: str, payload: str) -> None: ...


# ---------------------------------------------------------------------------
# Templates
# ---------------------------------------------------------------------------


async def _proximity_chain(
    s: AsyncSession,
    d: Disruption,
    *,
    source_label: str,
) -> tuple[ImpactReport, list[ToolInvocation]]:
    """Shared radius-based chain — weather / logistics / labor / unknown."""
    if d.lat is None or d.lng is None:
        return _empty_report(d, source_label=source_label), []

    radius_km = float(d.radius_km) if d.radius_km is not None else _DEFAULT_RADIUS_KM
    center = (float(d.lat), float(d.lng))

    args1 = ShipmentsTouchingRegionArgs(
        radius_center=center,
        radius_km=radius_km,
        status_in=["in_transit", "planned"],
    )
    r1 = await _shipments_touching_region(s, args1)
    trace: list[ToolInvocation] = [
        ToolInvocation(
            tool="shipments_touching_region",
            args=args1.model_dump(),
            result=r1,
        )
    ]

    rows1 = _rows_as_list(r1)
    shipment_ids = [str(row["id"]) for row in rows1 if row.get("id") is not None]
    if not shipment_ids:
        return _empty_report(d, source_label=source_label, trace=trace), trace

    args2 = ExposureAggregateArgs(shipment_ids=shipment_ids)
    r2 = await _exposure_aggregate(s, args2)
    trace.append(
        ToolInvocation(
            tool="exposure_aggregate",
            args=args2.model_dump(),
            result=r2,
        )
    )

    agg_rows = _rows_as_list(r2)
    agg = agg_rows[0] if agg_rows else {}
    total_revenue = _as_decimal(agg.get("total_revenue") or 0)
    total_units = int(agg.get("total_units") or 0)

    # Per-shipment exposure — even split of revenue. The LLM path gives finer
    # per-PO numbers; the fallback is intentionally coarser.
    per_shipment = (
        (total_revenue / Decimal(len(shipment_ids))).quantize(Decimal("0.01"))
        if total_revenue > 0
        else Decimal("0.00")
    )
    affected = [
        AffectedShipmentEntry(
            shipment_id=sid,
            exposure=per_shipment,
            days_to_sla_breach=None,
        )
        for sid in shipment_ids
    ]

    report = ImpactReport(
        disruption_id=d.id,
        total_exposure=total_revenue,
        units_at_risk=total_units,
        cascade_depth=_PROXIMITY_CASCADE_DEPTH,
        sql_executed="",  # rewritten by the persist layer
        reasoning_trace=ReasoningTrace(
            tool_calls=[],  # rewritten by the persist layer
            final_reasoning=(
                f"{_FALLBACK_MARKER} {source_label}: "
                f"{len(shipment_ids)} shipments within {radius_km:.0f}km of "
                f"({center[0]:.2f}, {center[1]:.2f}); "
                f"total_revenue={total_revenue} aggregated via exposure_aggregate."
            ),
        ),
        affected_shipments=affected,
    )
    return report, trace


async def _macro_template(
    s: AsyncSession,
    d: Disruption,
) -> tuple[ImpactReport, list[ToolInvocation]]:
    """Freight-rate / fuel proxy — mark all in-transit shipments as exposed."""
    result = await s.execute(text("SELECT id FROM shipments WHERE status = 'in_transit'"))
    shipment_ids = [str(row[0]) for row in result.all()]
    trace: list[ToolInvocation] = []

    if not shipment_ids:
        return _empty_report(d, source_label="macro", trace=trace), trace

    args = ExposureAggregateArgs(shipment_ids=shipment_ids)
    r = await _exposure_aggregate(s, args)
    trace.append(ToolInvocation(tool="exposure_aggregate", args=args.model_dump(), result=r))

    agg_rows = _rows_as_list(r)
    agg = agg_rows[0] if agg_rows else {}
    total_revenue = _as_decimal(agg.get("total_revenue") or 0)
    # Macro delta — low-confidence 5% revenue-at-risk proxy.
    exposure = (total_revenue * Decimal("0.05")).quantize(Decimal("0.01"))
    per_shipment = (
        (exposure / Decimal(len(shipment_ids))).quantize(Decimal("0.01"))
        if exposure > 0
        else Decimal("0.00")
    )
    affected = [
        AffectedShipmentEntry(
            shipment_id=sid,
            exposure=per_shipment,
            days_to_sla_breach=None,
        )
        for sid in shipment_ids
    ]
    report = ImpactReport(
        disruption_id=d.id,
        total_exposure=exposure,
        units_at_risk=int(agg.get("total_units") or 0),
        cascade_depth=_MACRO_CASCADE_DEPTH,
        sql_executed="",
        reasoning_trace=ReasoningTrace(
            tool_calls=[],
            final_reasoning=(
                f"{_FALLBACK_MARKER} macro: 5% revenue-at-risk proxy across "
                f"{len(shipment_ids)} in_transit shipments."
            ),
        ),
        affected_shipments=affected,
    )
    return report, trace


def _empty_report(
    d: Disruption,
    *,
    source_label: str,
    trace: list[ToolInvocation] | None = None,
) -> ImpactReport:
    """Degenerate report for a disruption with no geography / no matches.

    ``affected_shipments`` must be non-empty per the schema contract. We use a
    synthetic ``EMPTY-<disruption-id>`` marker — the pk collision here is
    intentional: if a shipment row with this id ever exists the upsert will be
    skipped via ``ON CONFLICT DO NOTHING`` and the zero-exposure row is simply
    not persisted. Caller logs this as a warning.
    """
    synthetic_id = f"EMPTY-{d.id}"
    return ImpactReport(
        disruption_id=d.id,
        total_exposure=Decimal("0"),
        units_at_risk=0,
        cascade_depth=1,
        sql_executed="",
        reasoning_trace=ReasoningTrace(
            tool_calls=[],
            final_reasoning=(
                f"{_FALLBACK_MARKER} {source_label}: insufficient geography or "
                "no shipments matched the disruption radius."
            ),
        ),
        affected_shipments=[
            AffectedShipmentEntry(
                shipment_id=synthetic_id,
                exposure=Decimal("0"),
                days_to_sla_breach=None,
            )
        ],
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _rows_as_list(result: dict[str, Any]) -> list[dict[str, Any]]:
    """``shipment_history_status`` returns a compound dict; guard against it.

    The two tools used in the fallback (``shipments_touching_region``,
    ``exposure_aggregate``) always return ``rows: list`` — but the tool
    contract leaves the door open, so normalise defensively.
    """
    rows = result.get("rows")
    if isinstance(rows, list):
        return [r for r in rows if isinstance(r, dict)]
    return []


async def _dispatch(
    s: AsyncSession,
    d: Disruption,
) -> tuple[ImpactReport, list[ToolInvocation]]:
    category = (d.category or "").lower()
    if category == "macro":
        return await _macro_template(s, d)
    # weather / policy / logistics / labor / unknown → proximity chain.
    return await _proximity_chain(s, d, source_label=f"{category or 'unknown'} template")


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


async def build_impact_report_fallback(
    *,
    disruption_id: uuid.UUID,
    bus: _Bus,
) -> uuid.UUID:
    """Write an ``impact_reports`` row via rules-based templates, no LLM.

    Returns the row id. Raises :class:`DisruptionNotFoundError` when the id
    has no row. Idempotent via the application-level
    ``existing_impact_id`` short-circuit already used by the LLM path.
    """
    async with default_session() as s:
        disruption = await _load_disruption(s, disruption_id)

        existing = await _existing_impact_id(s, disruption_id)
        if existing is not None:
            log.info(
                "analyst.fallback.impact_already_exists",
                disruption_id=str(disruption_id),
                impact_id=str(existing),
            )
            return existing

        report, raw_trace = await _dispatch(s, disruption)
        schema_trace = _trace_to_schema(raw_trace)
        sql_executed = _concat_sql(schema_trace)

        impact_id = await _persist(
            s,
            disruption_id=disruption_id,
            report=report,
            schema_trace=schema_trace,
            sql_executed=sql_executed,
        )
        await s.commit()

    payload = json.dumps(
        {
            "id": str(impact_id),
            "disruption_id": str(disruption_id),
            "total_exposure": str(_as_decimal(report.total_exposure)),
        }
    )
    await bus.publish("new_impact", payload)
    log.info(
        "analyst.fallback.impact_persisted",
        disruption_id=str(disruption_id),
        impact_id=str(impact_id),
        category=disruption.category,
        affected=len(report.affected_shipments),
    )
    return impact_id


__all__ = [
    "DisruptionNotFoundError",
    "build_impact_report_fallback",
]
