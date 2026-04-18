"""TDD for the Scout classifier wrapper.

The real LLM drifts; we cannot assert ``category == expected`` exactly. So
each fixture is paired with an accepted-category set and an integer target
severity, and the assertion is:

- ``classification.source_category in accepted_categories``
- ``|classification.severity - expected_severity| <= 1``

The LLM transport is monkeypatched with canned responses keyed off the
raw signal URL, so the wrapper itself (prompt loading, cache-key shape,
schema validation) is under test deterministically.

Replace the canned map with live Gemini calls by dropping the monkeypatch
— the tolerance bounds are intentionally generous for that case.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from pydantic import BaseModel

from backend.agents.scout.processors.classify import classify_raw_signal
from backend.llm.client import LLMClient
from backend.schemas import SignalClassification

_FIXTURES = Path(__file__).parent.parent / "fixtures" / "raw"


# (accepted_categories, expected_severity, canned_output)
_FIXTURE_EXPECTATIONS: dict[str, tuple[set[str], int, dict[str, Any]]] = {
    "01_typhoon_taiwan.json": (
        {"weather"},
        4,
        {
            "source_category": "weather",
            "title": "Super Typhoon Haikui approaches southern Taiwan",
            "summary": "Taiwan's CWA issued a sea warning for Haikui as the storm strengthens toward Category 4. Kaohsiung and Keelung ports warn of 48-hour berth closures.",  # noqa: E501
            "region": "Taiwan Strait",
            "lat": 22.6,
            "lng": 120.3,
            "radius_km": 400.0,
            "severity": 4,
            "confidence": 0.85,
            "dedupe_keywords": ["typhoon", "haikui", "taiwan", "kaohsiung"],
        },
    ),
    "02_ustr_tariff.json": (
        {"policy"},
        3,
        {
            "source_category": "policy",
            "title": "USTR finalizes Section 301 tariff increase on EV battery components",
            "summary": "USTR finalized a 25% Section 301 duty escalation on lithium-ion cells and graphite anodes from China, effective in 45 days.",  # noqa: E501
            "region": "United States",
            "lat": 38.9,
            "lng": -77.0,
            "radius_km": None,
            "severity": 3,
            "confidence": 0.9,
            "dedupe_keywords": ["ustr", "section301", "tariff", "ev", "battery"],
        },
    ),
    "03_ilwu_strike.json": (
        {"news", "logistics"},
        4,
        {
            "source_category": "news",
            "title": "ILWU authorizes strike at U.S. West Coast ports",
            "summary": "ILWU voted 94% in favor of authorizing a labor action at 29 U.S. West Coast ports. A walkout would disrupt 40% of containerized imports.",  # noqa: E501
            "region": "US West Coast",
            "lat": 34.1,
            "lng": -118.3,
            "radius_km": 600.0,
            "severity": 4,
            "confidence": 0.8,
            "dedupe_keywords": ["ilwu", "strike", "west-coast", "ports"],
        },
    ),
    "04_suez_restriction.json": (
        {"logistics"},
        4,
        {
            "source_category": "logistics",
            "title": "Suez Canal reduces max draft to 14.3 m",
            "summary": "The Suez Canal Authority cut maximum draft to 14.3 m after a silting survey, forcing deep-draft tankers and ULCVs to lighten or reroute.",  # noqa: E501
            "region": "Suez Canal",
            "lat": 30.5,
            "lng": 32.3,
            "radius_km": 200.0,
            "severity": 4,
            "confidence": 0.85,
            "dedupe_keywords": ["suez", "canal", "draft", "silting"],
        },
    ),
    "05_fed_rate_hike.json": (
        {"macro"},
        2,
        {
            "source_category": "macro",
            "title": "Fed raises policy rate 25 bps to 5.75-6.00%",
            "summary": "The FOMC raised the target range for the federal funds rate to 5.75-6.00% and signaled one more hike may be needed. Import financing costs steepen.",  # noqa: E501
            "region": "United States",
            "lat": 38.9,
            "lng": -77.0,
            "radius_km": None,
            "severity": 2,
            "confidence": 0.8,
            "dedupe_keywords": ["fomc", "rate-hike", "fed-funds"],
        },
    ),
    "06_shenzhen_heatwave.json": (
        {"weather", "macro"},
        3,
        {
            "source_category": "weather",
            "title": "Record heatwave triggers Shenzhen power curtailments",
            "summary": "Shenzhen crossed 40°C for multiple days. Rolling power cuts forced Bao'an industrial park electronics factories to reduce output by 30%.",  # noqa: E501
            "region": "Shenzhen",
            "lat": 22.5,
            "lng": 114.1,
            "radius_km": 150.0,
            "severity": 3,
            "confidence": 0.75,
            "dedupe_keywords": ["heatwave", "shenzhen", "power-curtailment"],
        },
    ),
    "07_rotterdam_congestion.json": (
        {"logistics"},
        3,
        {
            "source_category": "logistics",
            "title": "Rotterdam berthing delays reach 4.5 days after crane failure",
            "summary": "Three gantry cranes out at APM Maasvlakte II pushed berthing delays to 4.5 days. Carriers weigh omitting Rotterdam calls on Asia-Europe.",  # noqa: E501
            "region": "Rotterdam",
            "lat": 51.9,
            "lng": 4.5,
            "radius_km": 80.0,
            "severity": 3,
            "confidence": 0.82,
            "dedupe_keywords": ["rotterdam", "congestion", "crane-failure"],
        },
    ),
    "08_eu_cbam_phase.json": (
        {"policy"},
        3,
        {
            "source_category": "policy",
            "title": "EU publishes Phase 2 CBAM charges",
            "summary": "Phase 2 CBAM charges cover steel, aluminum, cement, and fertilizer imports from 2026-07-01, priced against the weekly EU ETS auction.",  # noqa: E501
            "region": "European Union",
            "lat": 50.8,
            "lng": 4.3,
            "radius_km": None,
            "severity": 3,
            "confidence": 0.88,
            "dedupe_keywords": ["eu", "cbam", "phase2", "steel", "aluminum"],
        },
    ),
    "09_mexico_warehouse_fire.json": (
        {"news"},
        3,
        {
            "source_category": "news",
            "title": "Fire destroys Monterrey auto-parts warehouse",
            "summary": "A seven-alarm fire destroyed a 40,000 m² auto-parts warehouse in Apodaca. Tier-2 suppliers to U.S. OEMs warn of harness and stamping allocations.",  # noqa: E501
            "region": "Monterrey",
            "lat": 25.67,
            "lng": -100.3,
            "radius_km": 20.0,
            "severity": 3,
            "confidence": 0.78,
            "dedupe_keywords": ["monterrey", "fire", "auto-parts", "apodaca"],
        },
    ),
    "10_panama_drought.json": (
        {"logistics", "weather"},
        4,
        {
            "source_category": "logistics",
            "title": "Panama Canal cuts daily transits to 22 amid Gatun Lake low",
            "summary": "The Panama Canal Authority cut permitted daily transits to 22 from 28. Neopanamax vessels face 13.4 m draft limits during the El Niño dry cycle.",  # noqa: E501
            "region": "Panama Canal",
            "lat": 9.08,
            "lng": -79.68,
            "radius_km": 100.0,
            "severity": 4,
            "confidence": 0.87,
            "dedupe_keywords": ["panama", "canal", "drought", "gatun"],
        },
    ),
}


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> LLMClient:
    c = LLMClient(cache_path=tmp_path / "cache.sqlite", model="flash")

    async def fake_raw(*, prompt: str, schema: type[BaseModel]) -> str:
        # The canned map is keyed by URL — the prompt always ends with the
        # serialized raw signal, so we can extract the URL from the prompt.
        for name, (_, _, canned) in _FIXTURE_EXPECTATIONS.items():
            raw = json.loads((_FIXTURES / name).read_text())
            if raw["url"] in prompt:
                return json.dumps(canned)
        raise AssertionError(f"no canned response matched prompt; schema={schema.__name__}")

    monkeypatch.setattr(c, "_raw_structured", fake_raw)
    return c


@pytest.mark.asyncio
@pytest.mark.parametrize("fixture_name", sorted(_FIXTURE_EXPECTATIONS))
async def test_classify_fixture(fixture_name: str, client: LLMClient) -> None:
    raw = json.loads((_FIXTURES / fixture_name).read_text())
    accepted, expected_sev, _ = _FIXTURE_EXPECTATIONS[fixture_name]

    result = await classify_raw_signal(raw, client)

    assert isinstance(result, SignalClassification)
    assert result.source_category in accepted, (
        f"{fixture_name}: got {result.source_category}, want one of {accepted}"
    )
    assert abs(result.severity - expected_sev) <= 1, (
        f"{fixture_name}: severity {result.severity} outside ±1 of {expected_sev}"
    )
    # Dedupe keywords must be populated — downstream hashing relies on them.
    assert result.dedupe_keywords, f"{fixture_name}: empty dedupe_keywords"


@pytest.mark.asyncio
async def test_classify_uses_url_as_cache_key(
    client: LLMClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Re-running against the same raw signal must hit the on-disk cache."""
    raw = json.loads((_FIXTURES / "01_typhoon_taiwan.json").read_text())
    await classify_raw_signal(raw, client)

    async def boom(**_: Any) -> str:
        raise AssertionError("second call must be served from cache")

    monkeypatch.setattr(client, "_raw_structured", boom)
    await classify_raw_signal(raw, client)
