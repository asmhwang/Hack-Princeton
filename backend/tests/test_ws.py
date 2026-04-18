"""WebSocket relay tests.

These tests verify the LISTEN/NOTIFY → WebSocket relay end-to-end.

Cross-event-loop note: TestClient runs the app on its own anyio event loop in a
background thread. bus.publish() opens a one-shot asyncpg connection (loop-agnostic)
so we can safely call it from a separate event loop. The NOTIFY lands in Postgres,
asyncpg delivers it to the listener running on TestClient's loop, which dispatches
to the relay handler, which broadcasts to connected WS clients.

Timeout note: starlette 1.0.0's WebSocketTestSession.receive_json() has no timeout
parameter. We use a ThreadPoolExecutor to apply a deadline to the blocking call.
"""

from __future__ import annotations

import asyncio
import concurrent.futures
import json

from fastapi.testclient import TestClient

from backend.api.main import app

# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


def _recv(ws, timeout: float = 3.0):
    """Receive a JSON message from ws with a wall-clock timeout (seconds)."""
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
        fut = ex.submit(ws.receive_json)
        return fut.result(timeout=timeout)


def _publish(bus, channel: str, payload: str) -> None:
    """Publish a NOTIFY via bus from a fresh event loop (loop-agnostic)."""
    loop = asyncio.new_event_loop()
    try:
        loop.run_until_complete(bus.publish(channel, payload))
    finally:
        loop.close()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_ws_handshake():
    """Baseline: WS endpoint accepts a connection and responds to ping."""
    with TestClient(app) as client, client.websocket_connect("/ws/updates") as ws:
        ws.send_text("ping")
        msg = _recv(ws)
        assert msg == {"type": "pong"}


def test_ws_bus_dsn_points_to_test_db():
    """Confirm the lifespan bus connects to supplai_test, not the dev DB."""
    with TestClient(app) as client:
        bus = app.state.bus
        assert "supplai_test" in bus._dsn, f"Bus DSN should point at supplai_test; got: {bus._dsn}"
        # Verify WS endpoint works while we're here
        with client.websocket_connect("/ws/updates") as ws:
            ws.send_text("ping")
            msg = _recv(ws)
            assert msg == {"type": "pong"}


def test_ws_relays_new_signal():
    """End-to-end: NOTIFY new_signal → connected WS client receives matching message."""
    with TestClient(app) as client, client.websocket_connect("/ws/updates") as ws:
        bus = app.state.bus
        payload = json.dumps(
            {"id": "11111111-1111-1111-1111-111111111111", "source_category": "weather"}
        )
        _publish(bus, "new_signal", payload)
        msg = _recv(ws)
        assert msg["type"] == "new_signal"
        assert msg["payload"]["id"] == "11111111-1111-1111-1111-111111111111"
        assert msg["payload"]["source_category"] == "weather"


def test_ws_relays_all_five_channels():
    """Each of the 5 frozen channels round-trips cleanly."""
    channels = {
        "new_signal": {"id": "aaa", "source_category": "policy"},
        "new_disruption": {"id": "bbb", "severity": 4},
        "new_impact": {"id": "ccc", "disruption_id": "ddd", "total_exposure": "1000000.00"},
        "new_mitigation": {"id": "eee", "impact_report_id": "fff"},
        "new_approval": {"id": "ggg", "mitigation_id": "hhh"},
    }
    with TestClient(app) as client, client.websocket_connect("/ws/updates") as ws:
        bus = app.state.bus
        loop = asyncio.new_event_loop()
        try:
            for ch, pl in channels.items():
                loop.run_until_complete(bus.publish(ch, json.dumps(pl)))
        finally:
            loop.close()

        received: dict[str, dict] = {}
        for _ in range(5):
            msg = _recv(ws)
            received[msg["type"]] = msg["payload"]

        for ch, expected in channels.items():
            assert received[ch] == expected, (
                f"channel {ch}: expected {expected}, got {received.get(ch)}"
            )


def test_ws_broadcasts_to_multiple_clients():
    """Two clients connected simultaneously both receive each broadcast."""
    with (
        TestClient(app) as client,
        client.websocket_connect("/ws/updates") as ws1,
        client.websocket_connect("/ws/updates") as ws2,
    ):
        bus = app.state.bus
        _publish(bus, "new_signal", '{"id":"x","source_category":"news"}')
        m1 = _recv(ws1)
        m2 = _recv(ws2)
        assert (
            m1
            == m2
            == {
                "type": "new_signal",
                "payload": {"id": "x", "source_category": "news"},
            }
        )


def test_ws_malformed_payload_forwarded_as_raw():
    """If a NOTIFY payload is not JSON, relay forwards it as {raw: <str>} (don't crash)."""
    with TestClient(app) as client, client.websocket_connect("/ws/updates") as ws:
        bus = app.state.bus
        _publish(bus, "new_signal", "not valid json")
        msg = _recv(ws)
        assert msg["type"] == "new_signal"
        assert msg["payload"] == {"raw": "not valid json"}
