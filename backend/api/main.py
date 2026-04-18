from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from backend.api.routes import activity, analytics, dev, disruptions, mitigations, signals
from backend.observability.logging import configure


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    configure()
    yield


app = FastAPI(title="suppl.ai", lifespan=lifespan)

app.include_router(signals.router, prefix="/api/signals", tags=["signals"])
app.include_router(disruptions.router, prefix="/api/disruptions", tags=["disruptions"])
app.include_router(mitigations.router, prefix="/api/mitigations", tags=["mitigations"])
app.include_router(analytics.router, prefix="/api/analytics", tags=["analytics"])
app.include_router(activity.router, prefix="/api/activity", tags=["activity"])
app.include_router(dev.router, prefix="/api/dev", tags=["dev"])


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
