# Plan C — API, Demo & Glue

> **Owner:** Teammate C.
> **Read first:** `docs/superpowers/plans/2026-04-18-parallel-coordination.md`.
> **Task specs (source of truth):** `docs/superpowers/plans/2026-04-18-suppl-ai-implementation.md`.

**Charter:** The contract layer between agents and dashboard. Define Pydantic schemas everyone consumes. Build FastAPI routes + WebSocket relay. Ship SQL safety validator and the analyst query-tool library. Author the 5 demo scenarios and Playwright E2E that prove the system works end-to-end. Own pitch deck + README.

## Tasks owned

| # | Task | Source | Strict TDD? | Approx effort |
|---|---|---|---|---|
| C.1 | **2.1** Pydantic schemas (signal, disruption, impact, mitigation, approval) | master | **partial** — mypy strict on every schema | 2h |
| C.2 | **2.2** SQL defense-in-depth validator | master | **yes** — parametrized test suite | 1.5h |
| C.3 | **2.6** Analyst query tools library | master | **yes** — per-tool fixture tests | 3h |
| C.4 | **3.1** WebSocket manager + LISTEN relay | master | **yes** — test: NOTIFY → WS client message within 500ms | 2h |
| C.5 | **3.2** Route stubs (signals, disruptions, mitigations, analytics, activity, dev.simulate) | master | milestone | 3h |
| C.6 | **3.3** OpenAPI TS regen + commit | master | trivial | 0.25h |
| C.7 | **9.1** Atomic approval transaction | master | **yes** — test: mid-transaction failure → rollback | 2h |
| C.8 | **11.1** 5 scenario fixtures | master | milestone | 2h |
| C.9 | **11.2** Playwright E2E suite (5 scenarios × full pipeline) | master | milestone | 3h |
| C.10 | **11.3** Simulate button wiring + scenarios endpoint | master | milestone | 0.5h |
| C.11 | **12.6, 12.7** Pitch deck + README + architecture doc | master | milestone | 4h |

**Total est:** ~23h focused.

## What you SHIP to others — in priority order

1. **C.1 Pydantic schemas** — **SHIP FIRST, WITHIN 2 HOURS.** Plan A's Analyst and Strategist agents consume `ImpactReport`, `MitigationOption`, `DraftCommunication`, `SignalClassification`. Plan B generates TS types from your FastAPI OpenAPI (which references these).
2. **C.2 SQL guard** — Plan A Task 6.1 uses it when storing synthesized `sql_executed`.
3. **C.3 Analyst query tools** — Plan A Task 6.1 feeds these into the Gemini tool-calling loop. Define them as Pydantic-arg functions with `{rows, synthesized_sql, row_count}` return shape.
4. **C.4 + C.5 API + WS** — Plan B's entire UI consumes this. Without a live API, B stubs endpoints.
5. **C.6 Regenerated `web/types/api.ts`** — commit after every route add. Pre-commit hook enforces it.
6. **C.7 Atomic approval endpoint** — Plan B Task 9.2 calls it.
7. **C.8 + C.10 Simulate scenarios** — Plan B Task 11.3 (menu) + the actual demo rely on these. Plan A must cascade correctly through them.

## What you CONSUME from others

- **Event bus impl** (`backend/db/bus.py`) — from Plan A Task 2.3. You use it in C.4 to listen on the 5 channels and relay to WebSocket clients.
- **Agent writes to DB** — your routes read these (signals, disruptions, etc.).
- **Running agents** — C.9's Playwright tests start A's agents as subprocesses.

## Sequencing

```
C.1 schemas  →  C.2 SQL guard  →  C.3 analyst tools   (ALL SHIP WITHIN FIRST 4-6 HOURS — unblocks A)
                                       ↓
                                  C.4 WS relay (needs A.1 bus)
                                       ↓
                                  C.5 route stubs  →  C.6 openapi regen  →  (B can start consuming)
                                       ↓
                                  C.7 approval transaction
                                       ↓
                                  C.8 scenarios  →  C.10 simulate wiring  (needs A.4/A.5/A.6 done)
                                       ↓
                                  C.9 Playwright e2e (runs full stack)
                                       ↓
                                  C.11 pitch + README + architecture
```

## Quick start

```bash
git checkout main
git pull
git checkout -b c/pydantic-schemas
# Implement Task 2.1 per master plan — one file per entity under backend/schemas/
uv run mypy --strict backend/schemas   # must be clean
git push -u origin c/pydantic-schemas
# Open PR to main AND ping A + B that schemas are ready.
```

## Safety-critical tests (must be green before merge)

- **SQL guard (C.2)** — parametrized suite in master plan Task 2.2 Step 1 (14 cases: 4 accept, 10 reject including comment-injection and multi-statement). 100% pass required.
- **WS relay (C.4)** — `test_notify_roundtrip_to_ws_client` within 500ms.
- **Approval atomicity (C.7)** — `test_approval_rollback_on_mid_transaction_failure`. Monkey-patch `WriteApprovalAudit` to raise; assert shipments still `in_transit`, no `approvals` row exists.
- **Playwright E2E (C.9)** — 5/5 scenarios green, 5 consecutive runs, no flakes.

## Demo scenarios spec (frozen — do NOT rename)

Each scenario is a pure-Python module at `backend/scripts/scenarios/<name>.py` with a canned Tavily/Open-Meteo payload and expected-shape assertions for e2e tests:

| Scenario | Category | Expected affected shipments | Expected exposure | Dominant mitigation type |
|---|---|---|---|---|
| `typhoon_kaia` | weather | ~14 electronics around Shenzhen | ~$2.3M | reroute via HCM |
| `busan_strike` | logistics | ~8 apparel + food | ~$1.4M | reroute to Kaohsiung |
| `cbam_tariff` | policy | ~5 industrial SKUs | ~$500K | switch to compliant supplier |
| `luxshare_fire` | industrial | ~6 electronics SKUs | ~$900K | activate backup supplier |
| `redsea_advisory` | logistics | 20+ shipments | ~$3.1M | accept delays vs expedite air |

Assertions in e2e: count within ±2, exposure within ±10% of expected.

## Definition of done

- [ ] All Pydantic schemas under `backend/schemas/` pass mypy --strict.
- [ ] SQL guard: all 14 test cases green; no false rejects on curated real SELECTs.
- [ ] Analyst tools: every tool has a fixture test verifying rows + `synthesized_sql` string + `row_count`.
- [ ] FastAPI routes return typed data; `/openapi.json` valid; TS codegen clean.
- [ ] WebSocket relays all 5 channels to connected clients within 500ms.
- [ ] Atomic approval: shipment status flip + audit row write in one transaction; rollback on any failure.
- [ ] All 5 scenarios cascade to ≥2 mitigations in Playwright ≤60s, 5 consecutive runs.
- [ ] 2-minute demo script + pitch PDF in `docs/`.
- [ ] README + `docs/architecture.md` with Mermaid diagram, sponsor sections (Dedalus, OpenClaw, Gemini, Tavily).

## Escalation signals

- Gemini schema drift causes C.1 → C.3 rework → pause and ping A (who shares same SDK)
- Playwright flaky → do NOT add `waitForTimeout(5000)` band-aid; isolate the real race and fix it
- Atomic approval intermittently fails under load → check SQLAlchemy session scoping, NOT `try: commit except: rollback` hand-rolled (use `async with session.begin():`)
- Demo scenario assertion fails — coordinate with Plan A: is the scenario's canned payload producing expected Analyst output? Tune scenario data, not the assertion thresholds.

## Pitch-deck discipline (Task 12.6)

2 minutes, 5 slides max:

1. **The problem** (20s) — Maya's hour of frantic tab-switching during a typhoon
2. **The system** (30s) — 3 agents, war-room UI, one-click approve
3. **Live demo** (60s) — Simulate Typhoon Kaia → disruption → impact → mitigations → approve → audit
4. **Why this is different** (20s) — not a chatbot; OpenClaw mutates real DB; Gemini function-calling eliminates SQL injection
5. **Sponsor tie-ins** (10s) — 3 Dedalus VMs live, OpenClaw in every mutation, Gemini per agent, Tavily queries documented

Script lives in `docs/demo-script.md`. Rehearse 3× from fresh VM boot on Sunday morning.
