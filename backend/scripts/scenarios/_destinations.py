"""Per-scenario destination map.

Each active scenario pairs its disruption centroid (the origin) with a
geographically-sensible destination port. Consumed by
``backend/scripts/scenarios/prime_chain.py`` so the seeded shipments have
distinct origin/destination coords instead of zero-length routes.
"""

from __future__ import annotations

# scenario_id -> (name, lat, lng)
SCENARIO_DESTINATIONS: dict[str, tuple[str, float, float]] = {
    "typhoon_kaia": ("Los Angeles", 34.05, -118.24),
    "busan_strike": ("Seattle", 47.61, -122.33),
    "cbam_tariff": ("Rotterdam", 51.92, 4.48),
    "luxshare_fire": ("Hong Kong", 22.32, 114.17),
    "redsea_advisory": ("Rotterdam", 51.92, 4.48),
}
