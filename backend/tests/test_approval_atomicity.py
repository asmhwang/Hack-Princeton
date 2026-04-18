"""Atomic approval transaction tests — Task 9.1 / Plan C task C.7.

Critical invariant: mid-transaction failure leaves ZERO partial state.
All 5 tests must pass; each covers a distinct safety guarantee.
"""

from __future__ import annotations

import uuid
from decimal import Decimal

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import insert, select

from backend.api.main import app
from backend.db.models import (
    AffectedShipment,
    Approval,
    Customer,
    Disruption,
    DraftCommunication,
    ImpactReport,
    MitigationOption,
    Port,
    PurchaseOrder,
    Shipment,
    Sku,
    Supplier,
)
from backend.db.session import session

# ---------------------------------------------------------------------------
# Seed helper — builds the full FK chain needed for approval
# ---------------------------------------------------------------------------

# Fixed IDs so assertions are cheap; unique hex suffix prevents cross-test
# collisions even though conftest TRUNCATEs between tests.
_PORT_A = "PT-TEST-A"
_PORT_B = "PT-TEST-B"
_SUPPLIER_ID = "SUP-TEST-01"
_CUSTOMER_ID = "CUS-TEST-01"
_SKU_ID = "SKU-TEST-01"
_PO_ID = "PO-TEST-001"
_SHP_IDS = ["SHP-TEST-001", "SHP-TEST-002", "SHP-TEST-003"]


async def _seed_approval_scenario(s):  # type: ignore[no-untyped-def]
    """Seed: ports → supplier → customer → SKU → PO → 3 shipments →
    disruption → impact_report → mitigation_option →
    3 affected_shipments → 2 draft_communications.

    Returns a dict with the key IDs needed by the tests.
    """
    # Reference data
    await s.execute(
        insert(Port).values(
            [
                {"id": _PORT_A, "name": "Test Port A", "country": "US", "modes": []},
                {"id": _PORT_B, "name": "Test Port B", "country": "CN", "modes": []},
            ]
        )
    )
    await s.execute(insert(Supplier).values(id=_SUPPLIER_ID, name="Test Supplier", categories=[]))
    await s.execute(insert(Customer).values(id=_CUSTOMER_ID, name="Test Customer"))
    await s.execute(insert(Sku).values(id=_SKU_ID))
    await s.execute(
        insert(PurchaseOrder).values(
            id=_PO_ID,
            customer_id=_CUSTOMER_ID,
            sku_id=_SKU_ID,
            qty=100,
            revenue=Decimal("50000"),
        )
    )

    # 3 shipments in "in_transit" — these are what the approval will flip
    await s.execute(
        insert(Shipment).values(
            [
                {
                    "id": shp_id,
                    "po_id": _PO_ID,
                    "supplier_id": _SUPPLIER_ID,
                    "origin_port_id": _PORT_B,
                    "dest_port_id": _PORT_A,
                    "status": "in_transit",
                }
                for shp_id in _SHP_IDS
            ]
        )
    )

    # Domain chain
    disruption_id = uuid.uuid4()
    await s.execute(
        insert(Disruption).values(
            id=disruption_id,
            title="Test Disruption",
            category="weather",
            severity=3,
            confidence=Decimal("0.8"),
            status="active",
            source_signal_ids=[],
        )
    )

    impact_id = uuid.uuid4()
    await s.execute(
        insert(ImpactReport).values(
            id=impact_id,
            disruption_id=disruption_id,
            total_exposure=Decimal("250000"),
            units_at_risk=300,
            cascade_depth=2,
            reasoning_trace={"tool_calls": [], "final_reasoning": "test"},
        )
    )

    mitigation_id = uuid.uuid4()
    await s.execute(
        insert(MitigationOption).values(
            id=mitigation_id,
            impact_report_id=impact_id,
            option_type="reroute",
            description="Reroute via alternative port",
            delta_cost=Decimal("12000"),
            delta_days=2,
            confidence=Decimal("0.85"),
            rationale="Port congestion expected to clear within 3 days.",
            status="pending",
        )
    )

    # 3 affected shipments linking the mitigation's impact report to the shipments
    await s.execute(
        insert(AffectedShipment).values(
            [
                {
                    "impact_report_id": impact_id,
                    "shipment_id": shp_id,
                    "exposure": Decimal("83333"),
                    "days_to_sla_breach": 5,
                }
                for shp_id in _SHP_IDS
            ]
        )
    )

    # 2 draft communications
    draft_ids = [uuid.uuid4(), uuid.uuid4()]
    await s.execute(
        insert(DraftCommunication).values(
            [
                {
                    "id": draft_ids[0],
                    "mitigation_id": mitigation_id,
                    "recipient_type": "supplier",
                    "recipient_contact": "supplier@test.com",
                    "subject": "Reroute notice",
                    "body": "Please reroute shipment per attached instructions.",
                },
                {
                    "id": draft_ids[1],
                    "mitigation_id": mitigation_id,
                    "recipient_type": "customer",
                    "recipient_contact": "customer@test.com",
                    "subject": "Delay notification",
                    "body": "Your shipment may be delayed due to a supply chain disruption.",
                },
            ]
        )
    )

    return {
        "disruption_id": disruption_id,
        "impact_id": impact_id,
        "mitigation_id": mitigation_id,
        "shipment_ids": _SHP_IDS,
        "draft_ids": draft_ids,
    }


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_approval_happy_path() -> None:
    """Full approval: shipments flip to rerouting, Approval row written, mitigation approved."""
    async with session() as s:
        ctx = await _seed_approval_scenario(s)
        await s.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.post(f"/api/mitigations/{ctx['mitigation_id']}/approve")

    assert r.status_code == 200
    body = r.json()
    assert body["shipments_flipped"] == 3
    assert body["drafts_saved"] == 2

    # Verify DB state
    async with session() as s:
        shipments = (
            (await s.execute(select(Shipment).where(Shipment.id.in_(ctx["shipment_ids"]))))
            .scalars()
            .all()
        )
        assert all(sh.status == "rerouting" for sh in shipments)

        approvals = (
            (
                await s.execute(
                    select(Approval).where(Approval.mitigation_id == ctx["mitigation_id"])
                )
            )
            .scalars()
            .all()
        )
        assert len(approvals) == 1
        assert approvals[0].approved_by == "maya_chen"

        # Drafts must be unchanged (pre-existing, approval does not modify them)
        drafts = (
            (
                await s.execute(
                    select(DraftCommunication).where(
                        DraftCommunication.mitigation_id == ctx["mitigation_id"]
                    )
                )
            )
            .scalars()
            .all()
        )
        assert len(drafts) == 2

        mit = (
            await s.execute(
                select(MitigationOption).where(MitigationOption.id == ctx["mitigation_id"])
            )
        ).scalar_one()
        assert mit.status == "approved"


@pytest.mark.asyncio
async def test_approval_rollback_on_audit_write_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    """If audit write fails mid-transaction, shipments must NOT flip, no Approval row."""
    async with session() as s:
        ctx = await _seed_approval_scenario(s)
        await s.commit()

    # Monkey-patch the audit write helper inside _approval module
    from backend.api import _approval as approval_mod

    async def _boom(*args: object, **kwargs: object) -> None:
        raise RuntimeError("simulated audit failure")

    monkeypatch.setattr(approval_mod, "_write_audit", _boom)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.post(f"/api/mitigations/{ctx['mitigation_id']}/approve")

    assert r.status_code == 500

    # VERIFY: no partial state
    async with session() as s:
        shipments = (
            (await s.execute(select(Shipment).where(Shipment.id.in_(ctx["shipment_ids"]))))
            .scalars()
            .all()
        )
        assert all(sh.status == "in_transit" for sh in shipments), (
            "shipment statuses must be unchanged after audit write failure"
        )

        approvals = (
            (
                await s.execute(
                    select(Approval).where(Approval.mitigation_id == ctx["mitigation_id"])
                )
            )
            .scalars()
            .all()
        )
        assert len(approvals) == 0, "no Approval row must be written"

        mit = (
            await s.execute(
                select(MitigationOption).where(MitigationOption.id == ctx["mitigation_id"])
            )
        ).scalar_one()
        assert mit.status == "pending", "mitigation status must not flip"


@pytest.mark.asyncio
async def test_approval_rollback_on_shipment_flip_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    """If shipment flip fails, no Approval row and mitigation stays pending."""
    async with session() as s:
        ctx = await _seed_approval_scenario(s)
        await s.commit()

    from backend.api import _approval as approval_mod

    async def _boom(*args: object, **kwargs: object) -> None:
        raise RuntimeError("simulated shipment flip failure")

    monkeypatch.setattr(approval_mod, "_flip_shipments", _boom)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.post(f"/api/mitigations/{ctx['mitigation_id']}/approve")

    assert r.status_code == 500

    async with session() as s:
        approvals = (
            (
                await s.execute(
                    select(Approval).where(Approval.mitigation_id == ctx["mitigation_id"])
                )
            )
            .scalars()
            .all()
        )
        assert len(approvals) == 0, "no Approval row must be written after shipment flip failure"

        mit = (
            await s.execute(
                select(MitigationOption).where(MitigationOption.id == ctx["mitigation_id"])
            )
        ).scalar_one()
        assert mit.status == "pending", "mitigation status must not flip after shipment failure"


@pytest.mark.asyncio
async def test_approval_404_on_unknown_mitigation() -> None:
    """Unknown mitigation ID returns 404."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.post(f"/api/mitigations/{uuid.uuid4()}/approve")
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_approval_409_on_already_approved() -> None:
    """Attempting to approve an already-approved mitigation returns 409."""
    async with session() as s:
        ctx = await _seed_approval_scenario(s)
        # Mark as approved already before calling the endpoint
        await s.execute(
            MitigationOption.__table__.update()
            .where(MitigationOption.id == ctx["mitigation_id"])
            .values(status="approved")
        )
        await s.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.post(f"/api/mitigations/{ctx['mitigation_id']}/approve")

    assert r.status_code == 409
