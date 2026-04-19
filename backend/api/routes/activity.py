from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from typing import Literal, cast

from fastapi import APIRouter, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select

from backend.api.deps import SessionDep
from backend.db.models import AgentLog

router = APIRouter()

Agent = Literal["Scout", "Analyst", "Strategist", "System"]
Severity = Literal["info", "warning", "critical", "success"]

_KNOWN_AGENTS: set[str] = {"Scout", "Analyst", "Strategist"}
_OPENCLAW_SUCCESS_ACTIONS = {"WriteApprovalAudit", "FlipShipmentStatuses"}
_ID_SHORT_LEN = 8  # UUID prefix length for compact IDs in feed messages


class ActivityItem(BaseModel):
    """Activity feed entry — contract shared with web/types/schemas.ts::activityItemSchema."""

    model_config = ConfigDict(extra="forbid")

    id: str
    agent: Agent
    message: str
    created_at: datetime
    severity: Severity = "info"


def _normalize_agent(name: str) -> Agent:
    candidate = name.strip().title()
    if candidate in _KNOWN_AGENTS:
        return cast(Agent, candidate)
    return "System"


def _short(value: object) -> str:
    s = str(value)
    return s[:_ID_SHORT_LEN] if len(s) > _ID_SHORT_LEN else s


def _msg_promoted(payload: dict[str, object]) -> str:
    did = payload.get("disruption_id")
    return f"Promoted disruption {_short(did)}" if did else "Promoted disruption"


def _msg_impact_written(payload: dict[str, object]) -> str:
    exposure = payload.get("total_exposure")
    return f"Impact report published · ${exposure}" if exposure else "Impact report published"


def _msg_options_written(payload: dict[str, object]) -> str:
    count = payload.get("count")
    if isinstance(count, int):
        return f"Drafted {count} mitigation option(s)"
    return "Drafted mitigation options"


# (message builder, severity) per known event_type. Builders take the payload
# so they can splice in IDs / exposure / counts for a richer feed entry.
_DISPATCH: dict[str, tuple[Callable[[dict[str, object]], str], Severity]] = {
    "signal_classified": (lambda _p: "Classified source signal", "info"),
    "signal_promoted_to_disruption": (_msg_promoted, "warning"),
    "impact_analysis_started": (lambda _p: "Running impact analysis", "info"),
    "impact_report_written": (_msg_impact_written, "warning"),
    "option_generation_started": (lambda _p: "Drafting mitigation options", "info"),
    "options_written": (_msg_options_written, "info"),
}


def _derive(event_type: str, payload: dict[str, object]) -> tuple[str, Severity]:
    """Map (event_type, payload) → (message, severity).

    Covers the six event_types emitted by the seed cascade plus ``openclaw.*``
    mutations. Unknown event_types fall back to a humanized event_type string.
    """
    if (entry := _DISPATCH.get(event_type)) is not None:
        builder, severity = entry
        return builder(payload), severity

    if event_type.startswith("openclaw."):
        action = event_type.removeprefix("openclaw.")
        sev: Severity = "success" if action in _OPENCLAW_SUCCESS_ACTIONS else "info"
        return f"OpenClaw · {action}", sev

    humanized = event_type.replace("_", " ").replace(".", " · ")
    return humanized or "Agent event", "info"


def _log_to_activity(row: AgentLog) -> ActivityItem:
    message, severity = _derive(row.event_type, row.payload or {})
    return ActivityItem(
        id=f"log-{row.id}",
        agent=_normalize_agent(row.agent_name),
        message=message,
        created_at=row.ts,
        severity=severity,
    )


@router.get("/feed")
async def get_activity_feed(
    session: SessionDep,
    limit: int = Query(50, ge=1, le=200, description="Max entries to return (1-200)"),
) -> list[ActivityItem]:
    """Return recent agent activity from agent_log, sorted by ts DESC.

    Shape matches the frontend `activityItemSchema` so the UI's zod parse
    succeeds without the API layer knowing UI details — messages and severity
    are derived server-side from `event_type` + `payload`.
    """
    stmt = select(AgentLog).order_by(AgentLog.ts.desc()).limit(min(limit, 200))
    result = await session.execute(stmt)
    rows = result.scalars().all()
    return [_log_to_activity(r) for r in rows]
