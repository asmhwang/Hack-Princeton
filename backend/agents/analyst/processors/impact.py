"""Analyst impact processor — Gemini function-calling loop → persisted impact report.

``build_impact_report(disruption_id, *, llm, bus)`` is the single public entry:

1. Load the ``Disruption`` row.
2. Short-circuit if an ``impact_reports`` row already exists for it (idempotent
   re-delivery; the table has no DB-level unique constraint on
   ``disruption_id`` so we enforce at the application layer).
3. Build a prompt concatenating the Analyst system prompt + disruption
   context. ``LLMClient.cached_context`` is invoked once with the schema
   summary so repeated calls within a process share a Gemini cached-content
   handle.
4. Invoke ``llm.with_tools(prompt, analyst_tools, final_schema=ImpactReport)``
   — Gemini Pro iterates tools until it emits the structured final JSON.
5. Rewrite ``reasoning_trace.tool_calls`` from the observed trace (the LLM
   doesn't know ``synthesized_sql`` — those come from the tool results) and
   concatenate ``synthesized_sql`` into ``impact_reports.sql_executed`` for
   the explainability drawer.
6. Persist (in one transaction): ``impact_reports`` row + an
   ``affected_shipments`` entry per ``AffectedShipmentEntry`` (upserted
   ``ON CONFLICT DO NOTHING`` to tolerate retries).
7. After commit, ``NOTIFY new_impact`` with the frozen payload schema
   ``{"id": <uuid>, "disruption_id": <uuid>, "total_exposure": <decimal-string>}``.

Tool-call reasoning traces truncate each ``args`` payload so oversize lists
(e.g. 500 shipment IDs) don't balloon the JSONB blob — the authoritative data
lives in ``impact_reports.sql_executed`` + ``affected_shipments``.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from decimal import Decimal
from pathlib import Path
from typing import Any, Protocol, cast

import structlog
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.validators.sql_guard import SqlSafetyError, validate_select_only
from backend.db.models import (
    AffectedShipment,
    Disruption,
)
from backend.db.models import (
    ImpactReport as ImpactReportRow,
)
from backend.db.session import session as default_session
from backend.llm.client import Tool, ToolInvocation
from backend.llm.tools.analyst_tools import TOOL_REGISTRY
from backend.schemas.impact import (
    ImpactReport,
    ReasoningTrace,
)
from backend.schemas.impact import (
    ToolInvocation as SchemaToolInvocation,
)

log = structlog.get_logger()

_PROMPT_DIR = Path(__file__).parent.parent / "prompts"
_IMPACT_SYSTEM = _PROMPT_DIR / "impact_system.md"
_SCHEMA_SUMMARY = _PROMPT_DIR / "schema_summary.md"

_SCHEMA_CACHE_KEY = "analyst_schema_v1"
_TOOL_CALL_MAX_ITERS = 6
_ARGS_PREVIEW_LIST_LIMIT = 10
_SQL_SEPARATOR = "\n-- ---- next ---- --\n"


class DisruptionNotFoundError(LookupError):
    """Raised when ``build_impact_report`` is handed an id with no row."""


class _LLM(Protocol):
    """Structural subset of ``LLMClient`` exercised by the Analyst."""

    async def with_tools(
        self,
        prompt: str,
        tools: list[Tool],
        *,
        final_schema: type[BaseModel],
        cache_key: str | None = ...,
        max_iters: int = ...,
    ) -> tuple[BaseModel, list[ToolInvocation]]: ...

    async def cached_context(self, key: str, content: str) -> str: ...


class _Bus(Protocol):
    async def publish(self, channel: str, payload: str) -> None: ...


# ---------------------------------------------------------------------------
# Tool registry → LLM Tool objects
# ---------------------------------------------------------------------------


def _build_tool_list() -> list[Tool]:
    tools: list[Tool] = []
    for name, description, args_schema, callable_ in TOOL_REGISTRY:
        tools.append(
            Tool(
                name=name,
                description=description,
                args_schema=args_schema,
                callable=cast(Any, callable_),
            )
        )
    return tools


# ---------------------------------------------------------------------------
# Prompt assembly
# ---------------------------------------------------------------------------


def _load_prompt_files() -> tuple[str, str]:
    return _IMPACT_SYSTEM.read_text(), _SCHEMA_SUMMARY.read_text()


def _impact_cache_key(d: Disruption) -> str:
    """Content-stable cache key: disruption category + centroid + radius + title.

    Excludes the UUID and source_signal_ids — those rotate per simulate call
    but don't affect the report's semantics. Offline replay relies on this.
    """
    parts = (
        (d.category or "").strip().lower(),
        f"{float(d.lat or 0):.4f}",
        f"{float(d.lng or 0):.4f}",
        f"{float(d.radius_km or 0):.1f}",
        (d.title or "").strip().lower(),
    )
    digest = hashlib.sha256("|".join(parts).encode()).hexdigest()
    return f"analyst::content::{digest}"


def _disruption_context(d: Disruption) -> str:
    return json.dumps(
        {
            "id": str(d.id),
            "title": d.title,
            "summary": d.summary,
            "category": d.category,
            "severity": d.severity,
            "region": d.region,
            "lat": float(d.lat) if d.lat is not None else None,
            "lng": float(d.lng) if d.lng is not None else None,
            "radius_km": float(d.radius_km) if d.radius_km is not None else None,
            "source_signal_ids": [str(s) for s in (d.source_signal_ids or [])],
        },
        indent=2,
    )


async def _assemble_prompt(llm: _LLM, d: Disruption) -> str:
    system, schema_md = _load_prompt_files()
    # Best-effort cached context — SDK no-ops if content below min size.
    try:
        await llm.cached_context(_SCHEMA_CACHE_KEY, schema_md)
    except Exception as err:  # noqa: BLE001 — defensive; SDK surface varies
        log.warning("analyst.cached_context_failed", error=str(err))

    return (
        f"{system}\n\n"
        f"## DB schema summary\n{schema_md}\n\n"
        f"## Disruption context\n```json\n{_disruption_context(d)}\n```\n\n"
        "Proceed — call tools, then emit the final ImpactReport JSON."
    )


# ---------------------------------------------------------------------------
# Trace translation
# ---------------------------------------------------------------------------


def _truncate_args(args: dict[str, Any]) -> dict[str, Any]:
    """Cap list-valued args at ``_ARGS_PREVIEW_LIST_LIMIT`` entries for logging."""
    out: dict[str, Any] = {}
    for k, v in args.items():
        if isinstance(v, list) and len(v) > _ARGS_PREVIEW_LIST_LIMIT:
            out[k] = v[:_ARGS_PREVIEW_LIST_LIMIT] + [f"...+{len(v) - _ARGS_PREVIEW_LIST_LIMIT}"]
        else:
            out[k] = v
    return out


def _trace_to_schema(trace: list[ToolInvocation]) -> list[SchemaToolInvocation]:
    """Convert ``llm.client.ToolInvocation`` → ``schemas.ToolInvocation``.

    The LLM trace carries the full tool result dict; we extract ``row_count``
    and ``synthesized_sql`` and discard the rows (they can be large; the
    authoritative data is in ``affected_shipments`` + the persisted SQL).
    """
    out: list[SchemaToolInvocation] = []
    for inv in trace:
        result = inv.result or {}
        sql = str(result.get("synthesized_sql") or "")
        row_count = int(result.get("row_count", 0))
        out.append(
            SchemaToolInvocation(
                tool_name=inv.tool,
                args=_truncate_args(inv.args or {}),
                row_count=row_count,
                synthesized_sql=sql,
            )
        )
    return out


def _concat_sql(trace: list[SchemaToolInvocation]) -> str:
    pieces: list[str] = []
    for inv in trace:
        sql = inv.synthesized_sql.strip()
        if not sql:
            continue
        # Defense-in-depth: each piece must independently pass the guard.
        try:
            validate_select_only(sql)
        except SqlSafetyError as err:
            # Do not leak bad SQL into persisted explainability string.
            log.warning("analyst.sql_rejected", tool=inv.tool_name, error=str(err))
            continue
        pieces.append(f"-- {inv.tool_name}\n{sql}")
    return _SQL_SEPARATOR.join(pieces)


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------


async def _load_disruption(s: AsyncSession, disruption_id: uuid.UUID) -> Disruption:
    row = (
        await s.execute(select(Disruption).where(Disruption.id == disruption_id))
    ).scalar_one_or_none()
    if row is None:
        raise DisruptionNotFoundError(f"disruption {disruption_id} not found")
    return row


async def _existing_impact_id(s: AsyncSession, disruption_id: uuid.UUID) -> uuid.UUID | None:
    """Return an existing ``impact_reports.id`` for this disruption, if any."""
    row = (
        await s.execute(
            select(ImpactReportRow.id).where(ImpactReportRow.disruption_id == disruption_id)
        )
    ).first()
    return row[0] if row is not None else None


async def _persist(
    s: AsyncSession,
    disruption_id: uuid.UUID,
    report: ImpactReport,
    schema_trace: list[SchemaToolInvocation],
    sql_executed: str,
) -> uuid.UUID:
    reasoning_trace = ReasoningTrace(
        tool_calls=schema_trace,
        final_reasoning=report.reasoning_trace.final_reasoning,
    )

    impact_id = uuid.uuid4()
    ir = ImpactReportRow(
        id=impact_id,
        disruption_id=disruption_id,
        total_exposure=report.total_exposure,
        units_at_risk=report.units_at_risk,
        cascade_depth=report.cascade_depth,
        sql_executed=sql_executed or None,
        reasoning_trace=reasoning_trace.model_dump(mode="json"),
    )
    s.add(ir)
    await s.flush()

    if report.affected_shipments:
        rows = [
            {
                "impact_report_id": impact_id,
                "shipment_id": entry.shipment_id,
                "exposure": entry.exposure,
                "days_to_sla_breach": entry.days_to_sla_breach,
            }
            for entry in report.affected_shipments
        ]
        stmt = (
            pg_insert(AffectedShipment)
            .values(rows)
            .on_conflict_do_nothing(index_elements=["impact_report_id", "shipment_id"])
        )
        await s.execute(stmt)

    return impact_id


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


async def build_impact_report(
    *,
    disruption_id: uuid.UUID,
    llm: _LLM,
    bus: _Bus,
) -> uuid.UUID:
    """Run the Analyst tool loop, persist the impact report, NOTIFY ``new_impact``.

    Returns the ``impact_reports.id``. Raises:

    - :class:`DisruptionNotFoundError` when ``disruption_id`` has no row.
    - :class:`backend.llm.client.LLMValidationError` when Gemini's final
      output fails validation after one retry (caller invokes fallback).
    """
    async with default_session() as s:
        disruption = await _load_disruption(s, disruption_id)

        # Idempotent short-circuit — application-level (no unique constraint
        # on disruption_id in the schema).
        existing = await _existing_impact_id(s, disruption_id)
        if existing is not None:
            log.info(
                "analyst.impact_already_exists",
                disruption_id=str(disruption_id),
                impact_id=str(existing),
            )
            return existing

        prompt = await _assemble_prompt(llm, disruption)
        tools = _build_tool_list()

        result, raw_trace = await llm.with_tools(
            prompt,
            tools,
            final_schema=ImpactReport,
            cache_key=_impact_cache_key(disruption),
            max_iters=_TOOL_CALL_MAX_ITERS,
        )
        report = cast(ImpactReport, result)

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
        "analyst.impact_persisted",
        disruption_id=str(disruption_id),
        impact_id=str(impact_id),
        affected=len(report.affected_shipments),
    )
    return impact_id


def _as_decimal(value: Decimal | int | float | str) -> Decimal:
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))
