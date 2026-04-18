from __future__ import annotations

from backend.scripts.scenarios._types import (
    Scenario,
    ScenarioDisruption,
    ScenarioExpectation,
    ScenarioSignal,
)

BUSAN_STRIKE = Scenario(
    id="busan_strike",
    signal=ScenarioSignal(
        source_category="logistics",
        source_name="tavily:logistics:lloyds",
        title="Dockworker strike paralyzes Busan port",
        summary=(
            "72-hour dockworker strike at Busan New Port has halted container operations."
            " Carriers diverting to Kaohsiung and Incheon. Estimated 400 TEU backlog per"
            " day, recovery timeline uncertain."
        ),
        region="Northeast Asia",
        lat=35.10,
        lng=129.04,
        radius_km=50,
        source_urls=["https://www.example.com/logistics/busan-strike"],
        severity=3,
        confidence=0.88,
        dedupe_keywords=["busan", "strike", "dockworker", "kaohsiung"],
    ),
    disruption=ScenarioDisruption(
        title="Dockworker strike paralyzes Busan port",
        summary=(
            "72-hour dockworker strike at Busan New Port has halted container operations."
            " Carriers diverting to Kaohsiung and Incheon. Estimated 400 TEU backlog per"
            " day, recovery timeline uncertain."
        ),
        category="logistics",
        severity=3,
        region="Northeast Asia",
        lat=35.10,
        lng=129.04,
        radius_km=50,
        confidence=0.88,
    ),
    expected=ScenarioExpectation(
        affected_shipments_min=6,
        affected_shipments_max=10,
        exposure_usd_min=1_100_000,
        exposure_usd_max=1_700_000,
        dominant_mitigation="reroute",
        notes="Analyst should identify Busan-origin shipments and suggest reroute to Kaohsiung.",
    ),
)
