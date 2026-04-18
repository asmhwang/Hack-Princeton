"""TDD: AgentBase lifecycle + checkpoint persistence.

Per master plan §2.5 Step 1 + WORKTREE_PLAN.md Phase A test spec.

Counter subclass subscribes to a channel, increments a persisted counter on
each payload, and survives a stop/start cycle via the state.json checkpoint.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

from backend.agents.base import AgentBase
from backend.db.bus import EventBus


class _Counter(AgentBase):
    name = "counter"
    channels = ["test_agent_ch"]
    # health_port=0 → ephemeral, avoids collisions under parallel runs
    health_port = 0

    async def on_notify(self, channel: str, payload: str) -> None:
        self._state["n"] = self._state.get("n", 0) + 1


@pytest.mark.asyncio
async def test_checkpoint_survives_restart(
    postgresql_url: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    state_file = tmp_path / "state.json"
    monkeypatch.setattr(_Counter, "state_path", state_file)

    a1 = _Counter(postgresql_url)
    await a1.start()

    pub = EventBus(postgresql_url)
    await pub.start()
    try:
        for _ in range(3):
            await pub.publish("test_agent_ch", "x")
        # give the LISTEN dispatcher time to fire handlers
        for _ in range(20):
            await asyncio.sleep(0.05)
            if a1._state.get("n", 0) >= 3:
                break
    finally:
        await pub.stop()

    assert a1._state.get("n") == 3
    await a1.stop()

    # state.json must exist and contain the counter
    assert state_file.exists()
    saved = json.loads(state_file.read_text())
    assert saved["n"] == 3

    # Restart: fresh instance loads checkpoint
    a2 = _Counter(postgresql_url)
    await a2.start()
    try:
        assert a2._state["n"] == 3
    finally:
        await a2.stop()


@pytest.mark.asyncio
async def test_handler_exception_does_not_crash_listener(
    postgresql_url: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A bad payload must not propagate out of the dispatcher."""

    class _Boom(AgentBase):
        name = "boom"
        channels = ["test_boom_ch"]
        health_port = 0

        def __init__(self, dsn: str) -> None:
            super().__init__(dsn)
            self.calls = 0

        async def on_notify(self, channel: str, payload: str) -> None:
            self.calls += 1
            if payload == "bad":
                raise RuntimeError("boom")
            self._state["ok"] = self._state.get("ok", 0) + 1

    monkeypatch.setattr(_Boom, "state_path", tmp_path / "boom.json")

    agent = _Boom(postgresql_url)
    await agent.start()
    pub = EventBus(postgresql_url)
    await pub.start()
    try:
        await pub.publish("test_boom_ch", "bad")
        await pub.publish("test_boom_ch", "good")
        for _ in range(20):
            await asyncio.sleep(0.05)
            if agent.calls >= 2:
                break
    finally:
        await pub.stop()

    assert agent.calls >= 2
    assert agent._state.get("ok") == 1
    await agent.stop()


@pytest.mark.asyncio
async def test_corrupt_state_json_does_not_crash_startup(
    postgresql_url: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    state_file = tmp_path / "state.json"
    state_file.write_text("{not valid json")
    monkeypatch.setattr(_Counter, "state_path", state_file)

    agent = _Counter(postgresql_url)
    await agent.start()
    try:
        assert agent._state == {}
    finally:
        await agent.stop()


@pytest.mark.asyncio
async def test_health_endpoint_reports_ok(
    postgresql_url: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(_Counter, "state_path", tmp_path / "state.json")
    agent = _Counter(postgresql_url)
    await agent.start()
    try:
        port = agent.bound_health_port
        assert port > 0
        reader, writer = await asyncio.open_connection("127.0.0.1", port)
        writer.write(b"GET /health HTTP/1.1\r\nHost: localhost\r\n\r\n")
        await writer.drain()
        raw = await asyncio.wait_for(reader.read(4096), timeout=2)
        writer.close()
        await writer.wait_closed()
    finally:
        await agent.stop()

    head, _, body = raw.partition(b"\r\n\r\n")
    assert b"200 OK" in head
    payload = json.loads(body)
    assert payload["agent"] == "counter"
    assert payload["ok"] is True
    assert "uptime_s" in payload
