"""Scout signal dedupe.

Two concerns:

- :func:`dedupe_hash` — stable SHA-256 fingerprint of `(region, category,
  keywords)`, normalized so punctuation / order / case variants collapse to
  the same hash.
- :func:`is_duplicate` — DB-level window check used by the Scout source
  loops before they insert a new signal.

The DB also enforces uniqueness on ``signals.dedupe_hash`` (Phase 1
migration) so this check is defense-in-depth against wasted round-trips,
not the sole safeguard.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from hashlib import sha256

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.models import Signal


def dedupe_hash(region: str, category: str, keywords: list[str]) -> str:
    """Return the canonical SHA-256 hash for `(region, category, keywords)`.

    Keywords are lower-cased, stripped, and sorted so that ordering variants
    and whitespace differences collapse to one hash.
    """
    norm_keywords = ",".join(sorted(k.strip().lower() for k in keywords))
    payload = f"{region.strip().lower()}||{category.strip().lower()}||{norm_keywords}"
    return sha256(payload.encode()).hexdigest()


async def is_duplicate(
    session: AsyncSession,
    dedupe_hash_value: str,
    *,
    window_hours: int = 72,
) -> bool:
    """Return True if a signal with ``dedupe_hash_value`` exists within the window."""
    cutoff = datetime.now(UTC).replace(tzinfo=None) - timedelta(hours=window_hours)
    stmt = select(Signal.id).where(
        Signal.dedupe_hash == dedupe_hash_value,
        Signal.first_seen_at >= cutoff,
    )
    result = await session.execute(stmt)
    return result.first() is not None
