from __future__ import annotations

import asyncio
import json
from typing import Any

import structlog
from fastapi import WebSocket, WebSocketDisconnect

log = structlog.get_logger()

RELAY_CHANNELS = (
    "new_signal",
    "new_disruption",
    "new_impact",
    "new_mitigation",
    "new_approval",
)


class ConnectionManager:
    def __init__(self) -> None:
        self._clients: set[WebSocket] = set()
        self._lock = asyncio.Lock()

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        async with self._lock:
            self._clients.add(ws)
        log.info("ws.connect", client_count=len(self._clients))

    async def disconnect(self, ws: WebSocket) -> None:
        async with self._lock:
            self._clients.discard(ws)
        log.info("ws.disconnect", client_count=len(self._clients))

    async def broadcast(self, message: dict[str, Any]) -> None:
        """Send JSON message to every connected client. Drops dead connections."""
        async with self._lock:
            targets = list(self._clients)
        dead: list[WebSocket] = []
        for ws in targets:
            try:
                await ws.send_json(message)
            except Exception as e:
                log.warning("ws.broadcast_failed", error=str(e))
                dead.append(ws)
        if dead:
            async with self._lock:
                for ws in dead:
                    self._clients.discard(ws)


def _make_relay(manager: ConnectionManager, channel: str) -> Any:
    async def _on_event(payload: str) -> None:
        try:
            parsed: Any = json.loads(payload)
        except json.JSONDecodeError:
            parsed = {"raw": payload}
        await manager.broadcast({"type": channel, "payload": parsed})

    return _on_event


async def ws_updates(ws: WebSocket) -> None:
    manager: ConnectionManager = ws.app.state.ws_manager
    await manager.connect(ws)
    try:
        # Keep the connection alive. Clients can send pings (we don't require them).
        while True:
            msg = await ws.receive_text()  # blocks until client sends or disconnects
            # Client → server messages are optional. Echo pings for keepalive.
            if msg == "ping":
                await ws.send_json({"type": "pong"})
    except WebSocketDisconnect:
        pass
    finally:
        await manager.disconnect(ws)
