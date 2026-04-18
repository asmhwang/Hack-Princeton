"""Scout fusion pass.

Cluster recent unpromoted signals by coarse region bucket (0.5° ≈ 55km) and
ask the LLM to fuse each multi-signal cluster into a single
:class:`DisruptionDraft`. Each successful draft is persisted as a
``disruptions`` row and the contributing signals are linked back via
``promoted_to_disruption_id``.

Scope notes:

- Solo-signal severity promotion (the "any ≥4 solo" rule from the plan) is
  not implemented here because the ``signals`` table does not currently
  persist classifier severity — that belongs to the Scout source loops and
  the classifier wrapper is authoritative. Fusion fires on cluster size
  ``>= 2`` only; solo promotion can be layered on when the schema carries
  a signal-level severity column.
- ``NOTIFY new_disruption`` is intentionally left to the caller
  (``scout/main.py``). This function returns the new disruption UUIDs so
  tests can assert without bus plumbing.
- Concurrent fusion is guarded by ``SELECT ... FOR UPDATE SKIP LOCKED`` on
  the candidate signal rows. Two Scout workers racing on the same cluster
  will see disjoint candidate sets.
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any, cast

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.models import Disruption, Signal
from backend.llm.client import LLMClient
from backend.schemas import DisruptionDraft

_PROMPT_PATH = Path(__file__).parent.parent / "prompts" / "fusion.md"

_BUCKET_DEGREES = 0.5
_MIN_AGE_SECONDS = 10
_MAX_AGE_HOURS = 72
_CLUSTER_MIN_SIZE = 2
_NO_FUSE_PREFIX = "NO_FUSE:"


def _region_bucket(lat: float | None, lng: float | None) -> tuple[float, float] | None:
    """Quantize coordinates to a ``_BUCKET_DEGREES`` grid; ``None`` if unset."""
    if lat is None or lng is None:
        return None
    return (
        round(lat / _BUCKET_DEGREES) * _BUCKET_DEGREES,
        round(lng / _BUCKET_DEGREES) * _BUCKET_DEGREES,
    )


def _signal_payload_for_prompt(sig: Signal) -> dict[str, Any]:
    return {
        "id": str(sig.id),
        "source_category": sig.source_category,
        "title": sig.title,
        "summary": sig.summary,
        "region": sig.region,
        "lat": float(sig.lat) if sig.lat is not None else None,
        "lng": float(sig.lng) if sig.lng is not None else None,
        "first_seen_at": sig.first_seen_at.isoformat(),
    }


def _load_prompt() -> str:
    return _PROMPT_PATH.read_text()


async def _candidate_signals(session: AsyncSession) -> list[Signal]:
    now = datetime.now(UTC).replace(tzinfo=None)
    min_age = now - timedelta(seconds=_MIN_AGE_SECONDS)
    max_age = now - timedelta(hours=_MAX_AGE_HOURS)
    stmt = (
        select(Signal)
        .where(
            Signal.promoted_to_disruption_id.is_(None),
            Signal.first_seen_at >= max_age,
            Signal.first_seen_at <= min_age,
        )
        .with_for_update(skip_locked=True)
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def _fuse_cluster(
    session: AsyncSession,
    cluster: list[Signal],
    llm: LLMClient,
    prompt_template: str,
) -> uuid.UUID | None:
    payload = {"signals": [_signal_payload_for_prompt(s) for s in cluster]}
    prompt = f"{prompt_template}\n\nCLUSTER:\n{json.dumps(payload, indent=2)}"
    cache_key = "fusion::" + "::".join(sorted(str(s.id) for s in cluster))

    draft_model = await llm.structured(prompt, DisruptionDraft, cache_key=cache_key)
    draft = cast(DisruptionDraft, draft_model)

    if draft.title.startswith(_NO_FUSE_PREFIX) or not draft.source_signal_ids:
        return None

    disruption = Disruption(
        id=uuid.uuid4(),
        title=draft.title,
        summary=draft.summary,
        category=draft.category,
        severity=draft.severity,
        region=draft.region,
        lat=draft.lat,
        lng=draft.lng,
        radius_km=Decimal(str(draft.radius_km)) if draft.radius_km is not None else None,
        source_signal_ids=draft.source_signal_ids,
        confidence=Decimal(str(draft.confidence)),
        status="active",
    )
    session.add(disruption)
    await session.flush()

    await session.execute(
        update(Signal)
        .where(Signal.id.in_(draft.source_signal_ids))
        .values(promoted_to_disruption_id=disruption.id)
    )
    return disruption.id


async def run_fusion_pass(session: AsyncSession, llm: LLMClient) -> list[uuid.UUID]:
    """Cluster unpromoted signals and create disruptions for each cluster.

    Returns the IDs of newly-created disruptions. ``NOTIFY new_disruption``
    is the caller's responsibility.
    """
    candidates = await _candidate_signals(session)
    if not candidates:
        return []

    buckets: dict[tuple[float, float], list[Signal]] = {}
    for sig in candidates:
        key = _region_bucket(
            float(sig.lat) if sig.lat is not None else None,
            float(sig.lng) if sig.lng is not None else None,
        )
        if key is None:
            continue
        buckets.setdefault(key, []).append(sig)

    new_ids: list[uuid.UUID] = []
    prompt_template = _load_prompt()
    for cluster in buckets.values():
        if len(cluster) < _CLUSTER_MIN_SIZE:
            continue
        disruption_id = await _fuse_cluster(session, cluster, llm, prompt_template)
        if disruption_id is not None:
            new_ids.append(disruption_id)
    return new_ids
