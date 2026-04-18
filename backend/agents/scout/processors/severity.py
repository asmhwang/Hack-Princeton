"""Scout severity rubric (PRD §5.2.1).

Pure function — no I/O. Callers preload the DB-side inputs (nearby ports/
suppliers and a recent-signal count) and hand them in so unit tests stay
deterministic.

Scoring (base = 1, clamp to ``[1, 5]``):

| Branch | Condition                                                    | +Δ |
|--------|--------------------------------------------------------------|----|
| (a)    | Any port OR supplier within 500km of signal coords           | +2 |
| (b)    | Signal keyword matches named-storm / sanction / strike / fire / flood | +1 |
| (c)    | ≥2 source categories concur on same region within 24h        | +1 |
| (d)    | Impact radius > 300km                                        | +1 |

Branch (a) uses haversine great-circle distance. The helper is exported and
unit-tested independently so the severity calculation stays reviewable.
"""

from __future__ import annotations

from collections.abc import Iterable
from math import asin, cos, radians, sin, sqrt

_EARTH_RADIUS_KM = 6371.0

_SEVERITY_KEYWORDS = frozenset(
    {
        "typhoon",
        "hurricane",
        "cyclone",
        "named storm",
        "sanction",
        "strike",
        "walkout",
        "fire",
        "flood",
    }
)

_BRANCH_A_RADIUS_KM = 500.0
_BRANCH_D_RADIUS_KM = 300.0
_BRANCH_C_MIN_CONCURRENT = 2
_MIN_SEVERITY = 1
_MAX_SEVERITY = 5


def haversine_km(a: tuple[float, float], b: tuple[float, float]) -> float:
    """Great-circle distance between ``(lat, lng)`` pairs, in kilometres."""
    lat1, lng1 = radians(a[0]), radians(a[1])
    lat2, lng2 = radians(b[0]), radians(b[1])
    dlat = lat2 - lat1
    dlng = lng2 - lng1
    h = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlng / 2) ** 2
    return 2 * _EARTH_RADIUS_KM * asin(sqrt(h))


def _has_nearby_port_or_supplier(
    coords: tuple[float, float],
    ports_suppliers: Iterable[tuple[float, float]],
) -> bool:
    return any(haversine_km(coords, point) <= _BRANCH_A_RADIUS_KM for point in ports_suppliers)


def _has_severity_keyword(keywords: Iterable[str]) -> bool:
    return any(k.strip().lower() in _SEVERITY_KEYWORDS for k in keywords)


def score_severity(
    *,
    coords: tuple[float, float],
    keywords: list[str],
    impact_radius_km: float,
    ports_suppliers: Iterable[tuple[float, float]],
    recent_signals_same_region: int,
) -> int:
    """Apply the Scout severity rubric and return an integer in ``[1, 5]``.

    Parameters
    ----------
    coords
        Signal location (lat, lng).
    keywords
        Signal keywords — matched case-insensitively against the keyword set.
    impact_radius_km
        Radius associated with the signal; branch (d) fires when ``> 300``.
    ports_suppliers
        Pre-filtered iterable of nearby port/supplier ``(lat, lng)`` tuples.
    recent_signals_same_region
        Count of distinct source categories within a 24h window on the same
        region (excluding the current signal). Branch (c) fires at ``>= 2``.
    """
    score = 1
    if _has_nearby_port_or_supplier(coords, ports_suppliers):
        score += 2
    if _has_severity_keyword(keywords):
        score += 1
    if recent_signals_same_region >= _BRANCH_C_MIN_CONCURRENT:
        score += 1
    if impact_radius_km > _BRANCH_D_RADIUS_KM:
        score += 1
    return max(_MIN_SEVERITY, min(_MAX_SEVERITY, score))
