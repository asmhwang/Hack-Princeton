"""Provision the 4 Dedalus Machines needed for suppl.ai (Task 12.1 / A.7.a).

Machines: ``scout-vm``, ``analyst-vm``, ``strategist-vm``, ``db-vm``. Default
tier unless overridden via ``--tier``.

This script is idempotent: if a Machine with the requested name already exists
it is reused (the request succeeds and prints the existing host). On
``NoReadyHosts`` Dedalus responses the script prints an actionable hint and
exits non-zero — caller deletes orphans and reruns.

Auth:
    ``DEDALUS_API_KEY`` from environment or ``--api-key``. Base URL defaults
    to ``DEDALUS_API_URL`` env or ``https://api.dedaluslabs.ai``. The
    provisioning API contract used here (``POST /v1/machines`` with JSON
    ``{"name","tier","region","image"}``) follows the Dedalus developer docs
    for HackPrinceton Spring '26; adjust the ``_create_machine`` payload if
    the contract shifts. Dry-run (``--dry-run``) prints the requests without
    hitting the network — safe for unit tests and CI.

Outputs:
    Writes ``infra/machines.json`` mapping logical name → host so the deploy
    script and smoke tests can read back the inventory without re-querying
    the control plane.

Usage:
    uv run python infra/provision.py
    uv run python infra/provision.py --dry-run
    uv run python infra/provision.py --only scout-vm,analyst-vm
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path

import httpx

_MACHINES = ("scout-vm", "analyst-vm", "strategist-vm", "db-vm")
_DEFAULT_BASE = "https://api.dedaluslabs.ai"
_DEFAULT_TIER = "default"
_DEFAULT_REGION = "us-east"
_DEFAULT_IMAGE = "ubuntu-22.04"
_TIMEOUT_S = 30.0
_HTTP_CONFLICT = 409
_HTTP_UNAVAILABLE = 503
_INVENTORY_PATH = Path(__file__).parent / "machines.json"


@dataclass
class _Machine:
    name: str
    host: str
    id: str
    tier: str
    region: str


class _ProvisionError(RuntimeError):
    pass


def _auth_headers(api_key: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}


def _list_machines(client: httpx.Client, base: str, api_key: str) -> dict[str, _Machine]:
    resp = client.get(f"{base}/v1/machines", headers=_auth_headers(api_key), timeout=_TIMEOUT_S)
    resp.raise_for_status()
    payload = resp.json()
    out: dict[str, _Machine] = {}
    for m in payload.get("machines", []):
        name = m.get("name")
        if not name:
            continue
        out[name] = _Machine(
            name=name,
            host=m.get("host", ""),
            id=m.get("id", ""),
            tier=m.get("tier", ""),
            region=m.get("region", ""),
        )
    return out


def _create_machine(
    client: httpx.Client,
    base: str,
    api_key: str,
    *,
    name: str,
    tier: str,
    region: str,
    image: str,
) -> _Machine:
    body = {"name": name, "tier": tier, "region": region, "image": image}
    resp = client.post(
        f"{base}/v1/machines",
        headers=_auth_headers(api_key),
        json=body,
        timeout=_TIMEOUT_S,
    )
    if resp.status_code == _HTTP_CONFLICT:  # already exists — idempotent path
        existing = _list_machines(client, base, api_key).get(name)
        if existing is None:
            raise _ProvisionError(f"409 on create {name} but not in list — control-plane race")
        return existing
    if resp.status_code == _HTTP_UNAVAILABLE and "NoReadyHosts" in resp.text:
        raise _ProvisionError(
            f"NoReadyHosts creating {name}. Delete orphan VMs "
            f"(https://dedaluslabs.ai/dashboard) or shrink memory request."
        )
    resp.raise_for_status()
    m = resp.json()
    return _Machine(
        name=m["name"],
        host=m.get("host", ""),
        id=m.get("id", ""),
        tier=m.get("tier", tier),
        region=m.get("region", region),
    )


def _write_inventory(machines: list[_Machine]) -> None:
    payload = {
        m.name: {"host": m.host, "id": m.id, "tier": m.tier, "region": m.region} for m in machines
    }
    _INVENTORY_PATH.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")


def _dry_run(names: list[str], tier: str, region: str, image: str) -> int:
    print(f"[dry-run] would POST /v1/machines for {len(names)} machines")
    for n in names:
        print(f"  {n:14s}  tier={tier}  region={region}  image={image}")
    print(f"[dry-run] would write inventory → {_INVENTORY_PATH}")
    return 0


def _run(names: list[str], *, api_key: str, base: str, tier: str, region: str, image: str) -> int:
    created: list[_Machine] = []
    with httpx.Client() as client:
        for name in names:
            try:
                m = _create_machine(
                    client, base, api_key, name=name, tier=tier, region=region, image=image
                )
            except _ProvisionError as e:
                print(f"error: {e}", file=sys.stderr)
                return 1
            except httpx.HTTPError as e:
                print(f"error: provisioning {name} failed: {e}", file=sys.stderr)
                return 1
            print(f"ok  {m.name:14s}  host={m.host}  id={m.id}")
            created.append(m)
    _write_inventory(created)
    print(f"wrote inventory → {_INVENTORY_PATH}")
    return 0


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(prog="provision", description="Provision suppl.ai Dedalus VMs.")
    p.add_argument("--api-key", default=os.environ.get("DEDALUS_API_KEY"))
    p.add_argument("--base", default=os.environ.get("DEDALUS_API_URL", _DEFAULT_BASE))
    p.add_argument("--tier", default=_DEFAULT_TIER)
    p.add_argument("--region", default=_DEFAULT_REGION)
    p.add_argument("--image", default=_DEFAULT_IMAGE)
    p.add_argument("--only", help="comma-separated subset of machine names to provision")
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="print planned requests without calling API",
    )
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    ns = _parse_args(argv)
    names = list(_MACHINES)
    if ns.only:
        subset = [s.strip() for s in ns.only.split(",") if s.strip()]
        unknown = [s for s in subset if s not in _MACHINES]
        if unknown:
            print(f"error: unknown machine(s): {unknown}. Valid: {_MACHINES}", file=sys.stderr)
            return 2
        names = subset
    if ns.dry_run:
        return _dry_run(names, ns.tier, ns.region, ns.image)
    if not ns.api_key:
        print("error: DEDALUS_API_KEY unset. Set env or pass --api-key.", file=sys.stderr)
        return 2
    return _run(
        names,
        api_key=ns.api_key,
        base=ns.base,
        tier=ns.tier,
        region=ns.region,
        image=ns.image,
    )


if __name__ == "__main__":
    sys.exit(main())
