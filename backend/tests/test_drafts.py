"""TDD for the Strategist drafts processor.

Per master plan §7.2:

- ``generate_drafts`` produces supplier / customer / internal drafts in one
  ``LLMClient.structured`` call.
- Post-parse validation rejects forbidden words ("regrettably",
  "unfortunately", etc.) in the ``internal`` body.
- Subject / body length bounds come from the Pydantic schema; ``structured``
  has already validated those by the time we see the bundle.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from pydantic import BaseModel

from backend.schemas.mitigation import (
    DraftCommunication,
    DraftCommunicationBundle,
    MitigationOption,
)


def _sample_option() -> MitigationOption:
    return MitigationOption(
        option_type="reroute",
        description="Shift 13 shipments from PORT-SZX to PORT-NGB to skirt Typhoon Haikui.",
        delta_cost=Decimal("42000.00"),
        delta_days=2,
        confidence=0.78,
        rationale=(
            "Typhoon berth closure at SZX closes 48h; PORT-NGB berth capacity confirmed via "
            "alternate_ports_near; 13 in_transit shipments re-lane feasibly."
        ),
    )


def _good_bundle() -> DraftCommunicationBundle:
    return DraftCommunicationBundle(
        supplier=DraftCommunication(
            recipient_type="supplier",
            recipient_contact="ops@supplier.example",
            subject="Action required: alternate routing via PORT-NGB",
            body=(
                "Please confirm receiving capacity at PORT-NGB for 13 containers; "
                "requested window: 2026-04-22 to 2026-04-25. Acknowledge within 24h."
            ),
        ),
        customer=DraftCommunication(
            recipient_type="customer",
            recipient_contact="ops@customer.example",
            subject="Shipment update: revised ETA due to weather",
            body=(
                "We are rerouting your shipment to maintain delivery integrity. "
                "The revised ETA is 2026-04-28 — a 2-day delay we are working to compress."
            ),
        ),
        internal=DraftCommunication(
            recipient_type="internal",
            recipient_contact="ops@suppl.ai",
            subject="Mitigation pending: reroute SZX→NGB, +$42k, +2d",
            body=(
                "- Option: reroute\n"
                "- Delta cost: $42,000\n"
                "- Delta days: +2\n"
                "- Owner: duty Strategist\n"
                "- Action: approve via War Room"
            ),
        ),
    )


def _bad_bundle_internal_forbidden() -> DraftCommunicationBundle:
    return DraftCommunicationBundle(
        supplier=DraftCommunication(
            recipient_type="supplier",
            recipient_contact="ops@supplier.example",
            subject="Alternate routing needed",
            body="Please confirm capacity for rerouted shipments by EOD.",
        ),
        customer=DraftCommunication(
            recipient_type="customer",
            recipient_contact="ops@customer.example",
            subject="Shipment delay notice",
            body="We are adjusting the route to preserve delivery integrity.",
        ),
        internal=DraftCommunication(
            recipient_type="internal",
            recipient_contact="ops@suppl.ai",
            subject="Mitigation pending",
            body=(
                "Regrettably, we are seeing a disruption. Please accept the "
                "reroute recommendation and approve via War Room."
            ),
        ),
    )


class _StubLLM:
    def __init__(self, bundle: DraftCommunicationBundle) -> None:
        self._bundle = bundle
        self.last_prompt: str | None = None

    async def structured(
        self,
        prompt: str,
        schema: type[BaseModel],
        *,
        cache_key: str | None = None,
    ) -> BaseModel:
        self.last_prompt = prompt
        assert schema is DraftCommunicationBundle
        return self._bundle


@pytest.mark.asyncio
async def test_generate_drafts_returns_three_drafts() -> None:
    from backend.agents.strategist.processors.drafts import generate_drafts

    llm = _StubLLM(_good_bundle())
    bundle = await generate_drafts(
        _sample_option(),
        llm=llm,
        supplier_contact="ops@supplier.example",
        customer_contact="ops@customer.example",
        disruption_title="Super Typhoon Haikui",
        impact_exposure="2300000.00",
        affected_shipment_ids=[f"SHP-T{i:03d}" for i in range(1, 14)],
    )

    assert bundle.supplier.recipient_type == "supplier"
    assert bundle.customer.recipient_type == "customer"
    assert bundle.internal.recipient_type == "internal"

    # internal is terse → uses bullet points + $ figures.
    assert "$42,000" in bundle.internal.body or "42,000" in bundle.internal.body
    # customer is empathetic with an explicit new ETA.
    assert "ETA" in bundle.customer.body

    # Prompt carried context.
    assert llm.last_prompt is not None
    assert "Typhoon Haikui" in llm.last_prompt
    assert "ops@supplier.example" in llm.last_prompt


@pytest.mark.asyncio
async def test_generate_drafts_rejects_forbidden_internal_words() -> None:
    from backend.agents.strategist.processors.drafts import (
        DraftQualityError,
        generate_drafts,
    )

    llm = _StubLLM(_bad_bundle_internal_forbidden())
    with pytest.raises(DraftQualityError):
        await generate_drafts(
            _sample_option(),
            llm=llm,
            supplier_contact="ops@supplier.example",
            customer_contact="ops@customer.example",
            disruption_title="Super Typhoon Haikui",
            impact_exposure="2300000.00",
            affected_shipment_ids=["SHP-T001"],
        )
