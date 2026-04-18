from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

SourceCategory = Literal["news", "weather", "policy", "logistics", "macro"]
DisruptionCategory = Literal["weather", "policy", "news", "logistics", "macro", "industrial"]


@dataclass(frozen=True)
class ScenarioSignal:
    source_category: SourceCategory
    source_name: str
    title: str
    summary: str
    region: str
    lat: float
    lng: float
    radius_km: float
    source_urls: list[str]
    severity: int
    confidence: float
    dedupe_keywords: list[str]


@dataclass(frozen=True)
class ScenarioDisruption:
    title: str
    summary: str
    category: DisruptionCategory
    severity: int
    region: str
    lat: float
    lng: float
    radius_km: float
    confidence: float
    status: Literal["active"] = "active"


@dataclass(frozen=True)
class ScenarioExpectation:
    affected_shipments_min: int
    affected_shipments_max: int
    exposure_usd_min: int
    exposure_usd_max: int
    dominant_mitigation: str
    notes: str = ""


@dataclass(frozen=True)
class Scenario:
    id: str
    signal: ScenarioSignal
    disruption: ScenarioDisruption
    expected: ScenarioExpectation
