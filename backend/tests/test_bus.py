import asyncio

import pytest

from backend.db.bus import EventBus


@pytest.mark.asyncio
async def test_publish_subscribe_roundtrip(postgresql_url):
    bus = EventBus(postgresql_url)
    await bus.start()
    received: asyncio.Queue[str] = asyncio.Queue()
    await bus.subscribe("test_ch", received.put_nowait)
    await bus.publish("test_ch", "hello")
    msg = await asyncio.wait_for(received.get(), timeout=2)
    assert msg == "hello"
    await bus.stop()


@pytest.mark.asyncio
async def test_survives_connection_drop(postgresql_url, monkeypatch):
    bus = EventBus(postgresql_url)
    await bus.start()
    received: asyncio.Queue[str] = asyncio.Queue()
    await bus.subscribe("test_ch", received.put_nowait)
    await bus._force_drop_for_test()  # forcibly close underlying conn
    await asyncio.sleep(0.5)  # let reconnect loop kick in
    await bus.publish("test_ch", "after-drop")
    msg = await asyncio.wait_for(received.get(), timeout=3)
    assert msg == "after-drop"
    await bus.stop()
