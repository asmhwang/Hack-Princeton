"""Idempotency test for seed_all.

Runs seed_all twice in the same session and asserts row counts are identical
on both runs and match the expected exact counts.
"""

from __future__ import annotations

import pytest
from sqlalchemy import func, select

from backend.db.models import Customer, Port, PurchaseOrder, Shipment, Sku, Supplier
from backend.db.session import session
from backend.scripts.seed import seed_all

_EXPECTED = {
    "ports": 30,
    "suppliers": 50,
    "skus": 40,
    "customers": 20,
    "purchase_orders": 200,
    "shipments": 500,
}


async def _counts(s) -> dict[str, int]:  # type: ignore[type-arg]
    return {
        m.__tablename__: (await s.execute(select(func.count()).select_from(m))).scalar_one()
        for m in [Port, Supplier, Sku, Customer, PurchaseOrder, Shipment]
    }


@pytest.mark.asyncio
async def test_seed_is_idempotent() -> None:
    async with session() as s:
        await seed_all(s)
        await s.commit()
        first = await _counts(s)

        await seed_all(s)
        await s.commit()
        second = await _counts(s)

    assert first == _EXPECTED, f"First run counts mismatch: {first}"
    assert second == _EXPECTED, f"Second run counts mismatch: {second}"


@pytest.mark.asyncio
async def test_shipment_status_distribution() -> None:
    async with session() as s:
        await seed_all(s)
        await s.commit()

        for status, expected in [("in_transit", 300), ("planned", 100), ("arrived", 100)]:
            count = (
                await s.execute(
                    select(func.count()).select_from(Shipment).where(Shipment.status == status)
                )
            ).scalar_one()
            assert count == expected, f"Expected {expected} {status} shipments, got {count}"


@pytest.mark.asyncio
async def test_no_same_origin_dest_port() -> None:
    async with session() as s:
        await seed_all(s)
        await s.commit()

        same_port_count = (
            await s.execute(
                select(func.count())
                .select_from(Shipment)
                .where(Shipment.origin_port_id == Shipment.dest_port_id)
            )
        ).scalar_one()
        assert same_port_count == 0, f"Found {same_port_count} shipments with same origin/dest"


@pytest.mark.asyncio
async def test_electronics_supplier_count() -> None:
    async with session() as s:
        await seed_all(s)
        await s.commit()

        count = (
            await s.execute(
                select(func.count()).select_from(Supplier).where(Supplier.industry == "electronics")
            )
        ).scalar_one()
        expected_electronics = 15
        assert count == expected_electronics, (
            f"Expected {expected_electronics} electronics suppliers, got {count}"
        )
