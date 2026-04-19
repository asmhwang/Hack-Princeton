"""Per-scenario destination map.

Each active scenario pairs its disruption centroid (the origin) with
three geographically-sensible destination ports so the three seeded
shipments render as three distinct arcs on the globe instead of
stacking on top of each other. Consumed by
``backend/scripts/scenarios/prime_chain.py``.
"""

from __future__ import annotations

Destination = tuple[str, float, float]  # (name, lat, lng)

# scenario_id -> 3 destinations, indexed 0..2 by shipment position.
SCENARIO_DESTINATIONS: dict[str, list[Destination]] = {
    # Each tuple-triple is picked so the three arcs diverge across different
    # continents / ocean basins — far enough apart to read as distinct lanes
    # on the globe at the default zoom.
    "typhoon_kaia": [
        ("Los Angeles", 34.05, -118.24),   # trans-Pacific, US West
        ("Hamburg", 53.55, 9.99),          # round-the-world, EU North
        ("Santos", -23.97, -46.33),        # Pacific + Atlantic, Brazil
    ],
    "busan_strike": [
        ("Long Beach", 33.77, -118.19),    # US West
        ("Rotterdam", 51.92, 4.48),        # trans-Siberian sea, EU
        ("Sydney", -33.86, 151.21),        # Southern hemisphere
    ],
    "cbam_tariff": [
        ("New York", 40.71, -74.01),       # trans-Atlantic, US East
        ("Houston", 29.76, -95.37),        # US Gulf
        ("Tokyo", 35.68, 139.69),          # trans-Siberian rail, Asia
    ],
    "luxshare_fire": [
        ("Los Angeles", 34.05, -118.24),   # trans-Pacific
        ("Frankfurt", 50.11, 8.68),        # air freight, EU
        ("Chennai", 13.08, 80.27),         # Indian subcontinent
    ],
    "redsea_advisory": [
        ("New York", 40.71, -74.01),       # trans-Atlantic
        ("Houston", 29.76, -95.37),        # US Gulf
        ("Singapore", 1.35, 103.82),       # Asia-Pacific via Suez bypass
    ],
}
