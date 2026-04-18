"""Route integration tests.

Uses httpx.AsyncClient with ASGITransport to exercise all route stubs against
the supplai_test DB (conftest.py sets DATABASE_URL to the test DB and truncates
tables before each test).

Each test is self-contained: inserts required fixtures inline, queries, then
assertions. The conftest autouse fixture truncates domain tables before each
test, so no cross-test leakage.
"""

from __future__ import annotations

import uuid
from decimal import Decimal

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import insert, text

from backend.api.main import app
from backend.db.models import ImpactReport, MitigationOption
from backend.db.session import session
from backend.scripts.seed import seed_all

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _get_client() -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


@pytest.fixture
async def seeded():
    """Seed reference data (ports/suppliers/skus/customers/shipments/POs)."""
    async with session() as s:
        await seed_all(s)
        await s.commit()


# ---------------------------------------------------------------------------
# /api/signals
# ---------------------------------------------------------------------------


async def test_list_signals_empty():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.get("/api/signals")
    assert r.status_code == 200
    assert r.json() == []


async def test_list_signals_returns_inserted_signal():
    sig_id = uuid.uuid4()
    async with session() as s:
        await s.execute(
            text(
                "INSERT INTO signals (id, source_category, source_name, title, confidence, "
                "first_seen_at, dedupe_hash, source_urls, raw_payload) "
                "VALUES (:id, 'news', 'test', 'Test signal', 0.5, NOW(), :hash, '{}', '{}')"
            ),
            {"id": sig_id, "hash": uuid.uuid4().hex},
        )
        await s.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.get("/api/signals")
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 1
    assert data[0]["id"] == str(sig_id)


async def test_list_signals_status_filter_active_empty():
    """With no promoted signals, ?status=active should return []."""
    sig_id = uuid.uuid4()
    async with session() as s:
        await s.execute(
            text(
                "INSERT INTO signals (id, source_category, source_name, title, confidence, "
                "first_seen_at, dedupe_hash, source_urls, raw_payload) "
                "VALUES (:id, 'news', 'test', 'Test signal', 0.5, NOW(), :hash, '{}', '{}')"
            ),
            {"id": sig_id, "hash": uuid.uuid4().hex},
        )
        await s.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.get("/api/signals?status=active")
    assert r.status_code == 200
    assert r.json() == []


# ---------------------------------------------------------------------------
# /api/disruptions
# ---------------------------------------------------------------------------


async def _insert_disruption(s_id: uuid.UUID | None = None) -> uuid.UUID:
    did = s_id or uuid.uuid4()
    async with session() as s:
        await s.execute(
            text(
                "INSERT INTO disruptions (id, title, category, severity, confidence, "
                "first_seen_at, last_seen_at, status, source_signal_ids) "
                "VALUES (:id, 'Test disruption', 'news', 3, 0.8, NOW(), NOW(), 'active', '{}')"
            ),
            {"id": did},
        )
        await s.commit()
    return did


async def test_list_disruptions_empty():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.get("/api/disruptions")
    assert r.status_code == 200
    assert r.json() == []


async def test_get_disruption_404_unknown():
    unknown = uuid.uuid4()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.get(f"/api/disruptions/{unknown}")
    assert r.status_code == 404


async def test_get_disruption_200_existing():
    did = await _insert_disruption()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.get(f"/api/disruptions/{did}")
    assert r.status_code == 200
    assert r.json()["id"] == str(did)
    assert r.json()["status"] == "active"


# ---------------------------------------------------------------------------
# /api/disruptions/{id}/impact
# ---------------------------------------------------------------------------


async def test_get_disruption_impact_404_no_impact():
    did = await _insert_disruption()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.get(f"/api/disruptions/{did}/impact")
    assert r.status_code == 404


async def test_get_disruption_impact_404_unknown_disruption():
    unknown = uuid.uuid4()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.get(f"/api/disruptions/{unknown}/impact")
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# /api/disruptions/{id}/mitigations
# ---------------------------------------------------------------------------


async def test_get_disruption_mitigations_404_unknown():
    unknown = uuid.uuid4()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.get(f"/api/disruptions/{unknown}/mitigations")
    assert r.status_code == 404


async def test_get_disruption_mitigations_empty_when_no_impact():
    did = await _insert_disruption()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.get(f"/api/disruptions/{did}/mitigations")
    assert r.status_code == 200
    assert r.json() == []


# ---------------------------------------------------------------------------
# /api/mitigations/:id/approve — must return 501
# ---------------------------------------------------------------------------


async def test_approve_mitigation_returns_501():
    random_id = uuid.uuid4()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.post(f"/api/mitigations/{random_id}/approve")
    assert r.status_code == 501
    body = r.json()
    assert "detail" in body
    assert "9.1" in body["detail"] or "approval" in body["detail"].lower()


# ---------------------------------------------------------------------------
# /api/mitigations/:id/dismiss
# ---------------------------------------------------------------------------


async def _insert_mitigation(disruption_id: uuid.UUID) -> uuid.UUID:
    """Insert an impact report + mitigation option for the given disruption."""
    ir_id = uuid.uuid4()
    mo_id = uuid.uuid4()
    trace_dict: dict[str, object] = {"tool_calls": [], "final_reasoning": "test"}

    async with session() as s:
        await s.execute(
            insert(ImpactReport).values(
                id=ir_id,
                disruption_id=disruption_id,
                total_exposure=Decimal("1000"),
                units_at_risk=5,
                cascade_depth=1,
                reasoning_trace=trace_dict,
            )
        )
        await s.execute(
            insert(MitigationOption).values(
                id=mo_id,
                impact_report_id=ir_id,
                option_type="reroute",
                description="Reroute via Busan",
                delta_cost=Decimal("5000"),
                delta_days=3,
                confidence=Decimal("0.75"),
                rationale="Busan has berths available for rerouting.",
                status="pending",
            )
        )
        await s.commit()
    return mo_id


async def test_dismiss_mitigation_404_unknown():
    unknown = uuid.uuid4()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.post(f"/api/mitigations/{unknown}/dismiss")
    assert r.status_code == 404


async def test_dismiss_mitigation_200_persists():
    did = await _insert_disruption()
    mo_id = await _insert_mitigation(did)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.post(f"/api/mitigations/{mo_id}/dismiss")

    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "dismissed"
    assert body["id"] == str(mo_id)

    # Verify DB actually persisted the change
    async with session() as s:
        row = await s.execute(
            text("SELECT status FROM mitigation_options WHERE id = :id"),
            {"id": mo_id},
        )
        assert row.scalar_one() == "dismissed"


# ---------------------------------------------------------------------------
# /api/analytics/exposure
# ---------------------------------------------------------------------------


async def test_exposure_quarter_empty():
    """No impact data → returns empty list."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.get("/api/analytics/exposure?group_by=quarter")
    assert r.status_code == 200
    assert isinstance(r.json(), list)


async def test_exposure_customer_empty():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.get("/api/analytics/exposure?group_by=customer")
    assert r.status_code == 200
    assert isinstance(r.json(), list)


async def test_exposure_sku_empty():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.get("/api/analytics/exposure?group_by=sku")
    assert r.status_code == 200
    assert isinstance(r.json(), list)


async def test_exposure_invalid_group_by_returns_422():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.get("/api/analytics/exposure?group_by=invalid")
    assert r.status_code == 422


# ---------------------------------------------------------------------------
# /api/activity/feed
# ---------------------------------------------------------------------------


async def test_activity_feed_empty():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.get("/api/activity/feed")
    assert r.status_code == 200
    assert r.json() == []


async def test_activity_feed_returns_inserted_entry():
    async with session() as s:
        await s.execute(
            text(
                "INSERT INTO agent_log (agent_name, trace_id, event_type, payload, ts) "
                "VALUES ('scout', :tid, 'signal_emitted', '{}'::jsonb, NOW())"
            ),
            {"tid": uuid.uuid4()},
        )
        await s.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.get("/api/activity/feed")
    assert r.status_code == 200
    assert len(r.json()) == 1
    assert r.json()[0]["agent_name"] == "scout"


# ---------------------------------------------------------------------------
# /api/dev/scenarios
# ---------------------------------------------------------------------------


async def test_dev_scenarios_returns_five_ids():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.get("/api/dev/scenarios")
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, list)
    assert len(data) == 5
    assert "typhoon_kaia" in data
    assert "busan_strike" in data
    assert "cbam_tariff" in data
    assert "luxshare_fire" in data
    assert "redsea_advisory" in data


# ---------------------------------------------------------------------------
# /api/dev/simulate
# ---------------------------------------------------------------------------


async def test_simulate_valid_scenario_inserts_signal():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.post("/api/dev/simulate", json={"scenario": "typhoon_kaia"})

    assert r.status_code == 200
    body = r.json()
    assert "signal_id" in body
    assert body["scenario"] == "typhoon_kaia"
    assert "Task 11" in body["note"]

    # Verify DB has the row
    sig_id = uuid.UUID(body["signal_id"])
    async with session() as s:
        row = await s.execute(
            text("SELECT source_name FROM signals WHERE id = :id"),
            {"id": sig_id},
        )
        assert row.scalar_one() == "simulate:typhoon_kaia"


async def test_simulate_invalid_scenario_returns_422():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.post("/api/dev/simulate", json={"scenario": "invalid_scenario"})
    assert r.status_code == 422
