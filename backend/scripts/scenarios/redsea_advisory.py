from __future__ import annotations

from backend.scripts.scenarios._types import (
    Scenario,
    ScenarioDisruption,
    ScenarioExpectation,
    ScenarioSignal,
)

REDSEA_ADVISORY = Scenario(
    id="redsea_advisory",
    signal=ScenarioSignal(
        source_category="logistics",
        source_name="tavily:logistics:alphaliner",
        title="Red Sea shipping advisory: carriers rerouting via Cape of Good Hope",
        summary=(
            "Major carriers (Maersk, MSC, CMA CGM) announced suspension of Red Sea"
            " transits due to security concerns. Cape of Good Hope rerouting adds 10-14"
            " days per voyage. Asia-Europe freight rates up 40%. Impact hits Suez-bound"
            " containers from Indian Ocean and Far East."
        ),
        region="Red Sea / Bab-el-Mandeb",
        lat=12.58,
        lng=43.33,
        radius_km=800,
        source_urls=["https://www.example.com/logistics/red-sea-advisory"],
        severity=3,
        confidence=0.91,
        dedupe_keywords=["red_sea", "suez", "cape_of_good_hope", "maersk", "reroute"],
    ),
    disruption=ScenarioDisruption(
        title="Red Sea shipping advisory: carriers rerouting via Cape of Good Hope",
        summary=(
            "Major carriers (Maersk, MSC, CMA CGM) announced suspension of Red Sea"
            " transits due to security concerns. Cape of Good Hope rerouting adds 10-14"
            " days per voyage. Asia-Europe freight rates up 40%. Impact hits Suez-bound"
            " containers from Indian Ocean and Far East."
        ),
        category="policy",
        severity=3,
        region="Red Sea / Bab-el-Mandeb",
        lat=12.58,
        lng=43.33,
        radius_km=800,
        confidence=0.91,
    ),
    expected=ScenarioExpectation(
        affected_shipments_min=18,
        affected_shipments_max=25,
        exposure_usd_min=2_700_000,
        exposure_usd_max=3_500_000,
        dominant_mitigation="accept_delay",
        notes=(
            "Analyst should identify all Asia-Europe transit shipments. A subset may"
            " justify 'expedite' for highest-priority SLA orders."
        ),
    ),
)
