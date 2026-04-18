"""TDD for Scout severity rubric (PRD §5.2.1).

Rubric (base = 1, clamp 1..5):

| Branch | Condition                                                    | +Δ |
|--------|--------------------------------------------------------------|----|
| (a)    | Any port OR supplier within 500km of signal coords           | +2 |
| (b)    | Keyword match: named storm, sanction, strike, fire, flood    | +1 |
| (c)    | ≥2 source categories concur on same region within 24h        | +1 |
| (d)    | Impact radius > 300km                                        | +1 |

Tests drive eight parametrized branches as required by the worktree plan.

The haversine helper is tested independently against a known pair
(NYC ↔ Boston ≈ 306 km) — drift here would silently break branch (a).
"""

from __future__ import annotations

import pytest

from backend.agents.scout.processors.severity import haversine_km, score_severity


def test_haversine_nyc_to_boston() -> None:
    # NYC (40.7128, -74.0060) to Boston (42.3601, -71.0589) ≈ 306 km
    d = haversine_km((40.7128, -74.0060), (42.3601, -71.0589))
    assert 290.0 < d < 320.0


SIGNAL_COORDS = (25.0, 121.0)  # Taiwan
NEAR_PORT = [(25.1, 121.2)]  # ~22 km away, triggers (a)
FAR_PORT = [(0.0, 0.0)]  # thousands of km, no trigger


@pytest.mark.parametrize(
    ("keywords", "radius", "ports_suppliers", "recent_same_region", "expected"),
    [
        # 1. no branches trigger → base 1
        ([], 10.0, FAR_PORT, 0, 1),
        # 2. only (a): port within 500km → 1 + 2 = 3
        ([], 10.0, NEAR_PORT, 0, 3),
        # 3. only (b): trigger keyword → 1 + 1 = 2
        (["typhoon"], 10.0, FAR_PORT, 0, 2),
        # 4. (a) + (b) → 1 + 2 + 1 = 4
        (["sanction"], 10.0, NEAR_PORT, 0, 4),
        # 5. (a) + (b) + (c): recent_same_region >= 2 → 1 + 2 + 1 + 1 = 5
        (["strike"], 10.0, NEAR_PORT, 2, 5),
        # 6. (a) + (b) + (c) + (d): radius > 300 → clamped at 5
        (["fire"], 500.0, NEAR_PORT, 2, 5),
        # 7. only (d): radius > 300 → 1 + 1 = 2
        ([], 500.0, FAR_PORT, 0, 2),
        # 8. boundary: radius == 300 is NOT > 300 (exclusive) → 1
        ([], 300.0, FAR_PORT, 0, 1),
    ],
)
def test_score_severity_branches(
    keywords: list[str],
    radius: float,
    ports_suppliers: list[tuple[float, float]],
    recent_same_region: int,
    expected: int,
) -> None:
    score = score_severity(
        coords=SIGNAL_COORDS,
        keywords=keywords,
        impact_radius_km=radius,
        ports_suppliers=ports_suppliers,
        recent_signals_same_region=recent_same_region,
    )
    assert score == expected


def test_score_never_exceeds_five() -> None:
    score = score_severity(
        coords=SIGNAL_COORDS,
        keywords=["typhoon", "flood", "fire"],
        impact_radius_km=9999.0,
        ports_suppliers=NEAR_PORT * 10,
        recent_signals_same_region=99,
    )
    assert score == 5


def test_score_never_below_one() -> None:
    score = score_severity(
        coords=SIGNAL_COORDS,
        keywords=[],
        impact_radius_km=0.0,
        ports_suppliers=[],
        recent_signals_same_region=0,
    )
    assert score == 1
