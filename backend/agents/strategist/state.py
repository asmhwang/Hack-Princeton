"""Typed accessors over the AgentBase state dict for the Strategist agent.

The Strategist tracks:

- ``last_impact_id`` — UUID of the most recently handled impact report;
  logged on startup for continuity.
- ``processed_count`` — monotonic counter.
- ``draft_failure_count`` — incremented when ``DraftQualityError`` forces
  skipping an option's drafts; useful for alerting.

Mutations go through :class:`AgentBase.checkpoint` which atomically rewrites
``state.json``.
"""

from __future__ import annotations

import uuid
from typing import Any

from backend.agents.base import AgentBase

_KEY_LAST_IMPACT = "last_impact_id"
_KEY_PROCESSED_COUNT = "processed_count"
_KEY_DRAFT_FAILURES = "draft_failure_count"


def load_last_impact_id(agent: AgentBase) -> uuid.UUID | None:
    raw = agent.checkpoint_get(_KEY_LAST_IMPACT)
    if not isinstance(raw, str):
        return None
    try:
        return uuid.UUID(raw)
    except ValueError:
        return None


def processed_count(agent: AgentBase) -> int:
    value = agent.checkpoint_get(_KEY_PROCESSED_COUNT, 0)
    return int(value) if isinstance(value, (int, str)) else 0


def draft_failure_count(agent: AgentBase) -> int:
    value = agent.checkpoint_get(_KEY_DRAFT_FAILURES, 0)
    return int(value) if isinstance(value, (int, str)) else 0


async def record_processed(
    agent: AgentBase,
    impact_id: uuid.UUID,
    *,
    draft_failures: int,
) -> None:
    await agent.checkpoint(_KEY_LAST_IMPACT, str(impact_id))
    await agent.checkpoint(_KEY_PROCESSED_COUNT, processed_count(agent) + 1)
    if draft_failures:
        await agent.checkpoint(
            _KEY_DRAFT_FAILURES, draft_failure_count(agent) + draft_failures
        )


def state_snapshot(agent: AgentBase) -> dict[str, Any]:
    last = load_last_impact_id(agent)
    return {
        _KEY_LAST_IMPACT: str(last) if last else None,
        _KEY_PROCESSED_COUNT: processed_count(agent),
        _KEY_DRAFT_FAILURES: draft_failure_count(agent),
    }
