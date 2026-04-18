from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

SourceCategory = Literal["news", "weather", "policy", "logistics", "macro"]


class SignalClassification(BaseModel):
    """Output of the Scout classifier — constrained via Gemini response_schema."""

    model_config = ConfigDict(extra="forbid")

    source_category: SourceCategory
    title: str = Field(min_length=3, max_length=200)
    summary: str = Field(min_length=10, max_length=1000)
    region: str | None = None
    lat: float | None = None
    lng: float | None = None
    radius_km: float | None = Field(default=None, ge=0, le=5000)
    severity: int = Field(ge=1, le=5)
    confidence: float = Field(ge=0, le=1)
    dedupe_keywords: list[str] = Field(max_length=10)


class SignalRecord(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid")

    id: uuid.UUID
    source_category: SourceCategory
    source_name: str
    title: str
    summary: str | None
    region: str | None
    lat: float | None
    lng: float | None
    radius_km: Decimal | None
    source_urls: list[str]
    confidence: Decimal
    first_seen_at: datetime
    promoted_to_disruption_id: uuid.UUID | None
