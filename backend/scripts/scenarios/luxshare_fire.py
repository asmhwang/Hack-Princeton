from __future__ import annotations

from backend.scripts.scenarios._types import (
    Scenario,
    ScenarioDisruption,
    ScenarioExpectation,
    ScenarioSignal,
)

LUXSHARE_FIRE = Scenario(
    id="luxshare_fire",
    signal=ScenarioSignal(
        # NOTE: signal originates from news coverage; disruption category is "industrial"
        # because the underlying event is a supplier facility incident, not a news category.
        source_category="news",
        source_name="tavily:news:reuters",
        title="Fire at Luxshare Vietnam facility halts connector production",
        summary=(
            "A fire at the Luxshare Precision Industry facility in Bắc Giang, Vietnam"
            " halted production of board-to-board connectors and assembly modules."
            " Expected downtime 2-3 weeks. Affected SKUs include PMIC and MCU"
            " sub-assemblies for Tier-1 customers."
        ),
        region="Southeast Asia",
        lat=21.27,
        lng=106.20,
        radius_km=200,
        source_urls=["https://www.example.com/news/luxshare-fire"],
        severity=4,
        confidence=0.94,
        dedupe_keywords=["luxshare", "fire", "vietnam", "bac_giang", "connector"],
    ),
    disruption=ScenarioDisruption(
        title="Fire at Luxshare Vietnam facility halts connector production",
        summary=(
            "A fire at the Luxshare Precision Industry facility in Bắc Giang, Vietnam"
            " halted production of board-to-board connectors and assembly modules."
            " Expected downtime 2-3 weeks. Affected SKUs include PMIC and MCU"
            " sub-assemblies for Tier-1 customers."
        ),
        category="news",
        severity=4,
        region="Southeast Asia",
        lat=21.27,
        lng=106.20,
        radius_km=200,
        confidence=0.94,
    ),
    expected=ScenarioExpectation(
        affected_shipments_min=4,
        affected_shipments_max=8,
        exposure_usd_min=700_000,
        exposure_usd_max=1_100_000,
        dominant_mitigation="alternate_supplier",
        notes="Analyst should identify PMIC/MCU SKU shipments from Luxshare Vietnam supplier.",
    ),
)
