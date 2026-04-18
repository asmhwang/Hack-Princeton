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
| A.7 | **12.1, 12.3, 12.4** Dedalus VMs + systemd + offline cache priming + restart persistence | master | 🚧 in progress — see below |

## A.7 breakdown (remaining work)

A.7 splits cleanly into two disjoint tracks. Partial progress already landed at cf19e06 (systemd units + smoke).

### A.7.a — Dedalus infra + restart persistence (Tasks 12.1 + 12.3)

**Branch:** `a/infra-dedalus`
**Worktree:** `../hp-infra-dedalus`
**Files owned:** `infra/**`, `scripts/smoke.py`, `scripts/restart_persistence_test.py`
**Est:** ~1.5h

- [ ] Provision 4 Machines via Dedalus SDK: `scout-vm`, `analyst-vm`, `strategist-vm`, `db-vm`. Default tier.
- [ ] Verify systemd units under `infra/` (already landed at cf19e06) — rerun + document.
- [ ] `scripts/smoke.py` hits `/health` on each agent VM + `/health` on API.
- [ ] `scripts/restart_persistence_test.py` — `systemctl stop supplai-<agent>` during demo run → `systemctl start` → assert no duplicate signals, cursors resumed, `state.json` matches.
- [ ] Update `README.md` with "three VMs running live" screenshot section.

### A.7.b — Offline cache priming + demo scenario fixtures (Task 12.4)

**Branch:** `a/offline-cache`
**Worktree:** `../hp-offline-cache`
**Files owned:** `scripts/prime_cache.py`, `backend/llm/*.sqlite.seed`, `scripts/simulate.py`, `backend/tests/test_offline_mode.py`
**Est:** ~1.5h

- [ ] For each of 5 demo scenarios (typhoon / strike / CBAM / Red Sea / earthquake per PRD §15.1), run end-to-end once with live Gemini + live Tavily. Cache auto-populates `backend/llm/prompt_cache.sqlite`.
- [ ] Freeze to seed files: `backend/llm/prompt_cache.sqlite.seed` + `backend/llm/tavily_cache.sqlite.seed` (may have per-source variants).
- [ ] VM bootstrap loads seeds if `DEMO_OFFLINE_CACHE=true` (belongs in `infra/bootstrap_*.sh`).
- [ ] `backend/tests/test_offline_mode.py` — asserts the typhoon scenario runs end-to-end through Scout → Analyst → Strategist with all external APIs stubbed to raise, using only seeded cache.
- [ ] **Side task:** investigate + fix `test_analyst_main::test_notify_new_disruption_triggers_impact_report` flake (SQLAlchemy NoResultFound — LISTEN/NOTIFY race). Root-cause before patching.
- [ ] `grep -r "smtplib\|sendmail\|smtp" backend/` — assert empty. Add a pytest collection hook or CI step that fails if any SMTP import sneaks back.

## Parallel execution

Both A.7.a and A.7.b run in parallel. Zero file overlap. Merge order: either first, the other follows with a rebase (trivial).

## What has been SHIPPED to others

- **Event bus** (`backend/db/bus.py`) → Plan C WebSocket relay consumes it at `/ws/updates`.
- **Agent base class** (`backend/agents/base.py`) — mypy-strict.
- **`NOTIFY` events on 5 channels** → Plan C relay forwards to frontend.
- **Agent writes to DB** → Plan B UI reads via Plan C's API.
- **Scout/Analyst/Strategist main processes** — each runs as `uv run python -m backend.agents.<name>.main`.

## Definition of done

- [x] A.1–A.6 all merged. mypy strict clean on shared modules.
- [x] All 5 Scout sources produce classified + deduped signals locally with offline cache.
- [ ] Typhoon scenario end-to-end runs on Dedalus VMs with `DEMO_OFFLINE_CACHE=true`.
- [ ] `systemctl stop + start` resumes from checkpoint without duplicate signals (A.7.a test).
- [ ] `grep -r "smtplib" backend/` empty (A.7.b gate).
- [ ] Offline cache seeded for all 5 scenarios (A.7.b).
- [ ] Analyst NOTIFY flake fixed or root-caused + skipped with issue reference (A.7.b).

## Resolved blockers

- **OpenClaw package** — turned out NOT to be a PyPI package. OpenClaw is a Node.js self-hosted gateway running on `strategist-vm`. Strategist talks to it via HTTP and/or uses a direct action layer under `backend/agents/strategist/actions/` (see 9d87738). Eragon rubric still satisfied via the action layer depth. See `docs/runbook.md` for the corrected install path once A.7.a runs the bootstrap.
- **Gemini 2.x function-calling** — `google-genai>=0.3` SDK used, adjusted in `backend/llm/client.py`.

## Escalation signals (still live for A.7)

- Dedalus VM provisioning hits `NoReadyHosts` — delete orphans to free slots or shrink memory request.
- `state.json` lost across restart — check `StateDirectory=supplai` in systemd unit.
- Offline seed file >100 MB — move to git-lfs or prune low-value cache entries.

## Quick start for remaining tracks

```bash
# A.7.a
cd ../hp-infra-dedalus
uv sync --all-groups
# implement, test with DEDALUS_API_KEY in .env.local
git push -u origin a/infra-dedalus
# open PR

# A.7.b
cd ../hp-offline-cache
uv sync --all-groups
# run live scenarios once, freeze seeds
git push -u origin a/offline-cache
# open PR
```
