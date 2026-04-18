from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from backend.observability.logging import configure


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    configure()
    yield


app = FastAPI(title="suppl.ai", lifespan=lifespan)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
