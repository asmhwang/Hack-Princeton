"""Prime offline SQLite caches for the 5 demo scenarios (Task 12.4).

This is an operator-run script: hit it once with live ``GEMINI_API_KEY``
(and optionally ``TAVILY_API_KEY``) to populate ``backend/llm/prompt_cache.sqlite``
and ``backend/agents/scout/sources/tavily-*.sqlite`` with responses for every
scripted scenario, then freeze the resulting DBs to ``*.sqlite.seed`` artefacts
the VM bootstrap copies into place when ``DEMO_OFFLINE_CACHE=true``.

What gets primed per scenario:

1. ``classify_raw_signal`` — Scout's first Gemini hit, keyed on the raw hit's
   URL. Cache fill means Scout can reclassify offline.
2. ``build_impact_report`` — Analyst's tool-calling loop keyed on the
   disruption UUID. Requires a seeded DB; the script inserts the scenario's
   signal + disruption rows + the typhoon-style fixture so the tool layer has
   rows to return. Uses the real DB at ``DATABASE_URL``.
3. ``generate_options`` / ``generate_drafts`` — Strategist's options bundle +
   three-draft set per impact report. Each is keyed independently.

Tavily cache priming is not done here because the Tavily SQLite is per-Scout-
source and fills naturally when Scout runs live for ~2 min against the source
set. Run ``uv run python -m backend.agents.scout.main`` for ~120s with
``TAVILY_API_KEY`` set, then copy ``scout-tavily-cache.sqlite`` →
``backend/llm/tavily_cache.sqlite.seed``.

Usage:
    GEMINI_API_KEY=... DATABASE_URL=... uv run python scripts/prime_cache.py
    uv run python scripts/prime_cache.py --scenario typhoon_kaia
    uv run python scripts/prime_cache.py --freeze   # just copy active → seed
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import shutil
import sys
import uuid
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

import structlog
from sqlalchemy.dialects.postgresql import insert as pg_insert

from backend.agents.analyst.processors.impact import build_impact_report
from backend.agents.scout.processors.classify import classify_raw_signal
from backend.agents.strategist.processors.drafts import generate_drafts
from backend.agents.strategist.processors.options import generate_options
from backend.db.bus import EventBus
from backend.db.models import (
    Customer,
    Disruption,
    Port,
    PurchaseOrder,
    Shipment,
    Signal,
    Sku,
    Supplier,
)
from backend.db.session import DBSettings, session
from backend.llm.client import LLMClient, LLMValidationError
from backend.scripts.scenarios import SCENARIOS
from backend.scripts.scenarios._types import Scenario
from backend.tests.fixtures.typhoon import seed_typhoon

log = structlog.get_logger()

_REPO_ROOT = Path(__file__).resolve().parent.parent
_PROMPT_CACHE_ACTIVE = _REPO_ROOT / "backend" / "llm" / "prompt_cache.sqlite"
_PROMPT_CACHE_SEED = _REPO_ROOT / "backend" / "llm" / "prompt_cache.sqlite.seed"
_TAVILY_CACHE_ACTIVE = _REPO_ROOT / "backend" / "llm" / "tavily_cache.sqlite"
_TAVILY_CACHE_SEED = _REPO_ROOT / "backend" / "llm" / "tavily_cache.sqlite.seed"


@dataclass
class _PrimeResult:
    scenario: str
    classify_ok: bool
    impact_ok: bool
    options_ok: bool
    drafts_ok: int
    error: str | None = None


# ---------------------------------------------------------------------------
# Tavily-shaped raw hit synth from a ScenarioSignal
# ---------------------------------------------------------------------------


def _scenario_raw_hit(scenario: Scenario) -> dict[str, Any]:
    """Build a Tavily-shaped raw hit so ``classify_raw_signal`` sees a stable
    ``url`` for cache keying. Matches Tavily response shape (title/content/url)."""
    sig = scenario.signal
    return {
        "title": sig.title,
        "content": sig.summary,
        "url": sig.source_urls[0] if sig.source_urls else f"https://suppl.ai/sim/{scenario.id}",
        "score": sig.confidence,
    }


# ---------------------------------------------------------------------------
# DB seeding per scenario — insert a signal + disruption row so
# build_impact_report/generate_options have inputs.
# ---------------------------------------------------------------------------


async def _seed_minimal_chain(s: Any, scenario: Scenario) -> None:
    """Seed minimal port+supplier+sku+customer+PO+shipments near the disruption.

    Ensures the Analyst tool loop finds real shipment IDs so ``affected_shipments``
    FK persist succeeds. Idempotent via ON CONFLICT DO NOTHING.
    """
    sid = scenario.id
    port_id = f"PORT-PRIME-{sid[:6].upper()}"
    supplier_id = f"SUP-PRIME-{sid[:6].upper()}"
    sku_id = f"SKU-PRIME-{sid[:6].upper()}"
    customer_id = f"CUST-PRIME-{sid[:6].upper()}"
    po_ids = [f"PO-PRIME-{sid[:4].upper()}-{i}" for i in range(1, 4)]
    shipment_ids = [f"SHP-PRIME-{sid[:4].upper()}-{i}" for i in range(1, 4)]
    today = date(2026, 4, 18)

    await s.execute(
        pg_insert(Port)
        .values(
            id=port_id,
            name=f"Prime-{sid}",
            country="XX",
            lat=Decimal(str(scenario.disruption.lat)),
            lng=Decimal(str(scenario.disruption.lng)),
            modes=["sea"],
        )
        .on_conflict_do_nothing()
    )
    await s.execute(
        pg_insert(Supplier)
        .values(
            id=supplier_id,
            name=f"Prime Supplier {sid}",
            country="XX",
            region=scenario.disruption.region,
            tier=1,
            industry="electronics",
            reliability_score=Decimal("0.9"),
            categories=["electronics"],
            lat=Decimal(str(scenario.disruption.lat)),
            lng=Decimal(str(scenario.disruption.lng)),
        )
        .on_conflict_do_nothing()
    )
    await s.execute(
        pg_insert(Sku)
        .values(
            id=sku_id,
            description=f"Prime SKU {sid}",
            family="electronics",
            industry="electronics",
            unit_cost=Decimal("10"),
            unit_revenue=Decimal("25"),
        )
        .on_conflict_do_nothing()
    )
    await s.execute(
        pg_insert(Customer)
        .values(
            id=customer_id,
            name=f"Prime Customer {sid}",
            tier="strategic",
            sla_days=14,
            contact_email=f"{sid}@example.com",
        )
        .on_conflict_do_nothing()
    )
    for i, po_id in enumerate(po_ids):
        await s.execute(
            pg_insert(PurchaseOrder)
            .values(
                id=po_id,
                customer_id=customer_id,
                sku_id=sku_id,
                qty=1000 * (i + 1),
                due_date=today + timedelta(days=14 + i * 7),
                revenue=Decimal(str(150000 * (i + 1))),
                sla_breach_penalty=Decimal("10000"),
            )
            .on_conflict_do_nothing()
        )
    for i, ship_id in enumerate(shipment_ids):
        await s.execute(
            pg_insert(Shipment)
            .values(
                id=ship_id,
                po_id=po_ids[i],
                supplier_id=supplier_id,
                origin_port_id=port_id,
                dest_port_id=port_id,
                status="in_transit",
                mode="sea",
                eta=today + timedelta(days=14 + i * 7),
                value=Decimal(str(150000 * (i + 1))),
            )
            .on_conflict_do_nothing()
        )


async def _seed_scenario_rows(scenario: Scenario) -> uuid.UUID:
    """Insert the scenario's signal + disruption. Returns disruption_id.

    For the typhoon scenario we call ``seed_typhoon`` (self-contained ground-truth).
    All other scenarios get ``_seed_minimal_chain`` so tool-loop queries surface
    real shipment IDs instead of the model fabricating them.
    """
    sig = scenario.signal
    dis = scenario.disruption

    async with session() as s:
        if scenario.id == "typhoon_kaia":
            typhoon = await seed_typhoon(s)
            await s.commit()
            return typhoon.disruption_id

        await _seed_minimal_chain(s, scenario)

        signal_id = uuid.uuid4()
        disruption_id = uuid.uuid4()
        dedupe_hash = f"prime::{scenario.id}::{signal_id.hex}"

        s.add(
            Signal(
                id=signal_id,
                source_category=sig.source_category,
                source_name=sig.source_name,
                title=sig.title,
                summary=sig.summary,
                region=sig.region,
                lat=Decimal(str(sig.lat)),
                lng=Decimal(str(sig.lng)),
                radius_km=Decimal(str(sig.radius_km)),
                source_urls=sig.source_urls,
                confidence=Decimal(str(sig.confidence)),
                raw_payload={"prime_cache": True},
                dedupe_hash=dedupe_hash,
                promoted_to_disruption_id=disruption_id,
            )
        )
        s.add(
            Disruption(
                id=disruption_id,
                title=dis.title,
                summary=dis.summary,
                category=dis.category,
                severity=dis.severity,
                region=dis.region,
                lat=Decimal(str(dis.lat)),
                lng=Decimal(str(dis.lng)),
                radius_km=Decimal(str(dis.radius_km)),
                source_signal_ids=[signal_id],
                confidence=Decimal(str(dis.confidence)),
                status=dis.status,
            )
        )
        await s.commit()
        return disruption_id


# ---------------------------------------------------------------------------
# Prime one scenario end-to-end
# ---------------------------------------------------------------------------


async def _prime_scenario(scenario: Scenario, llm: LLMClient, bus: EventBus) -> _PrimeResult:
    result = _PrimeResult(
        scenario=scenario.id,
        classify_ok=False,
        impact_ok=False,
        options_ok=False,
        drafts_ok=0,
    )

    # 1. Classify — one Gemini structured call.
    try:
        await classify_raw_signal(_scenario_raw_hit(scenario), llm)
        result.classify_ok = True
    except Exception as err:  # noqa: BLE001 — best-effort per scenario
        result.error = f"classify: {err}"
        return result

    # 2. Seed DB rows for Analyst/Strategist to consume.
    try:
        disruption_id = await _seed_scenario_rows(scenario)
    except Exception as err:  # noqa: BLE001
        result.error = f"seed: {err}"
        return result

    # 3. Impact — full tool loop. If the DB baseline doesn't have matching
    # shipments, the tools return empty rows but the cache still fills.
    try:
        impact_id = await build_impact_report(disruption_id=disruption_id, llm=llm, bus=bus)
        result.impact_ok = True
    except LLMValidationError as err:
        result.error = f"impact: {err}"
        return result
    except Exception as err:  # noqa: BLE001
        result.error = f"impact: {err}"
        return result

    # 4. Options — another tool loop.
    try:
        bundle, _trace = await generate_options(impact_report_id=impact_id, llm=llm)
        result.options_ok = True
    except Exception as err:  # noqa: BLE001
        result.error = f"options: {err}"
        return result

    # 5. Drafts — one structured call per option.
    for opt in bundle.options:
        try:
            await generate_drafts(
                opt,
                llm=llm,
                supplier_contact="supplier@example.com",
                customer_contact="customer@example.com",
                disruption_title=scenario.disruption.title,
                impact_exposure="0",
                affected_shipment_ids=[],
            )
            result.drafts_ok += 1
        except Exception as err:  # noqa: BLE001
            log.warning(
                "prime_cache.drafts_skipped",
                scenario=scenario.id,
                option=opt.option_type,
                error=str(err),
            )

    return result


# ---------------------------------------------------------------------------
# Freeze active → seed
# ---------------------------------------------------------------------------


def freeze_seeds() -> list[tuple[Path, Path]]:
    """Copy every active cache → its ``*.seed`` sibling. Returns list of (src, dst)."""
    copied: list[tuple[Path, Path]] = []
    for active, seed in (
        (_PROMPT_CACHE_ACTIVE, _PROMPT_CACHE_SEED),
        (_TAVILY_CACHE_ACTIVE, _TAVILY_CACHE_SEED),
    ):
        if not active.exists():
            log.warning("prime_cache.freeze.missing", active=str(active))
            continue
        seed.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(active, seed)
        copied.append((active, seed))
        log.info("prime_cache.freeze.ok", active=str(active), seed=str(seed))
    return copied


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------


async def _run(scenarios: list[str], freeze: bool) -> int:
    if os.environ.get("DEMO_OFFLINE_CACHE", "").lower() in ("1", "true", "yes", "on"):
        print(
            "error: DEMO_OFFLINE_CACHE=true — priming requires live API access. "
            "Unset the flag and retry.",
            file=sys.stderr,
        )
        return 2

    if not os.environ.get("GEMINI_API_KEY"):
        print(
            "error: GEMINI_API_KEY is not set. Export it before running.",
            file=sys.stderr,
        )
        return 2

    _PROMPT_CACHE_ACTIVE.parent.mkdir(parents=True, exist_ok=True)
    llm = LLMClient(cache_path=_PROMPT_CACHE_ACTIVE, model="flash")

    # Free-tier gemini-2.5-flash is capped at 5 req/min. Each scenario bursts
    # ~10-15 Gemini calls (classify + tool-loop + options + drafts), so we pace
    # between scenarios to let the window drain.
    inter_scenario_delay = float(os.environ.get("PRIME_INTER_SCENARIO_DELAY", "30"))

    bus = EventBus(DBSettings().database_url)
    await bus.start()
    try:
        results: list[_PrimeResult] = []
        for idx, sid in enumerate(scenarios):
            if idx > 0 and inter_scenario_delay > 0:
                log.info("prime_cache.pacing", sleep_s=inter_scenario_delay)
                await asyncio.sleep(inter_scenario_delay)
            scenario = SCENARIOS[sid]  # type: ignore[assignment]
            log.info("prime_cache.scenario.start", scenario=sid)
            try:
                res = await _prime_scenario(scenario, llm, bus)  # type: ignore[arg-type]
            except Exception as err:  # noqa: BLE001
                res = _PrimeResult(
                    scenario=sid,
                    classify_ok=False,
                    impact_ok=False,
                    options_ok=False,
                    drafts_ok=0,
                    error=str(err),
                )
            log.info(
                "prime_cache.scenario.done",
                scenario=sid,
                classify=res.classify_ok,
                impact=res.impact_ok,
                options=res.options_ok,
                drafts=res.drafts_ok,
                error=res.error,
            )
            results.append(res)
    finally:
        await bus.stop()

    print(json.dumps([r.__dict__ for r in results], indent=2))

    if freeze:
        freeze_seeds()

    return 0 if all(r.classify_ok for r in results) else 1


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="prime_cache",
        description="Populate offline LLM + Tavily caches for all demo scenarios.",
    )
    p.add_argument(
        "--scenario",
        action="append",
        choices=sorted(SCENARIOS.keys()),
        help="Prime only this scenario. Repeat the flag for multiples; omit for all.",
    )
    p.add_argument(
        "--no-freeze",
        action="store_true",
        help="Skip copying active caches → .seed files after priming.",
    )
    p.add_argument(
        "--freeze",
        action="store_true",
        help="Only freeze existing active caches; do not run any priming.",
    )
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    ns = _parse_args(argv)
    if ns.freeze:
        freeze_seeds()
        return 0
    scenarios = ns.scenario or sorted(SCENARIOS.keys())
    return asyncio.run(_run(scenarios, freeze=not ns.no_freeze))


if __name__ == "__main__":
    sys.exit(main())
