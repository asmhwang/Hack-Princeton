"""Strategist options processor — Gemini tool loop → ``MitigationOptionsBundle``.

``generate_options(impact_report_id, *, llm)`` is the single public entry:

1. Load the ``ImpactReport`` + its ``affected_shipments`` + the upstream
   ``Disruption`` so the LLM has the full crisis context.
2. Build a prompt concatenating the Strategist system prompt + the
   disruption + the impact snapshot. ``LLMClient.cached_context`` memoizes
   the schema summary once per process (mirrors the Analyst pattern).
3. Invoke ``llm.with_tools(prompt, strategist_tools, final_schema=
   MitigationOptionsBundle)`` — Gemini Pro iterates tools until it emits
   the structured bundle.
4. Return the parsed ``MitigationOptionsBundle`` + the raw tool trace. The
   caller (strategist ``main.py``) hands the bundle to the OpenClaw action
   layer for persistence.

Persistence is intentionally outside this module — Task 7.3 wraps every
mutation in an OpenClaw ``Action`` so the judge-visible agent_log trace
covers all DB writes.
"""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any, Protocol, cast

import structlog
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

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
from backend.schemas.mitigation import MitigationOptionsBundle

log = structlog.get_logger()

_PROMPT_DIR = Path(__file__).parent.parent / "prompts"
_OPTIONS_SYSTEM = _PROMPT_DIR / "options.md"
_SCHEMA_SUMMARY = _PROMPT_DIR / "schema_summary.md"

_SCHEMA_CACHE_KEY = "strategist_schema_v1"
_TOOL_CALL_MAX_ITERS = 8


class ImpactReportNotFoundError(LookupError):
    """Raised when ``generate_options`` is handed an id with no row."""


class _LLM(Protocol):
    """Structural subset of ``LLMClient`` the Strategist exercises."""

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


# ---------------------------------------------------------------------------
# Tool registry → LLM Tool objects. Strategist reuses the full Analyst tool
# set (which already includes alternate_suppliers_for_sku + alternate_ports_near
# per Phase 2 Task 2.6).
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
# Context loading
# ---------------------------------------------------------------------------


async def _load_context(
    s: AsyncSession,
    impact_report_id: uuid.UUID,
) -> tuple[ImpactReportRow, Disruption, list[AffectedShipment]]:
    ir = (
        await s.execute(select(ImpactReportRow).where(ImpactReportRow.id == impact_report_id))
    ).scalar_one_or_none()
    if ir is None:
        raise ImpactReportNotFoundError(f"impact_report {impact_report_id} not found")

    disruption = (
        await s.execute(select(Disruption).where(Disruption.id == ir.disruption_id))
    ).scalar_one()

    affected = list(
        (
            await s.execute(
                select(AffectedShipment).where(AffectedShipment.impact_report_id == ir.id)
            )
        )
        .scalars()
        .all()
    )
    return ir, disruption, affected


def _impact_context(
    ir: ImpactReportRow,
    d: Disruption,
    affected: list[AffectedShipment],
) -> str:
    # Truncate affected list for prompt size — Gemini already has the row
    # count; fine-grained exposure lives in the DB if a tool call needs it.
    preview = [
        {
            "shipment_id": a.shipment_id,
            "exposure": str(a.exposure),
            "days_to_sla_breach": a.days_to_sla_breach,
        }
        for a in affected[:10]
    ]
    payload = {
        "impact_report": {
            "id": str(ir.id),
            "total_exposure": str(ir.total_exposure),
            "units_at_risk": ir.units_at_risk,
            "cascade_depth": ir.cascade_depth,
            "affected_shipments_preview": preview,
            "affected_shipments_total": len(affected),
        },
        "disruption": {
            "id": str(d.id),
            "title": d.title,
            "category": d.category,
            "severity": d.severity,
            "region": d.region,
            "lat": float(d.lat) if d.lat is not None else None,
            "lng": float(d.lng) if d.lng is not None else None,
            "radius_km": float(d.radius_km) if d.radius_km is not None else None,
        },
    }
    return json.dumps(payload, indent=2)


async def _assemble_prompt(
    llm: _LLM,
    ir: ImpactReportRow,
    d: Disruption,
    affected: list[AffectedShipment],
) -> str:
    system = _OPTIONS_SYSTEM.read_text()
    schema_md = _SCHEMA_SUMMARY.read_text()
    try:
        await llm.cached_context(_SCHEMA_CACHE_KEY, schema_md)
    except Exception as err:  # noqa: BLE001 — defensive; SDK surface varies
        log.warning("strategist.cached_context_failed", error=str(err))

    return (
        f"{system}\n\n"
        f"## DB schema summary\n{schema_md}\n\n"
        f"## Impact context\n```json\n{_impact_context(ir, d, affected)}\n```\n\n"
        "Proceed — call tools, then emit the final MitigationOptionsBundle JSON."
    )


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


async def generate_options(
    *,
    impact_report_id: uuid.UUID,
    llm: _LLM,
) -> tuple[MitigationOptionsBundle, list[ToolInvocation]]:
    """Run the Strategist tool loop and return the parsed options bundle.

    Does not persist — the OpenClaw action layer in Task 7.3 owns writes.

    Raises :class:`ImpactReportNotFoundError` when ``impact_report_id`` has
    no row. Raises :class:`backend.llm.client.LLMValidationError` when
    Gemini's final output fails validation after one retry.
    """
    async with default_session() as s:
        ir, disruption, affected = await _load_context(s, impact_report_id)
        prompt = await _assemble_prompt(llm, ir, disruption, affected)

    tools = _build_tool_list()
    result, raw_trace = await llm.with_tools(
        prompt,
        tools,
        final_schema=MitigationOptionsBundle,
        cache_key=f"strategist::{impact_report_id}",
        max_iters=_TOOL_CALL_MAX_ITERS,
    )
    bundle = cast(MitigationOptionsBundle, result)
    log.info(
        "strategist.options_generated",
        impact_report_id=str(impact_report_id),
        option_count=len(bundle.options),
        tool_calls=len(raw_trace),
    )
    return bundle, raw_trace
