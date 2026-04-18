"""pytest configuration for backend tests.

Fixture strategy: use the already-migrated dev DB (localhost:5432/supplai) and
TRUNCATE all domain tables before each test that needs a clean slate.

Two problems solved here:
1. Cross-loop issues: the SQLAlchemy @cache'd engine/sessionmaker binds its
   connection pool to the event loop it was first created in.  pytest-asyncio
   uses a new loop per test function, so we must clear the lru_cache between
   tests so a fresh engine is created in the current test's loop.
2. Clean state: we use raw asyncpg (no SQLAlchemy pool) for TRUNCATE so the
   truncation itself never touches the cached pool.
"""

from __future__ import annotations

import asyncpg
import pytest

from backend.db.session import _sessionmaker, engine

_DSN = "postgresql://postgres:postgres@localhost:5432/supplai"

_TRUNCATE_SQL = (
    "TRUNCATE ports, suppliers, skus, customers, "
    "purchase_orders, shipments "
    "RESTART IDENTITY CASCADE"
)


@pytest.fixture(autouse=True)
async def _clean_db_state() -> None:  # type: ignore[return]
    """Clear the SQLAlchemy engine cache and truncate domain tables before each test."""
    # Clear cached engine/sessionmaker so a new one is created in the current
    # event loop — prevents "attached to a different loop" errors.
    engine.cache_clear()
    _sessionmaker.cache_clear()

    # Truncate via raw asyncpg — no pool, no loop binding issues.
    conn = await asyncpg.connect(_DSN)
    try:
        await conn.execute(_TRUNCATE_SQL)
    finally:
        await conn.close()
