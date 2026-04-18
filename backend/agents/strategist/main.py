"""Strategist agent entrypoint.

Subscribes to ``new_impact``. For each notify payload (a JSON object whose
``id`` key carries the impact-report UUID), the agent:

1. Runs the Gemini function-calling loop via
   :func:`backend.agents.strategist.processors.options.generate_options`.
2. For each mitigation option, runs
   :func:`backend.agents.strategist.processors.drafts.generate_drafts` with
   the resolved supplier + customer contacts from the impact context.
3. Persists everything via the OpenClaw action layer (``SaveMitigationOptions``
   → ``SaveDraftCommunications``), all in one session transaction.
4. After commit, emits ``NOTIFY new_mitigation`` with the list of written
   mitigation ids so the Plan B UI can hydrate the mitigation rail.

Run as::

    uv run python -m backend.agents.strategist.main

Also importable as :class:`StrategistAgent` for integration tests, which
drive the lifecycle manually (``await agent.start() / agent.stop()``).
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import signal
import uuid
from pathlib import Path

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.agents.base import AgentBase
from backend.agents.strategist.actions.openclaw_actions import (
    SaveDraftCommunications,
    SaveDraftCommunicationsArgs,
    SaveMitigationOptions,
    SaveMitigationOptionsArgs,
)
from backend.agents.strategist.config import StrategistSettings
from backend.agents.strategist.processors.drafts import (
    DraftQualityError,
    generate_drafts,
)
from backend.agents.strategist.processors.options import (
    ImpactReportNotFoundError,
    generate_options,
)
from backend.agents.strategist.state import record_processed
from backend.db.bus import EventBus
from backend.db.models import (
    AffectedShipment,
    Customer,
    Disruption,
    PurchaseOrder,
    Shipment,
    Supplier,
)
from backend.db.models import (
    ImpactReport as ImpactReportRow,
)
from backend.db.session import session as default_session
from backend.llm.client import LLMClient, LLMValidationError
from backend.schemas.mitigation import MitigationOption

log = structlog.get_logger()

_FALLBACK_SUPPLIER_CONTACT = "supplier@unknown.example"
_FALLBACK_CUSTOMER_CONTACT = "customer@unknown.example"


class StrategistAgent(AgentBase):
    name = "strategist"
    channels = ["new_impact"]

    def __init__(
        self,
        *,
        settings: StrategistSettings | None = None,
        llm: LLMClient | None = None,
    ) -> None:
        self.settings = settings or StrategistSettings()
        super().__init__(dsn=self.settings.database_url)
        self.state_path = Path(self.settings.state_path)
        self.health_port = self.settings.health_port
        self._llm = llm or LLMClient(
            cache_path=self.settings.llm_cache_path,
            model=self.settings.model,
        )

    # ------------------------------------------------------------------ handler

    async def on_notify(self, channel: str, payload: str) -> None:
        impact_id = _parse_impact_id(payload)
        if impact_id is None:
            log.warning("strategist.invalid_payload", channel=channel, payload=payload[:200])
            return

        try:
            bundle, _trace = await generate_options(
                impact_report_id=impact_id,
                llm=self._llm,
            )
        except ImpactReportNotFoundError:
            log.warning("strategist.impact_missing", impact_id=str(impact_id))
            return
        except LLMValidationError as err:
            log.warning("strategist.options_llm_failed", impact_id=str(impact_id), error=str(err))
            return

        context = await _load_mitigation_context(impact_id)

        draft_failures = 0
        mitigation_ids: list[uuid.UUID] = []

        async with default_session() as s:
            save_ids = await SaveMitigationOptions().execute(
                s,
                SaveMitigationOptionsArgs(
                    impact_report_id=impact_id,
                    options=bundle.options,
                ),
            )
            mitigation_ids.extend(save_ids)

            for mitigation_id, opt in zip(save_ids, bundle.options, strict=True):
                try:
                    drafts_bundle = await generate_drafts(
                        opt,
                        llm=self._llm,
                        supplier_contact=context.supplier_contact,
                        customer_contact=context.customer_contact,
                        disruption_title=context.disruption_title,
                        impact_exposure=context.total_exposure,
                        affected_shipment_ids=context.shipment_ids,
                    )
                except (LLMValidationError, DraftQualityError) as err:
                    draft_failures += 1
                    log.warning(
                        "strategist.drafts_skipped",
                        impact_id=str(impact_id),
                        mitigation_id=str(mitigation_id),
                        option_type=opt.option_type,
                        error=str(err),
                    )
                    continue

                await SaveDraftCommunications().execute(
                    s,
                    SaveDraftCommunicationsArgs(
                        mitigation_id=mitigation_id,
                        bundle=drafts_bundle,
                    ),
                )
            await s.commit()

        await record_processed(self, impact_id, draft_failures=draft_failures)

        notify_payload = json.dumps(
            {
                "impact_report_id": str(impact_id),
                "mitigation_ids": [str(mid) for mid in mitigation_ids],
            }
        )
        await self._bus.publish("new_mitigation", notify_payload)
        log.info(
            "strategist.impact_processed",
            impact_id=str(impact_id),
            mitigation_count=len(mitigation_ids),
            draft_failures=draft_failures,
        )

    # ------------------------------------------------------------------ test hooks

    @property
    def bus(self) -> EventBus:
        return self._bus


# ---------------------------------------------------------------------------
# Payload parsing
# ---------------------------------------------------------------------------


def _parse_impact_id(payload: str) -> uuid.UUID | None:
    """Accept either a bare UUID string or a JSON object with an ``id`` key.

    The Analyst publishes a JSON object today (per coordination doc §2);
    bare UUIDs are tolerated so the contract can evolve without lock-step.
    """
    candidate = payload.strip()
    if not candidate:
        return None
    try:
        return uuid.UUID(candidate)
    except ValueError:
        pass
    try:
        parsed = json.loads(candidate)
    except (ValueError, TypeError):
        return None
    if isinstance(parsed, dict):
        for key in ("id", "impact_report_id"):
            val = parsed.get(key)
            if isinstance(val, str):
                try:
                    return uuid.UUID(val)
                except ValueError:
                    continue
    return None


# ---------------------------------------------------------------------------
# Context resolution for drafts
# ---------------------------------------------------------------------------


class _DraftContext:
    """Per-impact snapshot the drafts processor needs.

    Resolved once at the top of the handler so the drafts loop doesn't
    re-query. Defaults to unknown-example contacts when the impact has
    no linked supplier or customer.
    """

    __slots__ = (
        "supplier_contact",
        "customer_contact",
        "disruption_title",
        "total_exposure",
        "shipment_ids",
    )

    def __init__(
        self,
        *,
        supplier_contact: str,
        customer_contact: str,
        disruption_title: str,
        total_exposure: str,
        shipment_ids: list[str],
    ) -> None:
        self.supplier_contact = supplier_contact
        self.customer_contact = customer_contact
        self.disruption_title = disruption_title
        self.total_exposure = total_exposure
        self.shipment_ids = shipment_ids


async def _load_mitigation_context(impact_id: uuid.UUID) -> _DraftContext:
    """Resolve supplier + primary customer email for the drafts prompt."""
    async with default_session() as s:
        ir = (
            await s.execute(select(ImpactReportRow).where(ImpactReportRow.id == impact_id))
        ).scalar_one()
        disruption = (
            await s.execute(select(Disruption).where(Disruption.id == ir.disruption_id))
        ).scalar_one()

        affected_rows = (
            (
                await s.execute(
                    select(AffectedShipment).where(AffectedShipment.impact_report_id == ir.id)
                )
            )
            .scalars()
            .all()
        )
        shipment_ids = [row.shipment_id for row in affected_rows]

        supplier_contact = _FALLBACK_SUPPLIER_CONTACT
        customer_contact = _FALLBACK_CUSTOMER_CONTACT
        if shipment_ids:
            supplier_contact = await _first_supplier_email(s, shipment_ids) or supplier_contact
            customer_contact = await _first_customer_email(s, shipment_ids) or customer_contact

    return _DraftContext(
        supplier_contact=supplier_contact,
        customer_contact=customer_contact,
        disruption_title=disruption.title or "Supply chain disruption",
        total_exposure=str(ir.total_exposure),
        shipment_ids=shipment_ids,
    )


async def _first_supplier_email(s: AsyncSession, shipment_ids: list[str]) -> str | None:
    """``suppliers`` has no ``contact_email`` column; synthesize one from supplier id."""
    row = (
        await s.execute(
            select(Supplier.id, Supplier.name)
            .join(Shipment, Shipment.supplier_id == Supplier.id)
            .where(Shipment.id.in_(shipment_ids))
            .limit(1)
        )
    ).first()
    if row is None:
        return None
    # Deterministic synthetic contact — real contact resolution is Eragon follow-up.
    slug = str(row.id).lower().replace("_", "-")
    return f"ops@{slug}.example"


async def _first_customer_email(s: AsyncSession, shipment_ids: list[str]) -> str | None:
    row = (
        await s.execute(
            select(Customer.contact_email)
            .join(PurchaseOrder, PurchaseOrder.customer_id == Customer.id)
            .join(Shipment, Shipment.po_id == PurchaseOrder.id)
            .where(Shipment.id.in_(shipment_ids))
            .where(Customer.contact_email.is_not(None))
            .limit(1)
        )
    ).first()
    if row is None:
        return None
    return str(row[0]) if row[0] else None


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------


async def _run() -> None:
    agent = StrategistAgent()
    await agent.start()
    stop = asyncio.Event()

    def _set_stop() -> None:
        stop.set()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        with contextlib.suppress(NotImplementedError):
            loop.add_signal_handler(sig, _set_stop)

    try:
        await stop.wait()
    finally:
        await agent.stop()


def main() -> None:
    asyncio.run(_run())


# Keep unused imports honest — MitigationOption used only for typing.
_ = MitigationOption


if __name__ == "__main__":
    main()
