# Plan A — Agents & Infrastructure

> **Owner:** Teammate A.
> **Read first:** `docs/superpowers/plans/2026-04-18-parallel-coordination.md`.
> **Task specs (source of truth):** `docs/superpowers/plans/2026-04-18-suppl-ai-implementation.md`.

**Charter:** Three agent processes running on three Dedalus VMs, communicating only through Postgres. Scout monitors five signal sources, Analyst produces impact reports via Gemini function-calling, Strategist drafts mitigations through OpenClaw. Swarm discipline: no RPC between agents.

## Tasks owned

| # | Task | Source | Strict TDD? | Approx effort |
|---|---|---|---|---|
| A.1 | **2.3** Event bus (LISTEN/NOTIFY + reconnect) | master plan | **yes** — test reconnect on dropped conn | 2h |
| A.2 | **2.4** LLM client (Gemini structured + tool-calling + cache) | master | **yes** — test cache hit, retry, schema validation | 3h |
| A.3 | **2.5** Agent base class (lifecycle + checkpoint + health) | master | **yes** — test checkpoint restore | 2h |
| A.4 | **5.1–5.12** Scout agent (dedupe, severity, classify, fusion, 5 sources, main) | master | **partial** — strict for dedupe + severity; light for sources | 8h |
| A.5 | **6.1–6.3** Analyst agent (tool loop + impact processor, fallback, main) | master | **yes** — test tool loop produces valid report | 5h |
| A.6 | **7.1–7.4** Strategist agent (options, drafts, OpenClaw, main) | master | **light** | 5h |
| A.7 | **12.1, 12.3, 12.4** Dedalus VMs + systemd units + offline cache priming + restart persistence | master | milestone | 3h |

**Total est:** ~28h focused. Parallelizable: nothing (each depends on the prior).

## What you SHIP to others

- **Event bus implementation** (`backend/db/bus.py`) — Plan C's WebSocket relay consumes this for `/ws/updates`.
- **Agent base class** (`backend/agents/base.py`) — nobody consumes directly, but it's part of the mypy-strict gate.
- **`NOTIFY` events on the 5 channels** — Plan C's WebSocket relay forwards these to the frontend. Payload format is frozen in the coordination doc.
- **Agent writes to DB** — Plan B's UI reads via Plan C's API; you don't talk to UI directly.

## What you CONSUME from others

- **`backend/schemas/*.py`** (Pydantic models) — from Plan C (Task 2.1). Blocks A.5 (Analyst needs `ImpactReport` schema) and A.6 (Strategist needs `MitigationOption` + `DraftCommunication` schemas).
- **SQL defense-in-depth validator** (`backend/api/validators/sql_guard.py`) — from Plan C (Task 2.2). A.5 uses it when storing `impact_reports.sql_executed`.
- **Analyst query tools** (`backend/llm/tools/analyst_tools.py`) — from Plan C (Task 2.6). A.5 feeds these into the Gemini tool-calling loop.
- **OpenAPI spec** — indirectly, via Plan C ensuring FastAPI routes compile.

## Sequencing

```
A.1 Event bus  → A.2 LLM client  → A.3 Agent base
                                       ↓
     (wait for C.1 schemas + C.2 SQL guard + C.5 tools) → A.4 Scout → A.5 Analyst → A.6 Strategist → A.7 Infra
```

**Start immediately with A.1 + A.2 + A.3** — those don't need anything from C/B.

## Quick start

```bash
git checkout main
git pull
git checkout -b a/event-bus
# Implement Task 2.3 per master plan's spec (including TDD test file).
uv sync --all-groups
uv run pytest backend/db/tests/test_bus.py -v   # should fail first
# Implement
uv run pytest backend/db/tests/test_bus.py -v   # should pass
git push -u origin a/event-bus
# Open PR to main.
```

## Safety-critical tests (must be green before merge)

- **Event bus:** `test_publish_subscribe_roundtrip`, `test_survives_connection_drop` — per Task 2.3.
- **LLM client:** `test_structured_returns_model`, `test_structured_retries_once_on_validation`, `test_offline_cache_short_circuits` — per Task 2.4.
- **Agent base:** `test_checkpoint_survives_restart` — per Task 2.5.
- **Scout dedupe:** two identical `(region, category, keywords)` within 72h → second rejected. Third 73h later accepted.
- **Scout severity:** 8 parametrized cases covering each rubric branch.

## Definition of done

- [ ] A.1–A.3 all merged; mypy strict on `backend/db/bus.py`, `backend/llm/client.py`, `backend/agents/base.py`.
- [ ] All 5 Scout sources produce classified+deduped signals locally with offline cache.
- [ ] Typhoon scenario: `NOTIFY new_disruption` triggers Analyst → impact report within 30s.
- [ ] Typhoon impact triggers Strategist → ≥2 mitigations + 3 drafts per mitigation within 45s.
- [ ] All 3 agents run as systemd services on Dedalus VMs; `systemctl stop + start` resumes from checkpoint without duplicate signals.
- [ ] `grep -r "smtplib" backend/` returns empty (demo-day gate).
- [ ] Offline cache primed for all 5 demo scenarios.

## Known blockers

- **OpenClaw package** — not on PyPI as `openclaw`. See `docs/runbook.md`. Task A.6 is blocked on Eragon providing install path. If blocked at hour 24, fall back to plain Python action layer wrapping the same DB mutations — still demonstrates depth-of-action for the Eragon rubric (see PRD §13.2).
- **Gemini 2.x function-calling** — newer SDK. If `google-genai>=0.3` has a different API than the plan assumes, adjust `LLMClient.with_tools` and document. Don't fight it.

## Escalation signals

Stop and raise if you hit any of these — don't silently work around:
- Tavily rate limit → swap to offline cache, do NOT change source cadence to work around it
- Gemini consistently returns invalid JSON → check `response_schema` binding; do not disable retry; ask for help
- PG LISTEN not receiving payloads → check reconnect loop; ensure `publish()` uses one-shot conn per coordination doc
- OpenClaw available but API differs from `annyzhou/openclaw-ddls` reference — ping Teammate C + check Eragon docs
