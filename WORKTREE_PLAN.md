# Worktree 3 — `a/agent-base-infra`

> **Parent plan:** `docs/superpowers/plans/2026-04-18-plan-A-agents-infra.md` (Tasks A.3 + A.7)
> **Master task specs:** `docs/superpowers/plans/2026-04-18-suppl-ai-implementation.md`
>   - Task 2.5 Agent base class (lines 1358–1438)
>   - Task 12.1 Dedalus VMs + systemd units (line 2034)
>   - Task 12.3 Agent restart persistence test (line 2048)
>   - Task 12.4 Offline cache priming (line 2055)
> **Coordination:** `docs/superpowers/plans/2026-04-18-parallel-coordination.md`
> **Branch:** `a/agent-base-infra` → PR into `main` (rebased onto `3ebb01d`)
> **Est effort:** 2h base + 3h infra = ~5h
> **Upstream state after 3ebb01d:**
> - `backend/db/bus.py` (WT1) merged — import `EventBus` directly, **no stub needed**.
> - `backend/llm/client.py` + `backend/llm/prompt_cache.py` (WT2) merged — real `LLMClient` available (AgentBase doesn't use it directly; subclasses do).
> - `backend/llm/tools/` (Plan C Task 2.6) merged — bonus, unblocks future Analyst worktree.
> - `backend/schemas/*` + `backend/api/validators/sql_guard.py` merged — schema-agnostic base class, no impact here.

## Charter

Two responsibilities fused because both cut across all three agents:

1. **`AgentBase` class** — the lifecycle contract every agent (Scout/Analyst/Strategist) subclasses. Handles: `EventBus` start/stop, channel subscription, checkpoint load/save (`state.json`), health HTTP endpoint, structlog trace setup.

2. **Dedalus VM infra** — `systemd` unit files per agent, deploy script, offline-cache priming loader, `scripts/smoke.py` health check. The judging requirement "restart resumes from checkpoint without duplicate signals" is validated here.

WT3 assumes WT1 (bus) and WT2 (llm client) interfaces. It can stub-import them until those PRs merge. After merge → rebase and run integration test.

## Deliverables

| # | File | Type | Purpose |
|---|---|---|---|
| 1 | `backend/agents/__init__.py` | new | package marker |
| 2 | `backend/agents/base.py` | new | `AgentBase` — lifecycle, LISTEN, checkpoint, health |
| 3 | `backend/tests/test_agent_base.py` | new | TDD: `test_checkpoint_survives_restart` + trivial subclass counter |
| 4 | `infra/systemd/supplai-scout.service` | new | scout unit, `Restart=on-failure`, `StateDirectory=supplai` |
| 5 | `infra/systemd/supplai-analyst.service` | new | analyst unit, same pattern |
| 6 | `infra/systemd/supplai-strategist.service` | new | strategist unit, same pattern |
| 7 | `infra/systemd/README.md` | new | deploy steps per Dedalus VM |
| 8 | `infra/scripts/deploy.sh` | new | rsync code, install unit, `systemctl daemon-reload` + `enable` + `start` |
| 9 | `scripts/smoke.py` | new | hits `/health` on each VM + API VM, prints table, exits non-zero on failure |
| 10 | `backend/llm/cache_loader.py` | new | reads `backend/llm/*.sqlite.seed` → copies into active cache path at boot when `DEMO_OFFLINE_CACHE=true` |
| 11 | `backend/tests/test_cache_loader.py` | new | TDD: loader copies seed, skips if target exists, skips if env flag off |

## TDD sequence

```
# Phase A: AgentBase — EventBus already on main, no stubs needed
1. cd ../Hack-Princeton-agent-base-infra
2. Write backend/tests/test_agent_base.py per master plan §2.5 Step 1 (imports real EventBus)
3. uv run pytest backend/tests/test_agent_base.py -v        # fails (no base.py yet)
4. Implement backend/agents/base.py (verbatim skeleton from master plan §2.5 Step 3)
5. pytest → green (checkpoint survives restart + counter semantics)
6. uv run mypy --strict backend/agents/base.py
7. Commit: "feat(agents): base class with lifecycle, LISTEN, checkpoint, health endpoint"

# Phase B: Infra (parallelizable with Phase A after test file written)
8. Write infra/systemd/*.service + deploy.sh + smoke.py + cache_loader.py
9. Write backend/tests/test_cache_loader.py
10. Run tests; all green
11. Commit: "feat(infra): dedalus systemd units + smoke + offline cache loader"

# Phase C: Push
12. git fetch origin; git rebase origin/main             # absorb any teammate work
13. Re-run full pytest; mypy strict on backend/agents/base.py + backend/llm/cache_loader.py
14. git push -u origin a/agent-base-infra
15. gh pr create --base main --title "feat(agents): base + dedalus infra" --body "Closes A.3 + A.7"
```

## `AgentBase` public contract (freeze — Scout/Analyst/Strategist depend on this)

```python
from __future__ import annotations
import asyncio, json
from pathlib import Path
from typing import Any
import structlog
from backend.db.bus import EventBus
from backend.observability.logging import new_trace

log = structlog.get_logger()

class AgentBase:
    name: str = "agent"
    channels: list[str] = []
    state_path: Path = Path("/var/lib/supplai/state.json")
    health_port: int = 0  # subclass sets (scout=9101, analyst=9102, strategist=9103)

    def __init__(self, dsn: str) -> None: ...
    async def start(self) -> None: ...          # load state, start bus, subscribe, launch bg tasks, start health server
    async def stop(self) -> None: ...           # cancel bg tasks, stop bus, save state
    async def on_notify(self, channel: str, payload: str) -> None: ...  # subclass overrides
    def background_tasks(self) -> list: return []                       # subclass overrides

    # Subclass helpers (not to be overridden)
    async def checkpoint(self, key: str, value: Any) -> None: ...       # mutates self._state + flushes
    def checkpoint_get(self, key: str, default: Any = None) -> Any: ...
    def _load_state(self) -> dict: ...
    def _save_state(self) -> None: ...
```

**Required behaviour:**

- `new_trace()` called at start of every `_wrap(channel)` dispatcher → every notify handler gets a fresh `trace_id` in structlog context.
- Exceptions in `on_notify` **must** be caught + logged (`agent.handler_failed`), never propagate out of `_dispatch` — otherwise one bad payload crashes the listener.
- `state.json` is written atomically: write to `state.json.tmp` + `os.replace`. A crash mid-write must not corrupt state.
- Health endpoint: small `aiohttp` or `uvicorn` app on `127.0.0.1:<health_port>`, single route `GET /health` → `{"agent": name, "ok": true, "uptime_s": <int>, "last_notify": <iso ts | null>}`.
- `stop()` completes within 5s even if handlers are mid-flight (cancel + gather with `return_exceptions=True`).

## Systemd unit template

```ini
# infra/systemd/supplai-scout.service
[Unit]
Description=suppl.ai Scout agent
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=supplai
WorkingDirectory=/opt/supplai
Environment="PYTHONPATH=/opt/supplai"
EnvironmentFile=/etc/supplai/env
ExecStart=/usr/local/bin/uv run python -m backend.agents.scout.main
StateDirectory=supplai
Restart=on-failure
RestartSec=3
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

Analyst + Strategist identical modulo `Description` + `ExecStart` module path. `StateDirectory=supplai` → `/var/lib/supplai/` readable by the user for checkpoint writes.

## `smoke.py` contract

```python
# scripts/smoke.py
# CLI: uv run python scripts/smoke.py --scout <url> --analyst <url> --strategist <url> --api <url>
# Output: pretty table — name / url / status_code / ok flag.
# Exit 0 iff all four return {"ok": true}. Exit 1 otherwise.
# Used in Task 12.3 restart test + demo-day pre-flight.
```

## Cache loader (Task 12.4) contract

```python
# backend/llm/cache_loader.py
def prime_cache_if_offline(seed_dir: Path, target: Path) -> None:
    """At boot, if DEMO_OFFLINE_CACHE=true and <target> does not exist,
       copy <seed_dir>/prompt_cache.sqlite.seed -> <target>.
       Idempotent: never overwrites an existing cache DB.
       No-op if env flag off."""
```

- Seed files themselves (`*.sqlite.seed`) are produced in Task 12.4 post-integration; not committed here.
- Called from each agent `main.py` at startup (WT3 just provides the helper; agent `main.py`s are separate WTs).

## Test specifications

### `test_agent_base.py` (TDD, per master plan §2.5)

```python
# Minimal subclass: subscribes to 'test_agent_ch', increments counter['n'] on each payload.
class _Counter(AgentBase):
    name = "counter"
    channels = ["test_agent_ch"]
    async def on_notify(self, channel, payload):
        self._state["n"] = self._state.get("n", 0) + 1

async def test_checkpoint_survives_restart(postgresql_url, tmp_path, monkeypatch):
    monkeypatch.setattr(_Counter, "state_path", tmp_path / "state.json")
    a1 = _Counter(postgresql_url)
    await a1.start()
    bus = EventBus(postgresql_url); await bus.start()
    for _ in range(3): await bus.publish("test_agent_ch", "x")
    await asyncio.sleep(0.3)
    await a1.stop()
    # Restart
    a2 = _Counter(postgresql_url); await a2.start()
    assert a2._state["n"] == 3
    await a2.stop()
```

### `test_cache_loader.py`

```python
def test_copies_seed_when_offline_and_target_missing(tmp_path, monkeypatch):
    monkeypatch.setenv("DEMO_OFFLINE_CACHE", "true")
    seed = tmp_path / "seeds"; seed.mkdir()
    (seed / "prompt_cache.sqlite.seed").write_bytes(b"payload")
    target = tmp_path / "cache.sqlite"
    prime_cache_if_offline(seed, target)
    assert target.read_bytes() == b"payload"

def test_noop_when_env_flag_off(tmp_path, monkeypatch):
    monkeypatch.delenv("DEMO_OFFLINE_CACHE", raising=False)
    ...

def test_noop_when_target_exists(...):
    ...
```

## Ship/consume contracts

- **SHIPS**:
  - `AgentBase` → consumed by Scout (`backend/agents/scout/main.py` WT4 + future), Analyst, Strategist `main.py`.
  - `cache_loader.prime_cache_if_offline` → called from each agent `main.py` at startup.
  - `infra/systemd/*.service` + `infra/scripts/deploy.sh` → deploy automation; reviewers read these.
  - `scripts/smoke.py` → Task 12.3 restart-persistence test uses this.
- **CONSUMES**:
  - `EventBus` from `backend.db.bus` — shipped in `f288bfa`, import directly.
  - `LLMClient` from `backend.llm.client` — shipped in `f921e31`. AgentBase doesn't instantiate it; subclasses do.
  - `backend/observability/logging.new_trace` (already exists in foundation).

## Definition of done

- [ ] `uv run pytest backend/tests/test_agent_base.py backend/tests/test_cache_loader.py -v` green.
- [ ] `uv run mypy --strict backend/agents/base.py backend/llm/cache_loader.py` clean.
- [ ] `uv run ruff check backend/agents backend/llm/cache_loader.py scripts/smoke.py` clean.
- [ ] `infra/systemd/*.service` files valid: `systemd-analyze verify infra/systemd/supplai-scout.service` (run on any Linux box with systemd installed — at minimum manual review for required fields).
- [ ] `infra/scripts/deploy.sh` is executable (`chmod +x`) + self-documenting usage on `--help`.
- [ ] `scripts/smoke.py --help` works without live targets.
- [ ] PR description includes a sequence diagram of agent startup: `load_state → bus.start → subscribe(channels) → spawn bg tasks → health server up`.
- [ ] After WT1 merged: final rebase, re-run full pytest — green. Push.
- [ ] PR merged into `main` before WT4's Scout `main.py` is wired (future WT, not this one).

## Known gotchas

- **`state.json` atomic write on macOS vs Linux:** `os.replace` is atomic on both, but if dev on macOS and deploy to Linux, permission bits differ. Use explicit `chmod 0o600` on state file write (contains no secrets but future-proofs).
- **Signal handling:** Dedalus systemd sends `SIGTERM` on stop. asyncio doesn't auto-handle → register `loop.add_signal_handler(signal.SIGTERM, lambda: asyncio.create_task(agent.stop()))` in `main.py`. This worktree surfaces the hook; the agent `main.py`s wire it.
- **Health endpoint port collisions in tests:** Use `health_port=0` (ephemeral) in test subclasses so multiple parallel test cases don't fight over a port. Production: explicit `9101/9102/9103`.
- **`_load_state()` must tolerate corrupt JSON**, not just missing file. Return `{}` and log a warning — don't crash the agent on startup.
- **Checkpoint timing:** `_save_state()` runs on `stop()`. If a handler is running when SIGTERM arrives, we may lose the last increment. Pattern: handlers call `await self.checkpoint(...)` after each significant mutation; don't rely only on shutdown flush. Document this in the docstring.

## Out of scope

- Agent-specific `main.py` modules (Scout/Analyst/Strategist) — future WTs.
- Building the actual `sqlite.seed` files — Task 12.4 runtime step post-integration.
- Nginx reverse-proxy — Task 12.1 Step 3 is "optional if time permits".
- Vercel deploy — Plan B / C concern.

## Escalation

- WT1 (event-bus) + WT2 (llm-client) already merged — no upstream blockers remain.
- If Dedalus provides custom metadata fields in `systemd` units we haven't seen → check runbook, adapt, document in PR.
- If `aiohttp` not desired for health endpoint → fall back to stdlib `http.server` in a thread (documented alternative).
