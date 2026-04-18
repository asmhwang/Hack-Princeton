"""Pure-function cost / delay math for Strategist mitigation options.

The Strategist tool loop may surface alternate ports, alternate suppliers, or
expedite-mode candidates. This module turns those DB-row inputs into the
concrete ``delta_cost`` / ``delta_days`` numbers the Gemini prompt cites —
and that the ``MitigationOption`` Pydantic schema requires.

All helpers are **pure**: no DB, no I/O, no randomness. They exist as a
separate module so unit tests can exercise each branch in microseconds and
so the LLM path can call them deterministically before emitting the final
bundle.

Models:

- **Reroute**: cost premium proportional to the extra sea-km incurred when
  shifting origin or destination to an alternate port; days premium scales
  with distance at a typical container-ship speed.
- **Supplier swap**: cost premium is a reliability-gap risk reserve (lower
  reliability → higher reserve), capped at 20% of PO revenue. Days premium
  flat — onboarding a second-source takes ~7 days.
- **Expedite**: cost premium is air-vs-sea freight differential. Days delta
  negative (shortens transit).
- **Accept delay**: cost is the SLA-breach penalty sum; days delta is
  caller-supplied (typically positive).
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

# Tunables — calibrated for the demo scenario magnitudes; exposed as
# module constants so tests can assert the exact arithmetic path.
REROUTE_USD_PER_KM = Decimal("3.50")
REROUTE_KM_PER_DAY = Decimal("650")  # ~14kt × 24h
SUPPLIER_SWAP_MAX_RESERVE_PCT = Decimal("0.20")
SUPPLIER_ONBOARD_DAYS = 7
EXPEDITE_USD_MULTIPLIER = Decimal("4.0")  # air ≈ 4× sea on this lane
EXPEDITE_DAYS_DELTA = -5
_TWO = Decimal("0.01")


def _q(value: Decimal) -> Decimal:
    return value.quantize(_TWO, rounding=ROUND_HALF_UP)


def reroute_cost(shipment_count: int, extra_km: float) -> Decimal:
    """Total freight premium for shifting ``shipment_count`` shipments by ``extra_km``."""
    if shipment_count <= 0 or extra_km <= 0:
        return Decimal("0.00")
    return _q(Decimal(shipment_count) * Decimal(str(extra_km)) * REROUTE_USD_PER_KM)


def reroute_days(extra_km: float) -> int:
    """Transit-days premium for the extra distance. Always non-negative, rounded up."""
    if extra_km <= 0:
        return 0
    days = Decimal(str(extra_km)) / REROUTE_KM_PER_DAY
    # ceil via (x + 1 - epsilon) // 1; use quantize then int()
    ceil = int(days.to_integral_value(rounding="ROUND_CEILING"))
    return max(ceil, 1)


def supplier_swap_cost(
    po_revenue: Decimal,
    *,
    current_reliability: float,
    alternate_reliability: float,
) -> Decimal:
    """Reliability-gap risk reserve, capped at ``SUPPLIER_SWAP_MAX_RESERVE_PCT`` × revenue."""
    gap = max(current_reliability - alternate_reliability, 0.0)
    reserve_pct = min(Decimal(str(gap)), SUPPLIER_SWAP_MAX_RESERVE_PCT)
    if reserve_pct <= 0:
        return Decimal("0.00")
    return _q(po_revenue * reserve_pct)


def supplier_swap_days() -> int:
    """Second-source onboarding is flat ``SUPPLIER_ONBOARD_DAYS`` days."""
    return SUPPLIER_ONBOARD_DAYS


def expedite_cost(baseline_shipment_value: Decimal) -> Decimal:
    """Freight-mode upgrade (sea → air) premium."""
    if baseline_shipment_value <= 0:
        return Decimal("0.00")
    return _q(baseline_shipment_value * (EXPEDITE_USD_MULTIPLIER - Decimal("1")))


def expedite_days() -> int:
    """Days delta is negative — expedite shortens transit."""
    return EXPEDITE_DAYS_DELTA


def accept_delay_cost(sla_penalties: list[Decimal]) -> Decimal:
    """Sum of SLA-breach penalties across affected POs."""
    total = sum(sla_penalties, Decimal("0"))
    return _q(total) if total > 0 else Decimal("0.00")
