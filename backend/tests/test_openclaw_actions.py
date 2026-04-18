"""Integration tests for the Strategist OpenClaw action layer.

Per master plan §7.3 Step 3: each action writes rows + an ``agent_log`` entry
with ``event_type='openclaw.<ActionName>'`` — that judge-visible audit
pattern is the whole point.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.models import (
    AgentLog,
    Approval,
    Shipment,
)
from backend.db.models import (
    DraftCommunication as DraftCommunicationRow,
)
from backend.db.models import (
    ImpactReport as ImpactReportRow,
)
from backend.db.models import (
    MitigationOption as MitigationOptionRow,
)
from backend.db.session import session
from backend.schemas.mitigation import (
    DraftCommunication,
    DraftCommunicationBundle,
    MitigationOption,
)
from backend.tests.fixtures.typhoon import TyphoonSeed, seed_typhoon


@pytest.fixture()
async def impact_session() -> AsyncIterator[tuple[AsyncSession, TyphoonSeed, uuid.UUID]]:
    """Yield (session, seed, impact_report_id) on the typhoon fixture."""
    async with session() as s:
        seed = await seed_typhoon(s)
        impact_id = uuid.uuid4()
        s.add(
            ImpactReportRow(
                id=impact_id,
                disruption_id=seed.disruption_id,
                total_exposure=Decimal("2300000"),
                units_at_risk=13000,
                cascade_depth=3,
                sql_executed="SELECT 1",
                reasoning_trace={"tool_calls": [], "final_reasoning": "fx"},
            )
        )
        await s.commit()
        yield s, seed, impact_id


def _mk_option(idx: int, kind: str) -> MitigationOption:
    return MitigationOption(
        option_type=kind,  # type: ignore[arg-type]
        description=f"Option {idx}: {kind} candidate with concrete plan.",
        delta_cost=Decimal("10000.00") * idx,
        delta_days=idx,
        confidence=0.7,
        rationale=(
            f"Rationale {idx} cites tool calls and concrete rows to justify the option."
        ),
    )


def _mk_drafts() -> DraftCommunicationBundle:
    return DraftCommunicationBundle(
        supplier=DraftCommunication(
            recipient_type="supplier",
            recipient_contact="ops@sup.example",
            subject="Action needed: alternate lane",
            body="Please confirm capacity and ack within 24h.",
        ),
        customer=DraftCommunication(
            recipient_type="customer",
            recipient_contact="ops@cust.example",
            subject="Shipment update: new ETA",
            body="We are adjusting the route; new ETA is 2026-04-28.",
        ),
        internal=DraftCommunication(
            recipient_type="internal",
            recipient_contact="ops@suppl.ai",
            subject="Mitigation pending",
            body="- Option: reroute\n- Cost: $42k\n- Owner: duty Strategist",
        ),
    )


# ---------------------------------------------------------------------------
# SaveMitigationOptions
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_save_mitigation_options_writes_rows_and_log(
    impact_session: tuple[AsyncSession, TyphoonSeed, uuid.UUID],
) -> None:
    from backend.agents.strategist.actions.openclaw_actions import (
        SaveMitigationOptions,
        SaveMitigationOptionsArgs,
    )

    _, _, impact_id = impact_session
    action = SaveMitigationOptions()
    options = [_mk_option(1, "reroute"), _mk_option(2, "alternate_supplier")]

    async with session() as s:
        ids = await action.execute(
            s,
            SaveMitigationOptionsArgs(impact_report_id=impact_id, options=options),
        )
        await s.commit()

    assert len(ids) == 2

    async with session() as s:
        rows = (
            (
                await s.execute(
                    select(MitigationOptionRow).where(
                        MitigationOptionRow.impact_report_id == impact_id
                    )
                )
            )
            .scalars()
            .all()
        )
        assert len(rows) == 2
        row_types = {r.option_type for r in rows}
        assert row_types == {"reroute", "alternate_supplier"}
        for row in rows:
            assert row.status == "pending"

        # agent_log entry with event_type='openclaw.SaveMitigationOptions'.
        log_rows = (
            (
                await s.execute(
                    select(AgentLog).where(
                        AgentLog.event_type == "openclaw.SaveMitigationOptions"
                    )
                )
            )
            .scalars()
            .all()
        )
        assert len(log_rows) == 1
        log_row = log_rows[0]
        assert log_row.agent_name == "strategist"
        assert "args" in log_row.payload
        assert "result" in log_row.payload


@pytest.mark.asyncio
async def test_save_draft_communications_writes_three_rows_and_log(
    impact_session: tuple[AsyncSession, TyphoonSeed, uuid.UUID],
) -> None:
    from backend.agents.strategist.actions.openclaw_actions import (
        SaveDraftCommunications,
        SaveDraftCommunicationsArgs,
        SaveMitigationOptions,
        SaveMitigationOptionsArgs,
    )

    _, _, impact_id = impact_session

    async with session() as s:
        option_ids = await SaveMitigationOptions().execute(
            s,
            SaveMitigationOptionsArgs(
                impact_report_id=impact_id,
                options=[_mk_option(1, "reroute")],
            ),
        )
        mitigation_id = option_ids[0]
        draft_ids = await SaveDraftCommunications().execute(
            s,
            SaveDraftCommunicationsArgs(
                mitigation_id=mitigation_id,
                bundle=_mk_drafts(),
            ),
        )
        await s.commit()

    assert len(draft_ids) == 3

    async with session() as s:
        rows = (
            (
                await s.execute(
                    select(DraftCommunicationRow).where(
                        DraftCommunicationRow.mitigation_id == mitigation_id
                    )
                )
            )
            .scalars()
            .all()
        )
        recipient_types = {r.recipient_type for r in rows}
        assert recipient_types == {"supplier", "customer", "internal"}
        # Zero-sends invariant (PRD §13.2 + schema validator).
        for r in rows:
            assert r.sent_at is None

        log_rows = (
            (
                await s.execute(
                    select(AgentLog).where(
                        AgentLog.event_type == "openclaw.SaveDraftCommunications"
                    )
                )
            )
            .scalars()
            .all()
        )
        assert len(log_rows) == 1


@pytest.mark.asyncio
async def test_flip_shipment_statuses_updates_and_logs(
    impact_session: tuple[AsyncSession, TyphoonSeed, uuid.UUID],
) -> None:
    from backend.agents.strategist.actions.openclaw_actions import (
        FlipShipmentStatuses,
        FlipShipmentStatusesArgs,
    )

    _, seed, _ = impact_session
    target_ids = seed.shipment_ids[:3]

    async with session() as s:
        flipped = await FlipShipmentStatuses().execute(
            s,
            FlipShipmentStatusesArgs(shipment_ids=target_ids, to="rerouting"),
        )
        await s.commit()

    assert flipped == 3

    async with session() as s:
        rows = (
            (
                await s.execute(
                    select(Shipment.id, Shipment.status).where(
                        Shipment.id.in_(target_ids)
                    )
                )
            )
            .all()
        )
        assert {r.status for r in rows} == {"rerouting"}

        log_rows = (
            (
                await s.execute(
                    select(AgentLog).where(
                        AgentLog.event_type == "openclaw.FlipShipmentStatuses"
                    )
                )
            )
            .scalars()
            .all()
        )
        assert len(log_rows) == 1


@pytest.mark.asyncio
async def test_write_approval_audit_persists_snapshot_and_logs(
    impact_session: tuple[AsyncSession, TyphoonSeed, uuid.UUID],
) -> None:
    from backend.agents.strategist.actions.openclaw_actions import (
        SaveMitigationOptions,
        SaveMitigationOptionsArgs,
        WriteApprovalAudit,
        WriteApprovalAuditArgs,
    )

    _, _, impact_id = impact_session

    async with session() as s:
        option_ids = await SaveMitigationOptions().execute(
            s,
            SaveMitigationOptionsArgs(
                impact_report_id=impact_id,
                options=[_mk_option(1, "reroute")],
            ),
        )
        mitigation_id = option_ids[0]
        snapshot = {"shipment_ids_flipped": ["SHP-T001", "SHP-T002"], "delta_usd": "42000"}
        approval_id = await WriteApprovalAudit().execute(
            s,
            WriteApprovalAuditArgs(
                mitigation_id=mitigation_id,
                approved_by="operator@suppl.ai",
                state_snapshot=snapshot,
            ),
        )
        await s.commit()

    async with session() as s:
        row = (
            await s.execute(select(Approval).where(Approval.id == approval_id))
        ).scalar_one()
        assert row.mitigation_id == mitigation_id
        assert row.approved_by == "operator@suppl.ai"
        assert row.state_snapshot["delta_usd"] == "42000"

        log_rows = (
            (
                await s.execute(
                    select(AgentLog).where(
                        AgentLog.event_type == "openclaw.WriteApprovalAudit"
                    )
                )
            )
            .scalars()
            .all()
        )
        assert len(log_rows) == 1
