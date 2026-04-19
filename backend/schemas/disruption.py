from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

DisruptionCategory = Literal["weather", "policy", "news", "logistics", "macro", "industrial"]
DisruptionStatus = Literal["active", "resolved"]


class DisruptionDraft(BaseModel):
    """LLM output when Scout fuses signals into a disruption."""

    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=3, max_length=200)
    summary: str | None = None
    category: DisruptionCategory
    severity: int = Field(ge=1, le=5)
    region: str | None = None
    lat: float | None = None
    lng: float | None = None
    radius_km: float | None = Field(default=None, ge=0, le=5000)
    confidence: float = Field(ge=0, le=1)
    source_signal_ids: list[uuid.UUID]


class DisruptionRecord(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid")

    id: uuid.UUID
    title: str
    summary: str | None
    category: DisruptionCategory
    severity: int
    region: str | None
    lat: float | None
    lng: float | None
    radius_km: Decimal | None
    source_signal_ids: list[uuid.UUID]
    confidence: Decimal
    first_seen_at: datetime
    last_seen_at: datetime
    status: DisruptionStatus
    # Populated by list_disruptions via a JOIN with impact_reports / affected_shipments.
    # Single-row endpoints leave these as None; the UI tolerates that.
    total_exposure: Decimal | None = None
    affected_shipments_count: int | None = None
