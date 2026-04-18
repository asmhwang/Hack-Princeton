"""pytest configuration for backend tests.

Fixture strategy: use a dedicated test DB (supplai_test) so pytest never
touches the developer's working supplai DB.

Two problems solved here:
1. Cross-loop issues: the SQLAlchemy @cache'd engine/sessionmaker binds its
   connection pool to the event loop it was first created in.  pytest-asyncio
   uses a new loop per test function, so we must clear the lru_cache between
   tests so a fresh engine is created in the current test's loop.
2. Clean state: we use raw asyncpg (no SQLAlchemy pool) for TRUNCATE so the
   truncation itself never touches the cached pool.
3. Test isolation: tests run against supplai_test, not the dev supplai DB.
   The session-scoped fixture creates the DB and runs alembic migrations if
   they haven't been run yet.
"""

from __future__ import annotations

import asyncio
import os
import subprocess
from collections.abc import Iterator

import asyncpg
import pytest

from backend.db.session import _sessionmaker, engine

# ---------------------------------------------------------------------------
# DSN constants — SQLAlchemy needs +asyncpg driver prefix; asyncpg does not.
# ---------------------------------------------------------------------------

_TEST_DB_NAME = "supplai_test"
_ADMIN_DSN = "postgresql://postgres:postgres@localhost:5432/postgres"
_TEST_DSN_ASYNCPG = f"postgresql://postgres:postgres@localhost:5432/{_TEST_DB_NAME}"
_TEST_DSN_SQLALCHEMY = f"postgresql+asyncpg://postgres:postgres@localhost:5432/{_TEST_DB_NAME}"

# Point SQLAlchemy at the test DB.  Must be set before any call to engine()
# so DBSettings() picks it up.  Module-level assignment runs before any
# fixture or test function calls engine().
os.environ["DATABASE_URL"] = _TEST_DSN_SQLALCHEMY

_TRUNCATE_SQL = (
    "TRUNCATE ports, suppliers, skus, customers, "
    "purchase_orders, shipments, "
    "signals, disruptions, impact_reports, affected_shipments, "
    "mitigation_options, draft_communications, approvals, agent_log "
    "RESTART IDENTITY CASCADE"
)


# ---------------------------------------------------------------------------
# Session-scoped: create the test DB and run migrations once per pytest run.
# ---------------------------------------------------------------------------


# Mutable container avoids a `global` statement (ruff PLW0603) while still
# letting fixtures share a session-wide flag.
_pg: dict[str, bool] = {"available": False}


@pytest.fixture(scope="session", autouse=True)
def _ensure_test_db() -> None:
    """Create supplai_test and run alembic migrations if Postgres is reachable.

    If Postgres is not running (e.g. LLM-only worktree with no DB dependency),
    silently skip DB setup. DB-dependent tests will still fail loudly when they
    try to open a session; tests that do not touch the DB run unaffected.
    """

    async def _create_db_if_missing() -> bool:
        try:
            conn = await asyncpg.connect(_ADMIN_DSN, timeout=3)
        except (OSError, asyncpg.PostgresError):
            return False
        try:
            exists = await conn.fetchval(
                "SELECT 1 FROM pg_database WHERE datname = $1", _TEST_DB_NAME
            )
            if not exists:
                # CREATE DATABASE cannot run inside a transaction block.
                await conn.execute(f'CREATE DATABASE "{_TEST_DB_NAME}"')
        finally:
            await conn.close()
        return True

    _pg["available"] = asyncio.run(_create_db_if_missing())
    if not _pg["available"]:
        return

    # Run alembic upgrade head against the test DB.
    env = {**os.environ, "DATABASE_URL": _TEST_DSN_SQLALCHEMY}
    result = subprocess.run(
        ["uv", "run", "alembic", "upgrade", "head"],
        env=env,
        capture_output=True,
        text=True,
        check=False,
        cwd=os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"alembic upgrade head failed against {_TEST_DB_NAME}:\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )


# ---------------------------------------------------------------------------
# Per-test: clear engine cache and truncate domain tables.
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
async def _clean_db_state() -> None:  # type: ignore[return]
    """Clear the SQLAlchemy engine cache and truncate domain tables before each test."""
    # Clear cached engine/sessionmaker so a new one is created in the current
    # event loop — prevents "attached to a different loop" errors.
    engine.cache_clear()
    _sessionmaker.cache_clear()

    if not _pg["available"]:
        return

    # Truncate via raw asyncpg — no pool, no loop binding issues.
    conn = await asyncpg.connect(_TEST_DSN_ASYNCPG)
    try:
        await conn.execute(_TRUNCATE_SQL)
    finally:
        await conn.close()


# ---------------------------------------------------------------------------
# Shared DSN fixture — used by the event-bus tests (EventBus normalises the
# SQLAlchemy-style prefix internally, so we hand over the same URL form as
# backend/db/session.py uses).
# ---------------------------------------------------------------------------


@pytest.fixture
def postgresql_url() -> Iterator[str]:
    yield _TEST_DSN_SQLALCHEMY
