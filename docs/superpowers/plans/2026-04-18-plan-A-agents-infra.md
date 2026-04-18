# Plan A — Agents & Infrastructure

> **Owner:** Teammate A.
> **Read first:** `docs/superpowers/plans/2026-04-18-parallel-coordination.md`.
> **Task specs (source of truth):** `docs/superpowers/plans/2026-04-18-suppl-ai-implementation.md`.

**Charter:** Three agent processes running on three Dedalus VMs, communicating only through Postgres. Scout monitors five signal sources, Analyst produces impact reports via Gemini function-calling, Strategist drafts mitigations through OpenClaw. Swarm discipline: no RPC between agents.

## Tasks owned

| # | Task | Source | Status | Merged at |
|---|---|---|---|---|
| A.1 | **2.3** Event bus (LISTEN/NOTIFY + reconnect) | master plan | ✅ done | f288bfa |
| A.2 | **2.4** LLM client (Gemini structured + tool-calling + cache) | master | ✅ done | f921e31 |
| A.3 | **2.5** Agent base class (lifecycle + checkpoint + health) | master | ✅ done | b02bcad |
| A.4 | **5.1–5.12** Scout agent (dedupe, severity, classify, fusion, 5 sources, main) | master | ✅ done | d1c49bf (main wiring), 9f36bf8 (sources), b63b7a5 (weather), plus processor commits |
| A.5 | **6.1–6.3** Analyst agent (tool loop + impact processor, fallback, main) | master | ✅ done | 886f425, bee27d9, 85ee6a9 |
| A.6 | **7.1–7.4** Strategist agent (options, drafts, OpenClaw actions, main) | master | ✅ done | 9d87738 |
| A.7 | **12.1, 12.3, 12.4** Dedalus VMs + systemd + offline cache priming + restart persistence | master | ✅ done | cf19e06 (systemd + smoke), bbf62c2 (A.7.a infra), 1d58be9 (A.7.b offline cache) |

## A.7 breakdown (shipped)

A.7 split cleanly into two disjoint tracks. Partial progress landed at cf19e06 (systemd units + smoke). Both follow-on tracks merged into `main`.

### A.7.a — Dedalus infra + restart persistence (Tasks 12.1 + 12.3) ✅

**Branch:** `a/infra-dedalus` (merged)
**Merge commit:** `bbf62c2`

- [x] Provisioner shipped: `infra/provision.py` idempotently creates 4 Machines (`scout-vm`, `analyst-vm`, `strategist-vm`, `db-vm`), handles 409 reuse + 503 `NoReadyHosts`, writes `infra/machines.json`.
- [x] Systemd units under `infra/systemd/` verified (cf19e06) and consumed by `infra/scripts/deploy.sh`.
- [x] `scripts/smoke.py --inventory infra/machines.json` hits `/health` on each agent VM + API.
- [x] `scripts/restart_persistence_test.py` — `systemctl restart supplai-<agent>` → asserts `state.json` sha256 identical + zero duplicate `content_hash` in 30s steady-state window.
- [x] `README.md` "Three VMs running live" section added (lines 218–259) with three-command bring-up + screenshot placeholder.

### A.7.b — Offline cache priming + demo scenario fixtures (Task 12.4) ✅

**Branch:** `a/offline-cache` (merged)
**Merge commit:** `1d58be9`

- [x] 5 demo scenarios primed via `scripts/prime_cache.py` (typhoon_kaia / busan_strike / cbam_tariff / luxshare_fire / redsea_advisory). Seeds FK-valid ports / suppliers / SKUs / customers / POs / shipments per non-typhoon scenario.
- [x] Frozen seeds in-tree: `backend/llm/prompt_cache.sqlite.seed` (25 entries = 5 scenarios × classify+impact+options+2 drafts) + `backend/llm/tavily_cache.sqlite.seed` (8 real Tavily responses).
- [x] `scripts/bootstrap_cache.py` + `backend/llm/cache_loader.py` wired into all 3 systemd units via `ExecStartPre`; no-op when `DEMO_OFFLINE_CACHE` off or seed already loaded.
- [x] `backend/tests/test_offline_mode.py` — 4 tests (classify / analyst fallback / drafts / full pipeline) with external APIs stubbed to raise.
- [x] `test_analyst_main` NOTIFY flake fixed: `asyncio.Event`-driven watcher replaced the polled loop (root cause = LISTEN/NOTIFY race on the polled-query path).
- [x] `backend/tests/test_no_smtp.py` — CI guard fails if `smtplib` / `sendmail` / `smtp` imports sneak into `backend/`. Currently empty.
- [x] Content-stable cache keys across runs: analyst/strategist hash `(category, centroid, radius, title)` + drafts use sha256 of option description (not `hash()`, which is `PYTHONHASHSEED`-randomized).
- [x] `LLMClient.with_tools` now honors `cache_key` (silently ignored before) — tool loops short-circuit offline.

## Parallel execution (historical)

Both A.7.a and A.7.b ran in parallel. Zero file overlap. A.7.a merged first (bbf62c2, 15:19 EDT), A.7.b followed (1d58be9, 16:35 EDT) with a trivial rebase.

## What has been SHIPPED to others

- **Event bus** (`backend/db/bus.py`) → Plan C WebSocket relay consumes it at `/ws/updates`.
- **Agent base class** (`backend/agents/base.py`) — mypy-strict.
- **`NOTIFY` events on 5 channels** → Plan C relay forwards to frontend.
- **Agent writes to DB** → Plan B UI reads via Plan C's API.
- **Scout/Analyst/Strategist main processes** — each runs as `uv run python -m backend.agents.<name>.main`.

## Definition of done

- [x] A.1–A.6 all merged. mypy strict clean on shared modules.
- [x] All 5 Scout sources produce classified + deduped signals locally with offline cache.
- [x] Typhoon scenario end-to-end runs via `DEMO_OFFLINE_CACHE=true` (covered by `backend/tests/test_offline_mode.py::test_full_pipeline_offline`).
- [x] `systemctl stop + start` resumes from checkpoint without duplicate signals — `scripts/restart_persistence_test.py` gates this (live-cloud gate; needs `DEDALUS_API_KEY` + `infra/machines.json`).
- [x] `grep -r "smtplib\|sendmail\|smtp" backend/` returns only `backend/tests/test_no_smtp.py` (the guard itself).
- [x] Offline cache seeded for all 5 scenarios (prompt + Tavily seeds shipped in `backend/llm/`).
- [x] Analyst NOTIFY flake fixed — `test_analyst_main` now uses an `asyncio.Event`-driven watcher (1d58be9).

## Resolved blockers

- **OpenClaw package** — turned out NOT to be a PyPI package. OpenClaw is a Node.js self-hosted gateway running on `strategist-vm`. Strategist talks to it via HTTP and/or uses a direct action layer under `backend/agents/strategist/actions/` (see 9d87738). Eragon rubric still satisfied via the action layer depth. See `docs/runbook.md` for the corrected install path once A.7.a runs the bootstrap.
- **Gemini 2.x function-calling** — `google-genai>=0.3` SDK used, adjusted in `backend/llm/client.py`.

## Escalation signals (live-cloud gates only)

- Dedalus VM provisioning hits `NoReadyHosts` — `infra/provision.py` surfaces this with an actionable error; free slots or shrink memory request and rerun (idempotent).
- `state.json` lost across restart — check `StateDirectory=supplai` in `infra/systemd/supplai-*.service`.
- Offline seed file >100 MB — prompt seed is 76K, Tavily seed is 144K; well under threshold. Re-check before regenerating.

## Demo-day runbook

```bash
# Provision + deploy + verify (A.7.a)
export DEDALUS_API_KEY=...
uv run python infra/provision.py                               # writes infra/machines.json
./infra/scripts/deploy.sh scout-vm scout
./infra/scripts/deploy.sh analyst-vm analyst
./infra/scripts/deploy.sh strategist-vm strategist
uv run python scripts/smoke.py --inventory infra/machines.json

# Restart persistence gate (Task 12.3)
uv run python scripts/restart_persistence_test.py --inventory infra/machines.json

# Offline cache verification (A.7.b)
DEMO_OFFLINE_CACHE=true uv run pytest backend/tests/test_offline_mode.py -v
```
