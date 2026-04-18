"""Strategist drafts processor — structured LLM call → ``DraftCommunicationBundle``.

Given a ``MitigationOption`` + its surrounding impact / customer context, the
Strategist must produce three pre-written messages (supplier, customer,
internal) that a human operator can one-click approve. The contracts:

- Use ``LLMClient.structured`` — no tool loop; drafts are text-generation,
  not DB retrieval. The caller pre-resolves supplier email + primary
  customer email from the impact report context and hands them in.
- The final object conforms to ``DraftCommunicationBundle`` (three keyed
  drafts).
- Post-parse validation enforces the forbidden-word list in the ``internal``
  draft body (per master plan 7.2 Step 2). Violations raise
  :class:`DraftQualityError` so the caller can log + skip that option
  rather than persist prose that breaks the ops-doc style guide.

No DB I/O; the caller owns persistence via the OpenClaw action layer.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Protocol, cast

import structlog
from pydantic import BaseModel

from backend.schemas.mitigation import (
    DraftCommunicationBundle,
    MitigationOption,
)

log = structlog.get_logger()

_PROMPT_DIR = Path(__file__).parent.parent / "prompts"
_DRAFTS_SYSTEM = _PROMPT_DIR / "drafts.md"

# Forbidden-word list for the ``internal`` draft (master plan 7.2).
_INTERNAL_FORBIDDEN = (
    "regrettably",
    "unfortunately",
    "apologies",
    "please accept",
)


class DraftQualityError(ValueError):
    """Raised when a draft violates the prompt-level style guide post-parse."""


class _LLM(Protocol):
    async def structured(
        self,
        prompt: str,
        schema: type[BaseModel],
        *,
        cache_key: str | None = ...,
    ) -> BaseModel: ...


# ---------------------------------------------------------------------------
# Prompt assembly
# ---------------------------------------------------------------------------


def _render_prompt(
    option: MitigationOption,
    *,
    supplier_contact: str,
    customer_contact: str,
    disruption_title: str,
    impact_exposure: str,
    affected_shipment_ids: list[str],
) -> str:
    system = _DRAFTS_SYSTEM.read_text()
    ctx = {
        "option": {
            "option_type": option.option_type,
            "description": option.description,
            "delta_cost": str(option.delta_cost),
            "delta_days": option.delta_days,
            "confidence": option.confidence,
            "rationale": option.rationale,
        },
        "context": {
            "disruption_title": disruption_title,
            "total_exposure": impact_exposure,
            "affected_shipment_count": len(affected_shipment_ids),
            "affected_shipment_ids_preview": affected_shipment_ids[:5],
            "supplier_contact": supplier_contact,
            "customer_contact": customer_contact,
            "internal_contact": "ops@suppl.ai",
        },
    }
    return (
        f"{system}\n\n"
        f"## Context\n```json\n{json.dumps(ctx, indent=2)}\n```\n\n"
        "Emit a single JSON object conforming to `DraftCommunicationBundle`."
    )


# ---------------------------------------------------------------------------
# Post-parse validation
# ---------------------------------------------------------------------------


def _validate_bundle(bundle: DraftCommunicationBundle) -> None:
    internal_body = bundle.internal.body.lower()
    for banned in _INTERNAL_FORBIDDEN:
        if banned in internal_body:
            raise DraftQualityError(f"internal draft contains forbidden phrase: {banned!r}")

    if bundle.supplier.recipient_type != "supplier":
        raise DraftQualityError("supplier draft has wrong recipient_type")
    if bundle.customer.recipient_type != "customer":
        raise DraftQualityError("customer draft has wrong recipient_type")
    if bundle.internal.recipient_type != "internal":
        raise DraftQualityError("internal draft has wrong recipient_type")


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


async def generate_drafts(
    option: MitigationOption,
    *,
    llm: _LLM,
    supplier_contact: str,
    customer_contact: str,
    disruption_title: str,
    impact_exposure: str,
    affected_shipment_ids: list[str],
) -> DraftCommunicationBundle:
    """Produce three drafts for a mitigation option.

    Raises :class:`DraftQualityError` on style-guide violations after parse.
    Raises :class:`backend.llm.client.LLMValidationError` if Gemini's output
    cannot be parsed into :class:`DraftCommunicationBundle` after one retry.
    """
    prompt = _render_prompt(
        option,
        supplier_contact=supplier_contact,
        customer_contact=customer_contact,
        disruption_title=disruption_title,
        impact_exposure=impact_exposure,
        affected_shipment_ids=affected_shipment_ids,
    )
    result = await llm.structured(
        prompt,
        DraftCommunicationBundle,
        cache_key=f"strategist.drafts::{option.option_type}::{hash(option.description)}",
    )
    bundle = cast(DraftCommunicationBundle, result)
    _validate_bundle(bundle)
    log.info(
        "strategist.drafts_generated",
        option_type=option.option_type,
        supplier_subject=bundle.supplier.subject,
    )
    return bundle


__all__ = [
    "DraftQualityError",
    "generate_drafts",
]
