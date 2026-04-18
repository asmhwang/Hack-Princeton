from __future__ import annotations

import re

import sqlparse


class SqlSafetyError(ValueError):
    pass


_FORBIDDEN_KEYWORDS = {
    "INSERT",
    "UPDATE",
    "DELETE",
    "DROP",
    "ALTER",
    "TRUNCATE",
    "GRANT",
    "REVOKE",
    "CREATE",
    "REPLACE",
    "COPY",
    "VACUUM",
    "MERGE",
    "CALL",
    "LOCK",
    "SET",
    "EXPLAIN",
    "DISCARD",
    "RESET",
    "CLUSTER",
    "REINDEX",
    "LISTEN",
    "NOTIFY",
}

_FORBIDDEN_FUNCTIONS = {
    "pg_sleep",
    "pg_advisory_lock",
    "pg_advisory_xact_lock",
    "pg_terminate_backend",
    "pg_cancel_backend",
    "dblink",
    "dblink_exec",
    "lo_import",
    "lo_export",
}


def validate_select_only(sql: str) -> None:  # noqa: PLR0912 — each branch is a distinct reject path
    """Validate that *sql* is a single, read-only SELECT statement.

    Defense-in-depth gate before persisting synthesized SQL to
    ``impact_reports.sql_executed``. Checks happen at the sqlparse token level
    (not raw text) so string literals like ``WHERE notes = 'pg_sleep_active'``
    do not false-reject.
    """
    stripped = sql.strip()
    if not stripped:
        raise SqlSafetyError("empty query")

    # Strip block comments first — they are dead code and safe to remove. This
    # matters before the multi-statement split because a `/* ; */` would
    # otherwise be miscounted.
    no_block_comments = re.sub(r"/\*.*?\*/", "", stripped, flags=re.DOTALL)

    # Exactly one non-empty statement.
    statements = [s for s in sqlparse.split(no_block_comments) if s.strip()]
    if len(statements) != 1:
        raise SqlSafetyError(f"exactly one SELECT statement required, got {len(statements)}")

    parsed = sqlparse.parse(statements[0])[0]
    all_tokens = list(parsed.flatten())  # type: ignore[no-untyped-call]

    # Reject line comments (--) at the token level. sqlparse exposes them as
    # Token.Comment.Single. Operating on tokens — not raw text — means a
    # literal like `WHERE x = 'uses -- as separator'` passes cleanly.
    for tok in all_tokens:
        if tok.ttype and "Comment.Single" in str(tok.ttype):
            raise SqlSafetyError("line comments (--) are not permitted")

    tokens = [t for t in all_tokens if not t.is_whitespace]
    if not tokens:
        raise SqlSafetyError("empty parse result")

    # First keyword must be SELECT or WITH (CTEs that read are fine).
    first_kw = next((t for t in tokens if t.ttype and "Keyword" in str(t.ttype)), None)
    if first_kw is None or first_kw.normalized.upper() not in {"SELECT", "WITH"}:
        raise SqlSafetyError(
            f"query must start with SELECT or WITH, got "
            f"{first_kw.normalized if first_kw else 'nothing'}"
        )

    # No forbidden keyword anywhere.
    for tok in tokens:
        if tok.ttype and "Keyword" in str(tok.ttype):
            kw = tok.normalized.upper()
            if kw in _FORBIDDEN_KEYWORDS:
                raise SqlSafetyError(f"forbidden keyword: {kw}")

    # Forbidden functions — check at Name-token level so `pg_sleep_active` as
    # an identifier or a string-literal is not caught. sqlparse tags bare
    # identifiers as Token.Name; a function call is followed by `(`.
    for i, tok in enumerate(tokens):
        if tok.ttype and "Name" in str(tok.ttype):
            name = tok.normalized.lower()
            if name in _FORBIDDEN_FUNCTIONS:
                next_tok = tokens[i + 1] if i + 1 < len(tokens) else None
                if next_tok is not None and next_tok.value == "(":
                    raise SqlSafetyError(f"forbidden function: {name}")

    # Non-keyword, non-punctuation body required — catches bare `SELECT`,
    # `SELECT;`. `SELECT *` is allowed (Wildcard counts as body).
    body = [
        t
        for t in tokens
        if not (t.ttype and ("Keyword" in str(t.ttype) or "Punctuation" in str(t.ttype)))
    ]
    if not body:
        raise SqlSafetyError("SELECT has no body")
