from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from backend.api.routes import activity, analytics, dev, disruptions, mitigations, signals
from backend.api.ws import RELAY_CHANNELS, ConnectionManager, _make_relay, ws_updates
from backend.db.bus import EventBus
from backend.db.session import DBSettings
from backend.observability.logging import configure


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    configure()
    manager = ConnectionManager()
    bus = EventBus(DBSettings().database_url)
    app.state.ws_manager = manager
    app.state.bus = bus
    await bus.start()
    for ch in RELAY_CHANNELS:
        await bus.subscribe(ch, _make_relay(manager, ch))
    try:
        yield
    finally:
        await bus.stop()


app = FastAPI(title="suppl.ai", lifespan=lifespan)

app.include_router(signals.router, prefix="/api/signals", tags=["signals"])
app.include_router(disruptions.router, prefix="/api/disruptions", tags=["disruptions"])
app.include_router(mitigations.router, prefix="/api/mitigations", tags=["mitigations"])
app.include_router(analytics.router, prefix="/api/analytics", tags=["analytics"])
app.include_router(activity.router, prefix="/api/activity", tags=["activity"])
app.include_router(dev.router, prefix="/api/dev", tags=["dev"])

app.add_api_websocket_route("/ws/updates", ws_updates)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
