"""Seed a historical trail of 6 resolved disruptions over the past 30 days.

Purpose: make Analytics / Exec / Activity screens look populated on demo day
without spoiling Beat 1's empty War Room. All disruptions are inserted with
status="resolved" and include:

- 1–2 source Signal rows, each pre-dating the disruption
- 1 ImpactReport row with hand-tuned reasoning_trace
- ≤3 AffectedShipment rows pinned to a per-slug prime chain
- 1–2 MitigationOption rows; the first is marked status="approved"
- 1 Approval row for the approved mitigation (approved_at shortly after impact)
- AgentLog cascade timeline

All inserts use ON CONFLICT DO NOTHING. Re-running inserts fresh UUIDs so
you'll accumulate rows if you run it multiple times — that's intentional;
analytics should aggregate cumulatively.

Usage:
    uv run python -m backend.scripts.seed_history
"""

from __future__ import annotations

import asyncio
import hashlib
import sys
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from backend.db.session import DBSettings
from backend.scripts.scenarios.demo_fixtures import (
    HISTORICAL_FIXTURES,
    HistoricalFixture,
    _trace,
)
from backend.scripts.seed_helpers import (
    insert_affected_shipments,
    insert_approval,
    insert_disruption,
    insert_impact_report,
    insert_mitigation,
    insert_signal,
    seed_cascade_agent_logs,
    seed_historical_prime_chain,
)


async def seed_one_historical(s: AsyncSession, fx: HistoricalFixture, now: datetime) -> uuid.UUID:
    # 1. Prime chain for this slug.
    base_date = (now - timedelta(days=fx.days_ago)).date() - timedelta(days=20)
    shipment_ids = await seed_historical_prime_chain(
        s,
        slug=fx.slug,
        region=fx.region,
        lat=fx.lat,
        lng=fx.lng,
        base_date=base_date,
    )

    disruption_id = uuid.uuid4()
    trace_id = uuid.uuid4()
    disruption_seen = now - timedelta(days=fx.days_ago)
    disruption_last_seen = disruption_seen + timedelta(days=2)  # resolved within a few days

    # 2. Signal rows (inserted pre-disruption).
    signal_ids: list[uuid.UUID] = []
    for i, sig in enumerate(fx.source_signals):
        sig_id = uuid.uuid4()
        signal_ids.append(sig_id)
        await insert_signal(
            s,
            signal_id=sig_id,
            source_category=sig.source_category,
            source_name=sig.source_name,
            title=sig.title,
            summary=sig.summary,
            region=sig.region,
            lat=sig.lat,
            lng=sig.lng,
            radius_km=sig.radius_km,
            source_urls=list(sig.source_urls),
            confidence=sig.confidence,
            first_seen_at=disruption_seen - timedelta(hours=sig.hours_before_disruption),
            dedupe_hash=hashlib.sha256(
                f"seed_history:{fx.slug}:{i}:{sig_id.hex}".encode()
            ).hexdigest(),
            promoted_to_disruption_id=disruption_id,
        )

    # 3. Disruption row (resolved).
    await insert_disruption(
        s,
        disruption_id=disruption_id,
        title=fx.title,
        summary=fx.summary,
        category=fx.category,
        severity=fx.severity,
        region=fx.region,
        lat=fx.lat,
        lng=fx.lng,
        radius_km=fx.radius_km,
        source_signal_ids=signal_ids,
        confidence=0.9,
        first_seen_at=disruption_seen,
        last_seen_at=disruption_last_seen,
        status="resolved",
    )

    # 4. Impact report.
    impact_id = uuid.uuid4()
    impact_generated_at = disruption_seen + timedelta(seconds=14)
    trace = _trace(
        region=fx.region,
        lat=fx.lat,
        lng=fx.lng,
        radius_km=fx.radius_km,
        shipment_ids=shipment_ids,
        exposure_rows=max(2, fx.units_at_risk // 2),
        row_count=fx.units_at_risk,
        final_reasoning=(
            f"{fx.title}. "
            f"{fx.units_at_risk} shipments within the advisory radius, total exposure "
            f"${fx.total_exposure:,}. "
            f"Resolved via {fx.mitigations[0].option_type.replace('_', ' ')} option — "
            f"confidence {int(fx.mitigations[0].confidence * 100)}%."
        ),
    )
    await insert_impact_report(
        s,
        impact_id=impact_id,
        disruption_id=disruption_id,
        total_exposure=fx.total_exposure,
        units_at_risk=fx.units_at_risk,
        cascade_depth=2,
        reasoning_trace=trace,
        generated_at=impact_generated_at,
    )

    # 5. Affected shipments (use only affected_count of the 3 prime chain ships).
    per_ship_exposure = fx.total_exposure / fx.affected_count
    shipments = [
        (shipment_ids[i], per_ship_exposure, None)  # SLA breach days null since resolved
        for i in range(min(fx.affected_count, len(shipment_ids)))
    ]
    await insert_affected_shipments(s, impact_id=impact_id, shipments=shipments)

    # 6. Mitigations — first one approved.
    mitigation_ids: list[uuid.UUID] = []
    for idx, mfx in enumerate(fx.mitigations):
        mid = uuid.uuid4()
        mitigation_ids.append(mid)
        await insert_mitigation(
            s,
            mitigation_id=mid,
            impact_report_id=impact_id,
            option_type=mfx.option_type,
            description=mfx.description,
            delta_cost=mfx.delta_cost,
            delta_days=mfx.delta_days,
            confidence=mfx.confidence,
            rationale=mfx.rationale,
            status="approved" if idx == 0 else "dismissed",
        )
        if idx == 0:
            await insert_approval(
                s,
                approval_id=uuid.uuid4(),
                mitigation_id=mid,
                approved_by="maya@suppl.ai",
                approved_at=impact_generated_at + timedelta(minutes=3),
                state_snapshot={
                    "disruption_id": str(disruption_id),
                    "impact_report_id": str(impact_id),
                    "mitigation_id": str(mid),
                    "shipment_ids": [sid for (sid, _, _) in shipments],
                    "total_exposure": str(fx.total_exposure),
                    "resolved_at": disruption_last_seen.isoformat(),
                },
            )

    # 7. Agent log cascade.
    await seed_cascade_agent_logs(
        s,
        trace_id=trace_id,
        disruption_id=disruption_id,
        impact_id=impact_id,
        mitigation_ids=mitigation_ids,
        first_seen_at=disruption_seen,
        total_exposure=fx.total_exposure,
    )

    await s.commit()
    return disruption_id


async def _main() -> None:
    settings = DBSettings()
    engine = create_async_engine(settings.database_url, echo=False)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    seeded: list[tuple[str, uuid.UUID, int]] = []
    now = datetime.now(UTC).replace(tzinfo=None)
    async with session_factory() as s:
        for fx in HISTORICAL_FIXTURES:
            disruption_id = await seed_one_historical(s, fx, now)
            seeded.append((fx.title, disruption_id, fx.days_ago))
    await engine.dispose()

    print("─" * 80)
    print(f"  Seeded {len(seeded)} historical resolved disruptions")
    for title, did, days_ago in seeded:
        print(f"    T-{days_ago:>3}d  {str(did)[:8]}  {title}")
    print("─" * 80)


if __name__ == "__main__":
    asyncio.run(_main())
    sys.exit(0)
