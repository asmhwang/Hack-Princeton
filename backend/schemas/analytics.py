from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class ExposureBucket(BaseModel):
    """One aggregated bucket for the exposure analytics endpoint.

    Fields:
        label   — human-readable dimension value (quarter string like "2026-Q2",
                  customer name, or SKU id)
        exposure — total dollar exposure across affected shipments in this bucket
        units   — total units_at_risk across impact reports in this bucket
        pos     — distinct purchase order count linked to affected shipments in
                  this bucket (proxy for order-level risk breadth)
    """

    model_config = ConfigDict(extra="forbid")

    label: str
    exposure: Decimal
    units: int
    pos: int


class ExposureSummary(BaseModel):
    """Top-of-page exposure stat used by the War Room status grid."""

    model_config = ConfigDict(extra="forbid")

    active_count: int
    total_exposure: Decimal


class AnalyticsPoint(BaseModel):
    """One row in an analytics breakdown (smaller shape than ExposureBucket).

    ``at_risk`` + ``mitigated`` split ``exposure`` by disruption status so the
    chart can stack the two. Approving a mitigation flips its disruption to
    ``resolved`` and moves its contribution from at_risk → mitigated.
    """

    model_config = ConfigDict(extra="forbid")

    label: str
    exposure: Decimal
    at_risk: Decimal
    mitigated: Decimal
    count: int


class AnalyticsSummary(BaseModel):
    """Triple-grouping analytics used by the Analytics screen."""

    model_config = ConfigDict(extra="forbid")

    by_customer: list[AnalyticsPoint]
    by_sku: list[AnalyticsPoint]
    by_quarter: list[AnalyticsPoint]
