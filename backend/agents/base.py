"""Agent lifecycle base class.

Every agent (Scout/Analyst/Strategist) subclasses ``AgentBase`` and overrides
``on_notify`` + optionally ``background_tasks``. The base handles:

- ``EventBus`` start/stop and channel subscription.
- ``state.json`` checkpoint load/save with atomic writes, so restart resumes
  without duplicating work (Task 12.3 judging requirement).
- A minimal stdlib ``asyncio`` HTTP server on ``127.0.0.1:<health_port>`` that
  serves ``GET /health`` → ``{"agent": name, "ok": true, "uptime_s": int,
  "last_notify": iso | null}``.
- ``structlog`` trace injection: ``new_trace()`` is called at the start of
  every handler dispatch so each notify gets a fresh ``trace_id``.
- Exception isolation: a raising handler never propagates out of the
  dispatcher — one bad payload must not kill the listener.

Checkpoint contract for subclasses: call ``await self.checkpoint(key, value)``
after each significant mutation. ``_save_state()`` also runs on ``stop()`` but
if a SIGTERM arrives mid-handler, in-flight mutations may be lost.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import os
import time
from collections.abc import Awaitable, Callable, Coroutine
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import structlog

from backend.db.bus import EventBus
from backend.observability.logging import new_trace

log = structlog.get_logger()

_HEALTH_HOST = "127.0.0.1"


class AgentBase:
    name: str = "agent"
    channels: list[str] = []
    state_path: Path = Path("/var/lib/supplai/state.json")
    health_port: int = 0

    def __init__(self, dsn: str) -> None:
        self._bus = EventBus(dsn)
        self._state: dict[str, Any] = {}
        self._tasks: list[asyncio.Task[Any]] = []
        self._stop = asyncio.Event()
        self._started_at: float = 0.0
        self._last_notify: datetime | None = None
        self._health_server: asyncio.base_events.Server | None = None
        self.bound_health_port: int = 0

    # ------------------------------------------------------------------ lifecycle

    async def start(self) -> None:
        self._state = self._load_state()
        self._started_at = time.monotonic()
        await self._bus.start()
        for ch in self.channels:
            await self._bus.subscribe(ch, self._wrap(ch))
        self._tasks = [asyncio.create_task(t) for t in self.background_tasks()]
        await self._start_health_server()
        log.info(
            "agent.started",
            agent=self.name,
            channels=self.channels,
            health_port=self.bound_health_port,
        )

    async def stop(self) -> None:
        self._stop.set()
        for t in self._tasks:
            t.cancel()
        if self._tasks:
            await asyncio.gather(*self._tasks, return_exceptions=True)
        await self._bus.stop()
        await self._stop_health_server()
        self._save_state()
        log.info("agent.stopped", agent=self.name)

    # ------------------------------------------------------------------ overrides

    async def on_notify(self, channel: str, payload: str) -> None:
        """Subclass hook. Default: no-op."""

    def background_tasks(self) -> list[Coroutine[Any, Any, Any]]:
        """Subclass hook. Return an iterable of coroutines to spawn at start()."""
        return []

    # ------------------------------------------------------------------ subclass helpers

    async def checkpoint(self, key: str, value: Any) -> None:
        """Set state key + flush atomically. Call after significant mutations."""
        self._state[key] = value
        self._save_state()

    def checkpoint_get(self, key: str, default: Any = None) -> Any:
        return self._state.get(key, default)

    # ------------------------------------------------------------------ dispatch

    def _wrap(self, channel: str) -> Callable[[str], Awaitable[None]]:
        async def _on(payload: str) -> None:
            new_trace()
            self._last_notify = datetime.now(UTC)
            try:
                await self.on_notify(channel, payload)
            except Exception as e:  # noqa: BLE001 — intentional blanket catch
                log.error(
                    "agent.handler_failed",
                    agent=self.name,
                    channel=channel,
                    error=str(e),
                )

        return _on

    # ------------------------------------------------------------------ state io

    def _load_state(self) -> dict[str, Any]:
        try:
            raw = self.state_path.read_text()
        except FileNotFoundError:
            return {}
        except OSError as e:
            log.warning("agent.state_read_failed", agent=self.name, error=str(e))
            return {}
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError as e:
            log.warning("agent.state_corrupt", agent=self.name, error=str(e))
            return {}
        if not isinstance(parsed, dict):
            log.warning("agent.state_not_object", agent=self.name, type=type(parsed).__name__)
            return {}
        return parsed

    def _save_state(self) -> None:
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.state_path.with_suffix(self.state_path.suffix + ".tmp")
        tmp.write_text(json.dumps(self._state))
        # non-POSIX fs may reject chmod — best-effort; correctness comes from
        # the atomic os.replace below, not from permission bits.
        with contextlib.suppress(OSError):
            os.chmod(tmp, 0o600)
        os.replace(tmp, self.state_path)

    # ------------------------------------------------------------------ health endpoint

    async def _start_health_server(self) -> None:
        self._health_server = await asyncio.start_server(
            self._handle_health_conn, _HEALTH_HOST, self.health_port
        )
        sock = self._health_server.sockets[0]
        self.bound_health_port = sock.getsockname()[1]

    async def _stop_health_server(self) -> None:
        if self._health_server is None:
            return
        self._health_server.close()
        try:
            await asyncio.wait_for(self._health_server.wait_closed(), timeout=5.0)
        except TimeoutError:
            log.warning("agent.health_server_close_timeout", agent=self.name)
        self._health_server = None

    async def _handle_health_conn(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        try:
            with contextlib.suppress(
                TimeoutError, asyncio.IncompleteReadError, asyncio.LimitOverrunError
            ):
                await asyncio.wait_for(reader.readuntil(b"\r\n\r\n"), timeout=1.0)
            body = json.dumps(self._health_payload()).encode()
            resp = (
                b"HTTP/1.1 200 OK\r\n"
                b"Content-Type: application/json\r\n"
                b"Content-Length: " + str(len(body)).encode() + b"\r\n"
                b"Connection: close\r\n\r\n"
            ) + body
            writer.write(resp)
            await writer.drain()
        except (ConnectionError, OSError):
            pass
        finally:
            writer.close()
            with contextlib.suppress(ConnectionError, OSError):
                await writer.wait_closed()

    def _health_payload(self) -> dict[str, Any]:
        uptime = int(time.monotonic() - self._started_at) if self._started_at else 0
        return {
            "agent": self.name,
            "ok": True,
            "uptime_s": uptime,
            "last_notify": self._last_notify.isoformat() if self._last_notify else None,
        }
