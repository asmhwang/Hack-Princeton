"""Demo simulate helper — POST /api/dev/simulate for one or all 5 scenarios.

Task 12.4 side task: lets a human (or CI) trigger the scripted disruptions
without keeping a browser tab open. Useful when priming the offline cache
(``scripts/prime_cache.py``) or driving the pitch-script end-to-end.

Usage:
    uv run python scripts/simulate.py --scenario typhoon_kaia
    uv run python scripts/simulate.py --all
    uv run python scripts/simulate.py --scenario busan_strike --api http://localhost:8000

Exit code 0 iff every requested scenario returned HTTP 200.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from dataclasses import dataclass

import httpx

from backend.scripts.scenarios import SCENARIOS

_DEFAULT_API = "http://localhost:8000"
_TIMEOUT_S = 30.0
_HTTP_OK = 200


@dataclass
class _Result:
    scenario: str
    status: int | None
    signal_id: str | None
    disruption_id: str | None
    error: str | None


async def _fire_one(client: httpx.AsyncClient, api: str, scenario: str) -> _Result:
    url = f"{api.rstrip('/')}/api/dev/simulate"
    try:
        resp = await client.post(url, json={"scenario": scenario}, timeout=_TIMEOUT_S)
    except httpx.HTTPError as err:
        return _Result(scenario, None, None, None, str(err))
    if resp.status_code != _HTTP_OK:
        return _Result(scenario, resp.status_code, None, None, f"body={resp.text[:200]}")
    try:
        body = resp.json()
    except ValueError as err:
        return _Result(scenario, resp.status_code, None, None, f"invalid json: {err}")
    return _Result(
        scenario,
        resp.status_code,
        str(body.get("signal_id")),
        str(body.get("disruption_id")),
        None,
    )


def _print_results(results: list[_Result]) -> None:
    width = max(len(r.scenario) for r in results)
    header = f"{'SCENARIO':<{width}}  STATUS  SIGNAL_ID                             DISRUPTION_ID"
    print(header)
    print("-" * len(header))
    for r in results:
        status = str(r.status) if r.status is not None else "---"
        sig = r.signal_id or "-"
        dis = r.disruption_id or "-"
        print(f"{r.scenario:<{width}}  {status:<6}  {sig:<36}  {dis}")
        if r.error:
            print(f"    error: {r.error}")


async def _run(api: str, scenarios: list[str]) -> int:
    async with httpx.AsyncClient() as client:
        results = await asyncio.gather(*(_fire_one(client, api, s) for s in scenarios))
    _print_results(results)
    return 0 if all(r.error is None and r.status == _HTTP_OK for r in results) else 1


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="simulate",
        description="POST /api/dev/simulate for one or all 5 canonical scenarios.",
    )
    p.add_argument("--scenario", choices=sorted(SCENARIOS.keys()))
    p.add_argument("--all", action="store_true", help="Fire every scenario once")
    p.add_argument("--api", default=_DEFAULT_API, help=f"API base URL (default: {_DEFAULT_API})")
    ns = p.parse_args(argv)
    if not ns.scenario and not ns.all:
        p.error("pass --scenario <id> or --all")
    return ns


def main(argv: list[str] | None = None) -> int:
    ns = _parse_args(argv)
    scenarios = sorted(SCENARIOS.keys()) if ns.all else [ns.scenario]
    return asyncio.run(_run(ns.api, scenarios))


if __name__ == "__main__":
    sys.exit(main())
