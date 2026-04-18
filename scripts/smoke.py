"""Pre-flight smoke check — hits /health on every VM and the API.

Task 12.3 judging gate ("restart resumes from checkpoint without duplicate
signals") and demo-day readiness. Exit 0 iff every target returns HTTP 200
with ``{"ok": true}``. Exit 1 otherwise so CI / shell chains short-circuit.

Usage:
    uv run python scripts/smoke.py \\
        --scout http://scout-vm:9101/health \\
        --analyst http://analyst-vm:9102/health \\
        --strategist http://strategist-vm:9103/health \\
        --api http://api-vm:8000/health
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from dataclasses import dataclass

import httpx

_TIMEOUT_S = 5.0
_HTTP_OK = 200


@dataclass
class _Target:
    name: str
    url: str


@dataclass
class _Result:
    target: _Target
    status: int | None
    ok: bool
    error: str | None


async def _probe(client: httpx.AsyncClient, tgt: _Target) -> _Result:
    try:
        resp = await client.get(tgt.url, timeout=_TIMEOUT_S)
    except httpx.HTTPError as e:
        return _Result(tgt, None, False, str(e))
    try:
        body = resp.json()
    except ValueError as e:
        return _Result(tgt, resp.status_code, False, f"invalid json: {e}")
    ok = resp.status_code == _HTTP_OK and bool(body.get("ok"))
    return _Result(tgt, resp.status_code, ok, None if ok else f"body={body}")


def _print_table(results: list[_Result]) -> None:
    name_w = max((len(r.target.name) for r in results), default=8)
    url_w = max((len(r.target.url) for r in results), default=16)
    header = f"{'NAME':<{name_w}}  {'URL':<{url_w}}  STATUS  OK    NOTE"
    print(header)
    print("-" * len(header))
    for r in results:
        status = str(r.status) if r.status is not None else "---"
        flag = "yes" if r.ok else "NO"
        note = r.error or ""
        print(f"{r.target.name:<{name_w}}  {r.target.url:<{url_w}}  {status:<6}  {flag:<4}  {note}")


async def _run(targets: list[_Target]) -> int:
    if not targets:
        print("smoke: no targets given. Pass --scout/--analyst/--strategist/--api.")
        return 2
    async with httpx.AsyncClient() as client:
        results = await asyncio.gather(*(_probe(client, t) for t in targets))
    _print_table(results)
    return 0 if all(r.ok for r in results) else 1


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="smoke",
        description="Hit /health on every suppl.ai service; non-zero exit on failure.",
    )
    p.add_argument("--scout", help="Scout /health URL")
    p.add_argument("--analyst", help="Analyst /health URL")
    p.add_argument("--strategist", help="Strategist /health URL")
    p.add_argument("--api", help="API /health URL")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    ns = _parse_args(argv)
    targets: list[_Target] = []
    for name in ("scout", "analyst", "strategist", "api"):
        url = getattr(ns, name)
        if url:
            targets.append(_Target(name=name, url=url))
    return asyncio.run(_run(targets))


if __name__ == "__main__":
    sys.exit(main())
