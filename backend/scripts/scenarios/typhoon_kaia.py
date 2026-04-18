from __future__ import annotations

from backend.scripts.scenarios._types import (
    Scenario,
    ScenarioDisruption,
    ScenarioExpectation,
    ScenarioSignal,
)

TYPHOON_KAIA = Scenario(
    id="typhoon_kaia",
    signal=ScenarioSignal(
        source_category="weather",
        source_name="tavily:news:scmp",
        title="Typhoon Kaia makes landfall near Shenzhen",
        summary=(
            "Category 3 typhoon Kaia made landfall near Shenzhen with sustained winds of"
            " 185 km/h. Yantian and Shekou terminals halting operations for 36-48 hours."
            " Shipping advisories issued for South China Sea and Hong Kong-Pearl River"
            " Delta corridor."
        ),
        region="South China Sea",
        lat=22.54,
        lng=114.06,
        radius_km=500,
        source_urls=["https://www.example.com/news/typhoon-kaia-shenzhen"],
        severity=4,
        confidence=0.92,
        dedupe_keywords=["typhoon", "kaia", "shenzhen", "yantian"],
    ),
    disruption=ScenarioDisruption(
        title="Typhoon Kaia — Shenzhen landfall",
        summary=(
            "Category 3 typhoon Kaia made landfall near Shenzhen with sustained winds of"
            " 185 km/h. Yantian and Shekou terminals halting operations for 36-48 hours."
            " Shipping advisories issued for South China Sea and Hong Kong-Pearl River"
            " Delta corridor."
        ),
        category="weather",
        severity=4,
        region="South China Sea",
        lat=22.54,
        lng=114.06,
        radius_km=500,
        confidence=0.92,
    ),
    expected=ScenarioExpectation(
        affected_shipments_min=12,
        affected_shipments_max=16,
        exposure_usd_min=1_800_000,
        exposure_usd_max=2_800_000,
        dominant_mitigation="reroute",
        notes=(
            "Analyst should use shipments_touching_region with center (22.54, 114.06)"
            " and radius 500km."
        ),
    ),
)
