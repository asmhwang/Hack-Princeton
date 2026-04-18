from __future__ import annotations

from backend.scripts.scenarios._types import (
    Scenario,
    ScenarioDisruption,
    ScenarioExpectation,
    ScenarioSignal,
)

CBAM_TARIFF = Scenario(
    id="cbam_tariff",
    signal=ScenarioSignal(
        source_category="policy",
        source_name="tavily:policy:ec_europa",
        title="EU CBAM tariff expansion targets steel and aluminum imports",
        summary=(
            "European Commission announced CBAM (Carbon Border Adjustment Mechanism)"
            " tariff expansion effective Q2. Non-compliant industrial suppliers face"
            " 12-18% tariff on steel, aluminum, and fasteners exported to EU. Affected"
            " SKUs include bearings and structural components."
        ),
        region="European Union",
        lat=50.85,
        lng=4.35,
        radius_km=2000,
        source_urls=["https://www.example.com/policy/cbam-expansion"],
        severity=3,
        confidence=0.90,
        dedupe_keywords=["cbam", "tariff", "eu", "steel", "aluminum"],
    ),
    disruption=ScenarioDisruption(
        title="EU CBAM tariff expansion targets steel and aluminum imports",
        summary=(
            "European Commission announced CBAM (Carbon Border Adjustment Mechanism)"
            " tariff expansion effective Q2. Non-compliant industrial suppliers face"
            " 12-18% tariff on steel, aluminum, and fasteners exported to EU. Affected"
            " SKUs include bearings and structural components."
        ),
        category="policy",
        severity=3,
        region="European Union",
        lat=50.85,
        lng=4.35,
        radius_km=2000,
        confidence=0.90,
    ),
    expected=ScenarioExpectation(
        affected_shipments_min=3,
        affected_shipments_max=7,
        exposure_usd_min=350_000,
        exposure_usd_max=700_000,
        dominant_mitigation="switch_compliant_supplier",
        notes="Analyst should identify industrial SKUs (bearings, structural) heading to EU ports.",
    ),
)
