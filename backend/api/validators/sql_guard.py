from __future__ import annotations

import re

import sqlparse


class SqlSafetyError(ValueError):
    pass


_FORBIDDEN = {
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
}


def validate_select_only(sql: str) -> None:
    """Validate that *sql* is a single, read-only SELECT statement.

    Raises SqlSafetyError on any violation.  Used as defense-in-depth before
    persisting synthesized SQL into impact_reports.sql_executed.
    """
    stripped = sql.strip()
    if not stripped:
        raise SqlSafetyError("empty query")

    # 1. Strip block comments (/*...*/) — they are dead code and safe to remove.
    no_block_comments = re.sub(r"/\*.*?\*/", "", stripped, flags=re.DOTALL)

    # 2. Reject if any line comment (--) remains after block-comment stripping.
    #    Analyst-synthesized SQL never needs line comments; their presence is
    #    suspicious (classic -- ; DROP injection pattern).
    if "--" in no_block_comments:
        raise SqlSafetyError("line comments (--) are not permitted")

    # 3. Reject pg_sleep and similar DoS functions by substring — they are not
    #    tokenized as SQL keywords so keyword scanning won't catch them.
    lower = no_block_comments.lower()
    if "pg_sleep" in lower:
        raise SqlSafetyError("forbidden function: pg_sleep")

    # 4. Exactly one non-empty statement after comment removal.
    statements = [s for s in sqlparse.split(no_block_comments) if s.strip()]
    if len(statements) != 1:
        raise SqlSafetyError(f"exactly one SELECT statement required, got {len(statements)}")

    # 5. Parse tokens.
    parsed = sqlparse.parse(statements[0])[0]
    tokens = [t for t in parsed.flatten() if not t.is_whitespace]  # type: ignore[no-untyped-call]
    if not tokens:
        raise SqlSafetyError("empty parse result")

    # 6. First keyword must be SELECT or WITH (CTEs that read are fine).
    first_kw = next((t for t in tokens if t.ttype and "Keyword" in str(t.ttype)), None)
    if first_kw is None or first_kw.normalized.upper() not in {"SELECT", "WITH"}:
        raise SqlSafetyError(
            f"query must start with SELECT or WITH, got "
            f"{first_kw.normalized if first_kw else 'nothing'}"
        )

    # 7. No forbidden keyword anywhere in the statement.
    for tok in tokens:
        if tok.ttype and "Keyword" in str(tok.ttype):
            kw = tok.normalized.upper()
            if kw in _FORBIDDEN:
                raise SqlSafetyError(f"forbidden keyword: {kw}")

    # 8. Must have at least one non-keyword token — catches bare "SELECT" with
    #    no column list or expression.
    non_keyword_tokens = [t for t in tokens if not (t.ttype and "Keyword" in str(t.ttype))]
    if not non_keyword_tokens:
        raise SqlSafetyError("SELECT has no body")
