from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import Select
from sqlalchemy.orm.attributes import InstrumentedAttribute

_MAX_LIMIT = 200


def apply_cursor(
    stmt: Select[Any],
    *,
    before_col: InstrumentedAttribute[datetime],
    before: datetime | None,
    limit: int,
) -> Select[Any]:
    """Apply cursor-pagination to a SELECT statement.

    Args:
        stmt:       The base SELECT to modify (must already be ordered).
        before_col: The ORM-mapped column to use as the cursor (e.g. Signal.first_seen_at).
        before:     If provided, restrict results to rows where before_col < before.
        limit:      Max rows to return; clamped to _MAX_LIMIT.

    Returns:
        Modified SELECT with WHERE clause and LIMIT applied.
    """
    if before is not None:
        stmt = stmt.where(before_col < before)
    return stmt.limit(min(limit, _MAX_LIMIT))
