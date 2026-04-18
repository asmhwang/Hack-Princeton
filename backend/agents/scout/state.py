"""Typed accessors over the AgentBase state dict for the Scout agent.

Scout tracks per-source cursors so a kill/relaunch resumes without
re-polling an interval it already consumed and without double-notifying
the bus. State is flushed atomically by :meth:`AgentBase.checkpoint` after
every successful poll.

Keys:

- ``last_poll_ts.<category>`` — ISO-8601 timestamp of last successful poll
  per source category (news/policy/logistics/macro).
- ``last_weather_poll_ts.<point_id>`` — per-watch-point Open-Meteo cursor.
- ``fusion_runs`` — monotonic counter for /health.
- ``poll_counts.<category>`` — monotonic counter per category for /health.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from backend.agents.base import AgentBase

_KEY_LAST_POLL = "last_poll_ts"
_KEY_LAST_WEATHER = "last_weather_poll_ts"
_KEY_FUSION_RUNS = "fusion_runs"
_KEY_POLL_COUNTS = "poll_counts"


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _get_map(agent: AgentBase, key: str) -> dict[str, Any]:
    raw = agent.checkpoint_get(key, {})
    return dict(raw) if isinstance(raw, dict) else {}


def last_poll_ts(agent: AgentBase, category: str) -> str | None:
    m = _get_map(agent, _KEY_LAST_POLL)
    val = m.get(category)
    return val if isinstance(val, str) else None


def last_weather_poll_ts(agent: AgentBase, point_id: str) -> str | None:
    m = _get_map(agent, _KEY_LAST_WEATHER)
    val = m.get(point_id)
    return val if isinstance(val, str) else None


def fusion_runs(agent: AgentBase) -> int:
    val = agent.checkpoint_get(_KEY_FUSION_RUNS, 0)
    return int(val) if isinstance(val, (int, str)) else 0


def poll_count(agent: AgentBase, category: str) -> int:
    m = _get_map(agent, _KEY_POLL_COUNTS)
    val = m.get(category, 0)
    return int(val) if isinstance(val, (int, str)) else 0


async def record_poll(agent: AgentBase, category: str) -> None:
    m = _get_map(agent, _KEY_LAST_POLL)
    m[category] = _now_iso()
    await agent.checkpoint(_KEY_LAST_POLL, m)
    counts = _get_map(agent, _KEY_POLL_COUNTS)
    counts[category] = poll_count(agent, category) + 1
    await agent.checkpoint(_KEY_POLL_COUNTS, counts)


async def record_weather_poll(agent: AgentBase, point_id: str) -> None:
    m = _get_map(agent, _KEY_LAST_WEATHER)
    m[point_id] = _now_iso()
    await agent.checkpoint(_KEY_LAST_WEATHER, m)


async def record_fusion(agent: AgentBase) -> None:
    await agent.checkpoint(_KEY_FUSION_RUNS, fusion_runs(agent) + 1)


def state_snapshot(agent: AgentBase) -> dict[str, Any]:
    return {
        _KEY_LAST_POLL: _get_map(agent, _KEY_LAST_POLL),
        _KEY_LAST_WEATHER: _get_map(agent, _KEY_LAST_WEATHER),
        _KEY_FUSION_RUNS: fusion_runs(agent),
        _KEY_POLL_COUNTS: _get_map(agent, _KEY_POLL_COUNTS),
    }
