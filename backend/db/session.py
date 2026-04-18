from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from functools import cache

from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)


class DBSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/supplai"


@cache
def engine() -> AsyncEngine:
    s = DBSettings()
    return create_async_engine(s.database_url, pool_size=5, max_overflow=5, pool_pre_ping=True)


@cache
def _sessionmaker() -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine(), expire_on_commit=False)


@asynccontextmanager
async def session() -> AsyncIterator[AsyncSession]:
    async with _sessionmaker()() as s:
        yield s
