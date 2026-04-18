from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import Any

import asyncpg
import structlog

log = structlog.get_logger()
Handler = Callable[[str], Awaitable[None] | None]


class EventBus:
    def __init__(self, dsn: str) -> None:
        self._dsn = dsn.replace("postgresql+asyncpg://", "postgresql://")
        self._conn: asyncpg.Connection[Any] | None = None
        self._subs: dict[str, list[Handler]] = {}
        self._reconnect_task: asyncio.Task[None] | None = None
        self._stop = asyncio.Event()

    async def start(self) -> None:
        self._stop.clear()
        await self._ensure_conn()
        self._reconnect_task = asyncio.create_task(self._reconnect_loop())

    async def stop(self) -> None:
        self._stop.set()
        if self._reconnect_task:
            self._reconnect_task.cancel()
        if self._conn:
            await self._conn.close()
            self._conn = None

    async def subscribe(self, channel: str, handler: Handler) -> None:
        self._subs.setdefault(channel, []).append(handler)
        if self._conn:
            await self._conn.add_listener(channel, self._dispatch)

    async def publish(self, channel: str, payload: str) -> None:
        conn = await asyncpg.connect(self._dsn)
        try:
            # pg_notify() function form accepts parameters; NOTIFY statement form does not.
            await conn.execute("SELECT pg_notify($1, $2)", channel, payload)
        finally:
            await conn.close()

    async def _ensure_conn(self) -> None:
        self._conn = await asyncpg.connect(self._dsn)
        for ch in self._subs:
            await self._conn.add_listener(ch, self._dispatch)

    def _dispatch(
        self,
        _conn: asyncpg.Connection[Any],
        _pid: int,
        channel: str,
        payload: str,
    ) -> None:
        for h in self._subs.get(channel, []):
            res = h(payload)
            if asyncio.iscoroutine(res):
                asyncio.create_task(res)

    async def _reconnect_loop(self) -> None:
        backoff = 1.0
        while not self._stop.is_set():
            if self._conn is None or self._conn.is_closed():
                try:
                    log.warning("bus.reconnect")
                    await self._ensure_conn()
                    backoff = 1.0
                except Exception as e:
                    log.error("bus.reconnect_failed", error=str(e), backoff=backoff)
                    await asyncio.sleep(backoff)
                    backoff = min(backoff * 2, 30.0)
            else:
                await asyncio.sleep(0.1)

    async def _force_drop_for_test(self) -> None:
        if self._conn:
            await self._conn.close()
            self._conn = None
