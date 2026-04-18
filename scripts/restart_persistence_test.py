"""Restart persistence test (Task 12.3 — judging gate).

For each agent VM:

1. Capture pre-restart signal count (``SELECT count(*) FROM signals``)
2. Capture ``/var/lib/supplai/state.json`` (size + sha256).
3. ``systemctl stop supplai-<agent>``
4. ``systemctl start supplai-<agent>``
5. Wait for ``/health`` to return ``{"ok": true}`` (max 30s).
6. Re-capture state.json; assert the on-disk file survived intact.
7. Wait 30s of steady-state, then re-check signal count: assert no rows
   with a duplicate ``content_hash`` landed (agent correctly resumed from
   the checkpoint cursor rather than replaying history).

Exit 0 iff all agents pass. Any failure prints the offending agent and
exits 1 — suitable as a pre-demo gate or a GitHub Actions job.

Usage:
    uv run python scripts/restart_persistence_test.py \\
        --ssh-user root --inventory infra/machines.json \\
        --database-url postgresql://postgres:postgres@db-vm:5432/supplai

If ``--inventory`` is omitted the script falls back to DNS-resolvable hostnames
(``scout-vm``, ``analyst-vm``, ``strategist-vm``). ``--database-url`` defaults
to the value of ``DATABASE_URL`` in the environment (asyncpg scheme is
rewritten to psycopg for this read-only script).
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path

import httpx

_STATE_PATH = "/var/lib/supplai/state.json"
_HEALTH_PORTS = {"scout": 9101, "analyst": 9102, "strategist": 9103}
_HEALTH_TIMEOUT_S = 30.0
_STEADY_STATE_WAIT_S = 30.0
_SSH_TIMEOUT_S = 15.0
_HTTP_OK = 200


@dataclass
class _Snapshot:
    size: int
    sha256: str


@dataclass
class _AgentResult:
    agent: str
    ok: bool
    note: str


def _ssh(host: str, user: str, cmd: str) -> subprocess.CompletedProcess[str]:
    argv = [
        "ssh",
        "-o",
        "BatchMode=yes",
        "-o",
        f"ConnectTimeout={int(_SSH_TIMEOUT_S)}",
        f"{user}@{host}",
        cmd,
    ]
    return subprocess.run(  # noqa: PLW1510 — capture_output implies check=False
        argv,
        capture_output=True,
        text=True,
        timeout=_SSH_TIMEOUT_S + 5,
    )


def _capture_state(host: str, user: str) -> _Snapshot | None:
    r = _ssh(host, user, f"sudo cat {_STATE_PATH} 2>/dev/null || true")
    if r.returncode != 0 or not r.stdout.strip():
        return None
    data = r.stdout.encode()
    return _Snapshot(size=len(data), sha256=hashlib.sha256(data).hexdigest())


def _restart(host: str, user: str, agent: str) -> None:
    unit = f"supplai-{agent}"
    r = _ssh(host, user, f"sudo systemctl restart {unit}")
    if r.returncode != 0:
        raise RuntimeError(f"systemctl restart {unit}: {r.stderr.strip()}")


async def _wait_healthy(url: str) -> bool:
    deadline = time.monotonic() + _HEALTH_TIMEOUT_S
    async with httpx.AsyncClient(timeout=5.0) as client:
        while time.monotonic() < deadline:
            try:
                resp = await client.get(url)
                if resp.status_code == _HTTP_OK and resp.json().get("ok"):
                    return True
            except (httpx.HTTPError, ValueError):
                pass
            await asyncio.sleep(1.0)
    return False


def _duplicate_content_hash_count(db_url: str) -> int:
    """Return count of content_hash values appearing more than once in signals."""
    import psycopg  # noqa: PLC0415 — psycopg is an optional gate-only dep

    sql = (
        "SELECT COALESCE(SUM(c - 1), 0) FROM ("
        "  SELECT content_hash, COUNT(*) AS c FROM signals "
        "  GROUP BY content_hash HAVING COUNT(*) > 1"
        ") t"
    )
    with psycopg.connect(db_url) as conn, conn.cursor() as cur:
        cur.execute(sql)
        row = cur.fetchone()
        return int(row[0]) if row else 0


async def _check_agent(  # noqa: PLR0911 — each early-return tags a distinct failure mode
    agent: str, host: str, user: str, db_url: str, check_dupes: bool
) -> _AgentResult:
    before = _capture_state(host, user)
    if before is None:
        return _AgentResult(agent, False, "no state.json on VM before restart")
    dup_before = _duplicate_content_hash_count(db_url) if check_dupes else 0
    try:
        _restart(host, user, agent)
    except (RuntimeError, subprocess.TimeoutExpired) as e:
        return _AgentResult(agent, False, f"restart failed: {e}")
    url = f"http://{host}:{_HEALTH_PORTS[agent]}/health"
    if not await _wait_healthy(url):
        return _AgentResult(agent, False, f"/health did not return ok within {_HEALTH_TIMEOUT_S}s")
    after = _capture_state(host, user)
    if after is None:
        return _AgentResult(agent, False, "state.json missing after restart")
    if after.sha256 != before.sha256:
        note = f"state.json changed across restart ({before.sha256[:8]} → {after.sha256[:8]})"
        return _AgentResult(agent, False, note)
    if check_dupes:
        await asyncio.sleep(_STEADY_STATE_WAIT_S)
        dup_after = _duplicate_content_hash_count(db_url)
        if dup_after > dup_before:
            delta = dup_after - dup_before
            return _AgentResult(agent, False, f"{delta} duplicate signals after restart")
    return _AgentResult(agent, True, "state preserved, no duplicate signals")


def _resolve_hosts(inventory: Path | None) -> dict[str, str]:
    if inventory is None:
        return {a: f"{a}-vm" for a in _HEALTH_PORTS}
    data = json.loads(inventory.read_text())
    out: dict[str, str] = {}
    for agent in _HEALTH_PORTS:
        entry = data.get(f"{agent}-vm")
        host = (entry or {}).get("host") or f"{agent}-vm"
        out[agent] = host
    return out


async def _run(
    *, user: str, inventory: Path | None, db_url: str, skip_db: bool, only: list[str] | None
) -> int:
    hosts = _resolve_hosts(inventory)
    agents = only or list(_HEALTH_PORTS.keys())
    results: list[_AgentResult] = []
    for agent in agents:
        if agent not in _HEALTH_PORTS:
            print(f"error: unknown agent {agent!r}", file=sys.stderr)
            return 2
        print(f"[{agent}] restart persistence check against {hosts[agent]} …")
        results.append(await _check_agent(agent, hosts[agent], user, db_url, not skip_db))
    print()
    name_w = max(len(r.agent) for r in results)
    for r in results:
        flag = "PASS" if r.ok else "FAIL"
        print(f"  {r.agent:<{name_w}}  {flag}  {r.note}")
    return 0 if all(r.ok for r in results) else 1


def _normalize_db_url(url: str) -> str:
    # asyncpg scheme not understood by psycopg
    return url.replace("postgresql+asyncpg://", "postgresql://", 1)


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="restart_persistence_test",
        description="Task 12.3 judging gate — stop + start every agent, assert clean resume.",
    )
    p.add_argument("--ssh-user", default=os.environ.get("REMOTE_USER", "root"))
    p.add_argument("--inventory", type=Path, help="infra/machines.json path")
    p.add_argument(
        "--database-url",
        default=os.environ.get(
            "DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/supplai"
        ),
    )
    p.add_argument(
        "--skip-db-check", action="store_true", help="skip duplicate-signal check (SSH-only mode)"
    )
    p.add_argument("--only", help="comma-separated subset: scout,analyst,strategist")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    ns = _parse_args(argv)
    only = [s.strip() for s in ns.only.split(",")] if ns.only else None
    db_url = _normalize_db_url(ns.database_url)
    try:
        return asyncio.run(
            _run(
                user=ns.ssh_user,
                inventory=ns.inventory,
                db_url=db_url,
                skip_db=ns.skip_db_check,
                only=only,
            )
        )
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    sys.exit(main())
