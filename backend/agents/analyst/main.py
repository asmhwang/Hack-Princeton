"""Analyst agent entrypoint.

Subscribes to ``new_disruption``. For each notify payload (a disruption UUID
as a bare string — matches Scout's publish side), the agent runs the Gemini
function-calling loop via
:func:`backend.agents.analyst.processors.impact.build_impact_report`. If the
LLM path raises :class:`LLMValidationError`, the rules-based fallback in
:mod:`backend.agents.analyst.processors.fallback` runs instead so the
Strategist downstream never stalls waiting on a dead disruption.

Run as::

    uv run python -m backend.agents.analyst.main

Also importable as ``AnalystAgent`` for integration tests, which drive the
lifecycle manually (``await agent.start() / agent.stop()``).
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import signal
import uuid
from pathlib import Path

import structlog

from backend.agents.analyst.config import AnalystSettings
from backend.agents.analyst.processors.fallback import build_impact_report_fallback
from backend.agents.analyst.processors.impact import build_impact_report
from backend.agents.analyst.state import record_processed
from backend.agents.base import AgentBase
from backend.db.bus import EventBus
from backend.llm.client import LLMClient, LLMValidationError

log = structlog.get_logger()


class AnalystAgent(AgentBase):
    name = "analyst"
    channels = ["new_disruption"]

    def __init__(
        self,
        *,
        settings: AnalystSettings | None = None,
        llm: LLMClient | None = None,
    ) -> None:
        self.settings = settings or AnalystSettings()
        super().__init__(dsn=self.settings.database_url)
        self.state_path = Path(self.settings.state_path)
        self.health_port = self.settings.health_port
        self._llm = llm or LLMClient(
            cache_path=self.settings.llm_cache_path,
            model=self.settings.model,
        )

    # ------------------------------------------------------------------ handler

    async def on_notify(self, channel: str, payload: str) -> None:
        disruption_id = _parse_disruption_id(payload)
        if disruption_id is None:
            log.warning("analyst.invalid_payload", channel=channel, payload=payload[:200])
            return

        used_fallback = False
        try:
            impact_id = await build_impact_report(
                disruption_id=disruption_id,
                llm=self._llm,
                bus=self._bus,
            )
        except LLMValidationError as err:
            log.warning(
                "analyst.llm_failed_fallback_invoked",
                disruption_id=str(disruption_id),
                error=str(err),
            )
            used_fallback = True
            impact_id = await build_impact_report_fallback(
                disruption_id=disruption_id,
                bus=self._bus,
            )

        await record_processed(self, disruption_id, used_fallback=used_fallback)
        log.info(
            "analyst.disruption_processed",
            disruption_id=str(disruption_id),
            impact_id=str(impact_id),
            used_fallback=used_fallback,
        )

    # ------------------------------------------------------------------ test hooks

    @property
    def bus(self) -> EventBus:
        """Exposed for integration tests that want to publish via the same bus."""
        return self._bus


def _parse_disruption_id(payload: str) -> uuid.UUID | None:
    """Accept either a bare UUID string or a JSON object with an ``id`` key.

    Scout publishes the bare UUID today (per coordination doc §2) — the JSON
    form is tolerated so the contract can evolve without a lock-step deploy.
    """
    candidate = payload.strip()
    if not candidate:
        return None
    try:
        return uuid.UUID(candidate)
    except ValueError:
        pass
    try:
        parsed = json.loads(candidate)
    except (ValueError, TypeError):
        return None
    if isinstance(parsed, dict):
        for key in ("disruption_id", "id"):
            val = parsed.get(key)
            if isinstance(val, str):
                try:
                    return uuid.UUID(val)
                except ValueError:
                    continue
    return None


async def _run() -> None:
    agent = AnalystAgent()
    await agent.start()
    stop = asyncio.Event()

    def _set_stop() -> None:
        stop.set()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        with contextlib.suppress(NotImplementedError):
            loop.add_signal_handler(sig, _set_stop)

    try:
        await stop.wait()
    finally:
        await agent.stop()


def main() -> None:
    asyncio.run(_run())


if __name__ == "__main__":
    main()
