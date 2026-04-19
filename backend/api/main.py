from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

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

# Allow the Next.js frontend (dev + prod + Vercel preview deploys) to call us
# from the browser. Without this the browser silently blocks every fetch.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "https://suppl-ai-seven.vercel.app",
    ],
    allow_origin_regex=r"https://.*\.(vercel\.app|ngrok-free\.dev|ngrok\.app|ngrok\.io)",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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
