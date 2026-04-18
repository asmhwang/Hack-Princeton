"""Judging contract: Strategist drafts communications but NEVER sends email.

Fails CI if any runtime module under ``backend/`` or ``scripts/`` imports a
mail-transport library. Tests are exempt — a hypothetical test could legitimately
stub ``smtplib``. The guard scans source text, not runtime ``sys.modules``, so
conditional/lazy imports are caught too.
"""

from __future__ import annotations

import re
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SCAN_ROOTS = [_REPO_ROOT / "backend", _REPO_ROOT / "scripts"]
_EXCLUDE_DIR_PARTS = {"tests", "__pycache__", ".venv", "node_modules"}

# Match `import smtplib`, `from smtplib import …`, `import aiosmtplib …`,
# `from email.mime …`, etc. Comments/strings that happen to contain "smtp"
# (e.g., a docstring saying "never send email via SMTP") are allowed.
_FORBIDDEN = re.compile(
    r"^\s*(?:from|import)\s+("
    r"smtplib|aiosmtplib|email\.(?:mime|message)|"
    r"yagmail|mailjet|sendgrid|postmarker|mailgun"
    r")\b",
    re.MULTILINE,
)


def _iter_python_files() -> list[Path]:
    files: list[Path] = []
    for root in _SCAN_ROOTS:
        if not root.is_dir():
            continue
        for p in root.rglob("*.py"):
            if _EXCLUDE_DIR_PARTS & set(p.parts):
                continue
            files.append(p)
    return files


def test_no_smtp_imports_in_runtime_code() -> None:
    offenders: list[tuple[Path, str]] = []
    for path in _iter_python_files():
        text = path.read_text(encoding="utf-8", errors="replace")
        for match in _FORBIDDEN.finditer(text):
            offenders.append((path.relative_to(_REPO_ROOT), match.group(0).strip()))

    assert not offenders, (
        "Email-transport imports found — Strategist must only DRAFT, never SEND. "
        "draft_communications.sent_at must always be NULL.\n"
        + "\n".join(f"  {p}: {line}" for p, line in offenders)
    )
