"""Typed accessors over the AgentBase state dict for the Analyst agent.

The Analyst tracks two pieces of recoverable state across restarts:

- ``last_disruption_id`` — UUID of the most recently handled disruption;
  logged on startup so a human can verify continuity across VM restarts.
- ``processed_count`` — monotonic counter for /health debug output and
  dashboards.

All mutations go through :class:`AgentBase.checkpoint`, which atomically
rewrites ``state.json``. Keys are plain strings because the file must remain
``json.loads``-round-trippable.
"""

from __future__ import annotations

import uuid
from typing import Any

from backend.agents.base import AgentBase

_KEY_LAST_DISRUPTION = "last_disruption_id"
_KEY_PROCESSED_COUNT = "processed_count"
_KEY_FALLBACK_COUNT = "fallback_count"


def load_last_disruption_id(agent: AgentBase) -> uuid.UUID | None:
    raw = agent.checkpoint_get(_KEY_LAST_DISRUPTION)
    if not isinstance(raw, str):
        return None
    try:
        return uuid.UUID(raw)
    except ValueError:
        return None


def processed_count(agent: AgentBase) -> int:
    value = agent.checkpoint_get(_KEY_PROCESSED_COUNT, 0)
    return int(value) if isinstance(value, (int, str)) else 0


def fallback_count(agent: AgentBase) -> int:
    value = agent.checkpoint_get(_KEY_FALLBACK_COUNT, 0)
    return int(value) if isinstance(value, (int, str)) else 0


async def record_processed(
    agent: AgentBase,
    disruption_id: uuid.UUID,
    *,
    used_fallback: bool,
) -> None:
    """Flush a single processed-disruption event to ``state.json`` atomically.

    Two checkpoint writes instead of one keeps the AgentBase helper surface
    minimal — ``checkpoint`` already fsyncs via ``os.replace``, so the small
    cost buys us per-field clarity. ``used_fallback`` increments a separate
    counter so ops can alert on high fallback ratios without parsing logs.
    """
    await agent.checkpoint(_KEY_LAST_DISRUPTION, str(disruption_id))
    await agent.checkpoint(_KEY_PROCESSED_COUNT, processed_count(agent) + 1)
    if used_fallback:
        await agent.checkpoint(_KEY_FALLBACK_COUNT, fallback_count(agent) + 1)


def state_snapshot(agent: AgentBase) -> dict[str, Any]:
    """Read-only view for ``/health`` responses and test assertions."""
    last = load_last_disruption_id(agent)
    return {
        _KEY_LAST_DISRUPTION: str(last) if last else None,
        _KEY_PROCESSED_COUNT: processed_count(agent),
        _KEY_FALLBACK_COUNT: fallback_count(agent),
    }
