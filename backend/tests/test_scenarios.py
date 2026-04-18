"""Tests for the 5 demo scenario fixtures and their wiring into /api/dev/simulate.

Covers:
1. Schema integrity for every scenario (severity, confidence, category, expectation ranges).
2. SCENARIOS dict completeness (all 5 IDs present).
3. /api/dev/simulate inserts both signal and disruption rows with correct cross-references.
4. Simulating the same scenario twice produces two distinct disruptions.
5. Simulating an unknown scenario returns 422.
6. Response expected block matches ScenarioExpectation fields.
"""

from __future__ import annotations

import dataclasses
import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from backend.api.main import app
from backend.db.session import session
from backend.scripts.scenarios import SCENARIOS
from backend.scripts.scenarios._types import DisruptionCategory, Scenario, SourceCategory

_EXPECTED_IDS = [
    "typhoon_kaia",
    "busan_strike",
    "cbam_tariff",
    "luxshare_fire",
    "redsea_advisory",
]

_VALID_SOURCE_CATEGORIES: set[str] = set(SourceCategory.__args__)  # type: ignore[attr-defined]
_VALID_DISRUPTION_CATEGORIES: set[str] = set(DisruptionCategory.__args__)  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# 1. Schema integrity — validate every scenario's fields
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("scenario_id", _EXPECTED_IDS)
def test_scenario_signal_severity_in_range(scenario_id: str) -> None:
    s: Scenario = SCENARIOS[scenario_id]  # type: ignore[assignment]
    assert 1 <= s.signal.severity <= 5, (
        f"{scenario_id}: signal.severity={s.signal.severity} not in [1,5]"
    )


@pytest.mark.parametrize("scenario_id", _EXPECTED_IDS)
def test_scenario_signal_confidence_in_range(scenario_id: str) -> None:
    s: Scenario = SCENARIOS[scenario_id]  # type: ignore[assignment]
    assert 0 <= s.signal.confidence <= 1, (
        f"{scenario_id}: signal.confidence={s.signal.confidence} not in [0,1]"
    )


@pytest.mark.parametrize("scenario_id", _EXPECTED_IDS)
def test_scenario_signal_source_category_valid(scenario_id: str) -> None:
    s: Scenario = SCENARIOS[scenario_id]  # type: ignore[assignment]
    assert s.signal.source_category in _VALID_SOURCE_CATEGORIES, (
        f"{scenario_id}: signal.source_category='{s.signal.source_category}' invalid"
    )


@pytest.mark.parametrize("scenario_id", _EXPECTED_IDS)
def test_scenario_disruption_category_valid(scenario_id: str) -> None:
    s: Scenario = SCENARIOS[scenario_id]  # type: ignore[assignment]
    assert s.disruption.category in _VALID_DISRUPTION_CATEGORIES, (
        f"{scenario_id}: disruption.category='{s.disruption.category}' invalid"
    )


@pytest.mark.parametrize("scenario_id", _EXPECTED_IDS)
def test_scenario_expectation_ranges_consistent(scenario_id: str) -> None:
    s: Scenario = SCENARIOS[scenario_id]  # type: ignore[assignment]
    exp = s.expected
    assert exp.affected_shipments_min <= exp.affected_shipments_max, (
        f"{scenario_id}: affected_shipments_min > max"
    )
    assert exp.exposure_usd_min <= exp.exposure_usd_max, f"{scenario_id}: exposure_usd_min > max"


@pytest.mark.parametrize("scenario_id", _EXPECTED_IDS)
def test_scenario_id_field_matches_dict_key(scenario_id: str) -> None:
    s: Scenario = SCENARIOS[scenario_id]  # type: ignore[assignment]
    assert s.id == scenario_id, f"SCENARIOS['{scenario_id}'].id='{s.id}' doesn't match dict key"


# ---------------------------------------------------------------------------
# 2. SCENARIOS dict completeness
# ---------------------------------------------------------------------------


def test_scenarios_dict_has_exactly_five_ids() -> None:
    assert set(SCENARIOS.keys()) == set(_EXPECTED_IDS), (
        f"SCENARIOS keys mismatch: {sorted(SCENARIOS.keys())} != {sorted(_EXPECTED_IDS)}"
    )


# ---------------------------------------------------------------------------
# 3. /api/dev/simulate inserts both signal + disruption
# ---------------------------------------------------------------------------


async def test_simulate_inserts_signal_and_disruption() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.post("/api/dev/simulate", json={"scenario": "typhoon_kaia"})

    assert r.status_code == 200
    body = r.json()
    assert "signal_id" in body
    assert "disruption_id" in body
    assert body["scenario"] == "typhoon_kaia"

    sig_id = uuid.UUID(body["signal_id"])
    dis_id = uuid.UUID(body["disruption_id"])

    async with session() as s:
        sig_row = await s.execute(
            text("SELECT source_name, promoted_to_disruption_id FROM signals WHERE id = :id"),
            {"id": sig_id},
        )
        sig = sig_row.one()
        assert sig.source_name == "tavily:news:scmp"
        assert sig.promoted_to_disruption_id == dis_id

        dis_row = await s.execute(
            text("SELECT category, severity, source_signal_ids FROM disruptions WHERE id = :id"),
            {"id": dis_id},
        )
        dis = dis_row.one()
        assert dis.category == "weather"
        assert dis.severity == 4
        assert str(sig_id) in [str(x) for x in dis.source_signal_ids]


# ---------------------------------------------------------------------------
# 4. Simulating the same scenario twice produces two distinct disruptions
# ---------------------------------------------------------------------------


async def test_simulate_twice_produces_two_disruptions() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r1 = await c.post("/api/dev/simulate", json={"scenario": "busan_strike"})
        r2 = await c.post("/api/dev/simulate", json={"scenario": "busan_strike"})

    assert r1.status_code == 200
    assert r2.status_code == 200

    dis_id_1 = r1.json()["disruption_id"]
    dis_id_2 = r2.json()["disruption_id"]
    sig_id_1 = r1.json()["signal_id"]
    sig_id_2 = r2.json()["signal_id"]

    assert dis_id_1 != dis_id_2, "Two simulations must produce distinct disruption IDs"
    assert sig_id_1 != sig_id_2, "Two simulations must produce distinct signal IDs"

    # Both disruptions should exist in DB
    async with session() as s:
        count_row = await s.execute(
            text("SELECT COUNT(*) FROM disruptions WHERE id IN (:id1, :id2)"),
            {"id1": uuid.UUID(dis_id_1), "id2": uuid.UUID(dis_id_2)},
        )
        assert count_row.scalar_one() == 2


# ---------------------------------------------------------------------------
# 5. Simulating an unknown scenario returns 422
# ---------------------------------------------------------------------------


async def test_simulate_unknown_scenario_returns_422() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.post("/api/dev/simulate", json={"scenario": "not_a_real_scenario"})
    assert r.status_code == 422


# ---------------------------------------------------------------------------
# 6. Response expected block matches ScenarioExpectation fields
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("scenario_id", _EXPECTED_IDS)
async def test_simulate_response_expected_matches_fixture(scenario_id: str) -> None:
    """The response's 'expected' dict must match the scenario fixture's ScenarioExpectation."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.post("/api/dev/simulate", json={"scenario": scenario_id})

    assert r.status_code == 200
    body = r.json()
    assert "expected" in body

    scenario: Scenario = SCENARIOS[scenario_id]  # type: ignore[assignment]
    fixture_expected = dataclasses.asdict(scenario.expected)
    assert body["expected"] == fixture_expected, (
        f"{scenario_id}: response expected mismatch.\n"
        f"  got:      {body['expected']}\n"
        f"  expected: {fixture_expected}"
    )
