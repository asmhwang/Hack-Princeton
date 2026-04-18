"""Scout agent entrypoint.

Scout has no inbound NOTIFY channels — it is purely producer-side. The
lifecycle is driven by five source loops and one fusion tick, each running
on its own cadence as a background task. Each loop opens a fresh session
per poll so a stuck DB call on one source cannot back up another.

Run as::

    uv run python -m backend.agents.scout.main

Also importable as :class:`ScoutAgent` for integration tests, which drive
the lifecycle manually (``await agent.start() / agent.stop()``) and inject
a fake Tavily client so no real HTTP calls happen.
"""

from __future__ import annotations

import asyncio
import contextlib
import signal
from collections.abc import Coroutine
from typing import Any, Protocol

import structlog

from backend.agents.base import AgentBase
from backend.agents.scout.config import ScoutSettings
from backend.agents.scout.processors.fusion import run_fusion_pass
from backend.agents.scout.sources import logistics, macro, news, policy, weather
from backend.agents.scout.sources.tavily import TavilyClient
from backend.agents.scout.state import (
    record_fusion,
    record_poll,
    record_weather_poll,
)
from backend.db.session import session
from backend.llm.client import LLMClient

log = structlog.get_logger()


class _TavilyProto(Protocol):
    async def search(self, query: str, *, topic: str, days: int = 1) -> list[dict[str, Any]]: ...


_TAVILY_SOURCES = (news, policy, logistics, macro)


class ScoutAgent(AgentBase):
    name = "scout"
    channels: list[str] = []

    def __init__(
        self,
        *,
        settings: ScoutSettings | None = None,
        llm: LLMClient | None = None,
        tavily: _TavilyProto | None = None,
    ) -> None:
        self.settings = settings or ScoutSettings()
        super().__init__(dsn=self.settings.database_url)
        self.state_path = self.settings.state_path
        self.health_port = self.settings.health_port
        self._llm = llm or LLMClient(
            cache_path=self.settings.llm_cache_path,
            model=self.settings.model,
        )
        self._tavily: _TavilyProto = tavily or TavilyClient(
            cache_path=self.settings.tavily_cache_path,
        )

    # ------------------------------------------------------------------ bg tasks

    def background_tasks(self) -> list[Coroutine[Any, Any, Any]]:
        tasks: list[Coroutine[Any, Any, Any]] = [
            self._tavily_loop(news),
            self._tavily_loop(policy),
            self._tavily_loop(logistics),
            self._tavily_loop(macro),
            self._fusion_loop(),
        ]
        if self.settings.watch_points:
            tasks.append(self._weather_loop())
        return tasks

    # ------------------------------------------------------------------ tavily

    async def _tavily_loop(self, source: Any) -> None:
        """One loop per Tavily-backed category. Iterates forever at source cadence."""
        category: str = source.SOURCE_CATEGORY
        cadence: float = float(source.CADENCE_SECONDS)
        while not self._stop.is_set():
            try:
                async with session() as s:
                    await source.poll_once(
                        db_session=s,
                        llm=self._llm,
                        bus=self._bus,
                        client=self._tavily,
                    )
                    await s.commit()
                await record_poll(self, category)
            except asyncio.CancelledError:
                raise
            except Exception as err:  # noqa: BLE001 — loop must stay alive
                log.error("scout.poll_loop.error", category=category, error=str(err))
            await self._sleep_or_stop(cadence)

    # ------------------------------------------------------------------ weather

    async def _weather_loop(self) -> None:
        cadence = float(weather.CADENCE_SECONDS)
        while not self._stop.is_set():
            try:
                async with session() as s:
                    await weather.poll_once(
                        watch_points=self.settings.watch_points,
                        db_session=s,
                        bus=self._bus,
                    )
                    await s.commit()
                for p in self.settings.watch_points:
                    await record_weather_poll(self, p.id)
            except asyncio.CancelledError:
                raise
            except Exception as err:  # noqa: BLE001
                log.error("scout.weather_loop.error", error=str(err))
            await self._sleep_or_stop(cadence)

    # ------------------------------------------------------------------ fusion

    async def _fusion_loop(self) -> None:
        cadence = float(self.settings.fusion_cadence_s)
        while not self._stop.is_set():
            try:
                async with session() as s:
                    new_ids = await run_fusion_pass(s, self._llm)
                    await s.commit()
                for did in new_ids:
                    await self._bus.publish("new_disruption", str(did))
                await record_fusion(self)
            except asyncio.CancelledError:
                raise
            except Exception as err:  # noqa: BLE001
                log.error("scout.fusion_loop.error", error=str(err))
            await self._sleep_or_stop(cadence)

    # ------------------------------------------------------------------ helpers

    async def _sleep_or_stop(self, seconds: float) -> None:
        """Sleep honoring ``self._stop`` so ``stop()`` returns promptly."""
        with contextlib.suppress(TimeoutError):
            await asyncio.wait_for(self._stop.wait(), timeout=seconds)


async def _run() -> None:
    agent = ScoutAgent()
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
