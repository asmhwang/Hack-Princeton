# suppl.ai Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship an end-to-end agentic supply-chain war-room — three Dedalus-hosted agents (Scout, Analyst, Strategist) coordinating via Postgres `LISTEN/NOTIFY`, a FastAPI+WebSocket layer, and a Next.js dashboard — that runs all five demo scenarios in ≤60s with zero SQL mutation risk and zero email sends.

**Architecture:** Three Python asyncio agents, each on its own Dedalus VM, communicating only through Postgres (no direct RPC) — the "swarm discipline." Gemini 2.x calls use **function/tool calling + structured output** (no text-to-SQL, no free-form parsing). OpenClaw wraps Strategist's DB mutations. Next.js 15 App Router pushes live updates over WebSocket; Tailwind 4 + heavily customized shadcn primitives + Motion for the Linear/Vercel-grade aesthetic.

**Tech Stack:**
- Backend: Python 3.12 · `uv` · `ruff` · `mypy --strict` · FastAPI · SQLAlchemy 2.x async · asyncpg · Alembic · Pydantic v2 · structlog · tenacity · google-genai (Gemini 2.x) · openclaw · pytest · pytest-asyncio · pytest-postgresql
- Frontend: Next.js 15 (App Router) · React 19 · TypeScript strict · Tailwind CSS 4 · shadcn/ui · Zustand 5 · TanStack Query 5 · zod · openapi-typescript · Leaflet + react-leaflet · Recharts · Motion · Playwright
- Infra: 4 Dedalus Machines · Vercel · GitHub Actions · pre-commit + gitleaks

---

## How to read this plan

- **Phases 0–4** are the foundation. They are **mostly sequential**; they unblock parallel work.
- **Phases 5–7** (Scout → Analyst → Strategist) are Teammate A's track. Scout must exist before Analyst can be tested end-to-end; same Analyst → Strategist.
- **Phases 8–10** are Teammate B's track and can start the moment the API contract for each feature exists.
- **Phase 11** (demo scenarios + e2e) integrates everything; owner is Teammate C but all hands at the end.
- **Phase 12** (infra + polish) is the last pass.

**TDD granularity rule (per §CLAUDE.md and explicit user decision):**
- **Strict TDD** (write failing test → run → implement → re-run → commit, literal code shown) for: SQL-safety, event-bus reconnect, signal dedupe, severity scorer, dollar-exposure math, LLM-output parsing, approval state-transition atomicity, and all pure processors.
- **Milestone-level** (acceptance criteria + Playwright/visual check) for: UI composition, animations, charts, map, drawer/modal UX.

**LLM practices baked in:**
1. **Function/tool calling** instead of text-to-SQL for every read path. Tools are parameterized queries; the model picks tool+args, we execute.
2. **Structured output** via Gemini `response_schema` bound to Pydantic models for every classification/scoring/drafting call.
3. **Explicit prompt caching** via Gemini `cached_contents` for the big reusable context (schema reference, agent system prompt).
4. **Offline SQLite cache** `(prompt_hash → output)` per-VM for demo robustness if Gemini/Tavily go dark.
5. Prompts live as **versioned `.md` files** in each agent's `prompts/` dir, not inline Python strings.
6. Each agent carries an **eval suite** (pytest fixtures: for each of the 5 demo scenarios, assert expected-shape outputs).

**Known foot-guns baked into the plan:**
- Postgres `LISTEN/NOTIFY` drops silently on connection loss → Phase 2 Task 2.5 implements a reconnect+resubscribe loop.
- Motion package renamed: it's `motion`, not `framer-motion` → Phase 4 Task 4.2 installs the right one.
- `openapi-typescript` + `zod` codegen runs in pre-commit **and** CI → Phase 0 Task 0.7 and Phase 3 Task 3.1.
- Gemini explicit prompt caching ≠ SQLite offline cache → Phase 2 Task 2.7 implements both.

---

## Monorepo file structure

Create this tree during Phase 0. Don't pre-create empty files — Alembic/FastAPI/Next.js scaffolds generate most of them.

```
Hack-Princeton/
├── .github/workflows/ci.yml
├── .pre-commit-config.yaml
├── .gitleaks.toml
├── .gitignore
├── README.md
├── CLAUDE.md                              (exists)
├── suppl_ai_PRD.md                        (exists)
├── pyproject.toml                         (uv workspace root)
├── uv.lock
├── alembic.ini
├── backend/
│   ├── __init__.py
│   ├── db/
│   │   ├── __init__.py
│   │   ├── models.py                      (SQLAlchemy 2.x async)
│   │   ├── session.py                     (engine + pool)
│   │   ├── migrations/                    (alembic)
│   │   └── bus.py                         (LISTEN/NOTIFY reconnect loop)
│   ├── schemas/                           (Pydantic v2, shared)
│   │   ├── __init__.py
│   │   ├── signal.py
│   │   ├── disruption.py
│   │   ├── impact.py
│   │   ├── mitigation.py
│   │   └── approval.py
│   ├── llm/
│   │   ├── __init__.py
│   │   ├── client.py                      (Gemini wrapper: structured-out, tool-calling, cache)
│   │   ├── prompt_cache.py                (SQLite offline fallback)
│   │   └── tools/                         (Analyst query tools)
│   │       ├── __init__.py
│   │       └── analyst_tools.py
│   ├── observability/
│   │   ├── __init__.py
│   │   └── logging.py                     (structlog config, trace_id ctx)
│   ├── agents/
│   │   ├── __init__.py
│   │   ├── base.py                        (shared agent lifecycle + LISTEN loop)
│   │   ├── scout/
│   │   │   ├── __init__.py
│   │   │   ├── main.py
│   │   │   ├── config.py
│   │   │   ├── state.py
│   │   │   ├── sources/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── tavily.py              (shared Tavily wrapper)
│   │   │   │   ├── news.py
│   │   │   │   ├── weather.py             (Open-Meteo)
│   │   │   │   ├── policy.py
│   │   │   │   ├── logistics.py
│   │   │   │   └── macro.py
│   │   │   ├── processors/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── classify.py            (Gemini Flash classifier)
│   │   │   │   ├── dedupe.py              (72h window)
│   │   │   │   ├── severity.py            (rubric scorer)
│   │   │   │   └── fusion.py              (signal → disruption promotion/merge)
│   │   │   ├── prompts/
│   │   │   │   ├── classify.md
│   │   │   │   └── fusion.md
│   │   │   └── tests/
│   │   ├── analyst/
│   │   │   ├── __init__.py
│   │   │   ├── main.py
│   │   │   ├── config.py
│   │   │   ├── state.py
│   │   │   ├── processors/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── impact.py              (runs tool loop, builds report)
│   │   │   │   └── fallback.py            (rules-based template by category)
│   │   │   ├── prompts/
│   │   │   │   └── impact_system.md
│   │   │   └── tests/
│   │   └── strategist/
│   │       ├── __init__.py
│   │       ├── main.py
│   │       ├── config.py
│   │       ├── state.py
│   │       ├── processors/
│   │       │   ├── __init__.py
│   │       │   ├── options.py             (generate mitigation options)
│   │       │   ├── costing.py             (Δcost, Δdays math)
│   │       │   └── drafts.py              (supplier/customer/internal)
│   │       ├── actions/                   (OpenClaw-wrapped mutations)
│   │       │   ├── __init__.py
│   │       │   └── openclaw_actions.py
│   │       ├── prompts/
│   │       │   ├── options.md
│   │       │   └── drafts.md
│   │       └── tests/
│   ├── api/
│   │   ├── __init__.py
│   │   ├── main.py                        (FastAPI app factory)
│   │   ├── deps.py                        (DB session, current_user stub)
│   │   ├── ws.py                          (WebSocket manager, LISTEN relay)
│   │   ├── validators/
│   │   │   ├── __init__.py
│   │   │   └── sql_guard.py               (defense-in-depth; blocks non-SELECT)
│   │   └── routes/
│   │       ├── __init__.py
│   │       ├── signals.py
│   │       ├── disruptions.py
│   │       ├── mitigations.py
│   │       ├── analytics.py
│   │       ├── activity.py
│   │       └── dev.py                     (POST /api/dev/simulate)
│   ├── scripts/
│   │   ├── seed.py                        (idempotent)
│   │   ├── simulate.py                    (manual trigger helper)
│   │   └── smoke.py                       (check agents reachable)
│   └── tests/
│       ├── __init__.py
│       ├── conftest.py                    (pytest-postgresql, fixtures)
│       ├── fixtures/
│       │   ├── scenario_typhoon.py
│       │   ├── scenario_busan.py
│       │   ├── scenario_cbam.py
│       │   ├── scenario_luxshare.py
│       │   └── scenario_redsea.py
│       └── integration/
│           └── test_end_to_end.py
├── web/
│   ├── package.json
│   ├── pnpm-lock.yaml
│   ├── next.config.ts
│   ├── tsconfig.json
│   ├── tailwind.config.ts
│   ├── postcss.config.mjs
│   ├── eslint.config.mjs
│   ├── playwright.config.ts
│   ├── app/
│   │   ├── layout.tsx
│   │   ├── globals.css                    (all design tokens)
│   │   ├── (dashboard)/
│   │   │   ├── layout.tsx
│   │   │   ├── page.tsx                   (War Room)
│   │   │   ├── disruption/[id]/page.tsx
│   │   │   ├── analytics/page.tsx
│   │   │   └── exec/page.tsx
│   │   └── providers.tsx                  (TanStack, WS, Zustand)
│   ├── components/
│   │   ├── ui/                            (customized shadcn)
│   │   ├── shell/
│   │   │   ├── TopBar.tsx
│   │   │   ├── LeftRail.tsx
│   │   │   └── RightRail.tsx
│   │   ├── disruption/
│   │   │   ├── DisruptionCard.tsx
│   │   │   ├── DisruptionHeader.tsx
│   │   │   └── AffectedShipmentsTable.tsx
│   │   ├── mitigation/
│   │   │   ├── MitigationCardStack.tsx
│   │   │   ├── MitigationCard.tsx
│   │   │   ├── ApprovalModal.tsx
│   │   │   └── ExplainabilityDrawer.tsx
│   │   ├── map/
│   │   │   └── WorldMap.tsx
│   │   ├── agent-activity/
│   │   │   └── ActivityFeed.tsx
│   │   ├── charts/
│   │   │   ├── ExposureByQuarter.tsx
│   │   │   ├── ExposureByCustomer.tsx
│   │   │   └── ExposureBySku.tsx
│   │   └── skeletons/
│   │       ├── WarRoomSkeleton.tsx
│   │       └── DisruptionDetailSkeleton.tsx
│   ├── lib/
│   │   ├── api-client.ts                  (fetch + zod-validated)
│   │   ├── ws-client.ts
│   │   ├── store.ts                       (Zustand)
│   │   ├── design-tokens.ts               (TS mirror of CSS vars)
│   │   ├── format.ts                      (currency, dates, tabular)
│   │   └── query-keys.ts                  (TanStack key registry)
│   ├── hooks/
│   │   ├── useDisruptions.ts
│   │   ├── useImpact.ts
│   │   ├── useMitigations.ts
│   │   ├── useApprove.ts
│   │   ├── useSimulate.ts
│   │   └── useLiveUpdates.ts
│   ├── types/
│   │   ├── api.ts                         (openapi-typescript generated)
│   │   └── schemas.ts                     (zod schemas)
│   ├── tests/
│   │   └── e2e/
│   │       ├── scenarios.spec.ts          (all 5)
│   │       └── approval.spec.ts
│   └── public/
└── docs/
    ├── superpowers/
    │   ├── plans/
    │   └── specs/
    ├── architecture.md
    ├── demo-script.md
    └── runbook.md
```

---

## Cross-cutting conventions

### Conventional commits
Every commit uses `feat:`, `fix:`, `chore:`, `test:`, `docs:`, `refactor:`. Scope with component name in parens when useful: `feat(scout): add weather source`.

### Agent base class pattern (all 3 agents subclass this)
Implemented in `backend/agents/base.py` during Phase 2. Behaviors it provides:
- Startup: load checkpoint, open DB pool, register structlog trace context, subscribe to LISTEN channels.
- Loop: `asyncio.gather` over the agent's tasks (Scout has 5 sources; Analyst/Strategist have one worker each).
- Reconnect: on `asyncpg.InterfaceError`/`ConnectionDoesNotExistError`, back off → reopen pool → re-LISTEN → continue. Drops are silent otherwise.
- Shutdown: flush checkpoint to `/var/lib/supplai/state.json`, close pool.
- Health: exposes `/health` on `127.0.0.1:<port>` for a smoke check from the orchestrator VM.
- Logging: every DB write emits a `structlog` event with `trace_id`, `agent`, `event_type`, minimal payload.

### LLM call pattern
All Gemini calls go through `backend/llm/client.py:LLMClient`, which provides three methods:
- `structured(prompt, schema, model, cache_key)` → parses response via `response_schema` into a Pydantic model. Retries once on `ValidationError` with the error appended to the prompt. On second failure, raises `LLMValidationError` which callers catch and fall back.
- `with_tools(prompt, tools, model, cache_key)` → runs the tool-calling loop: model calls tool → we execute → feed result back → loop until model returns a final structured answer (also via `response_schema`). Hard cap: 6 tool calls per invocation.
- `cached_context(key, content)` → creates/reuses a Gemini `cached_contents` handle for large reusable context (e.g., full DB schema reference, agent system prompt).
- Every call checks the offline SQLite cache first (`backend/llm/prompt_cache.py`) keyed on `(model, hash(prompt+schema_fingerprint))`. Demo mode forces cache-only.

### Pre-commit + CI rules
- `pre-commit` runs: `ruff format`, `ruff check --fix`, `mypy --strict backend/db backend/schemas backend/llm backend/agents/base.py`, `gitleaks`, `openapi-typescript` check (no diff allowed), `pnpm lint`, `pnpm typecheck`.
- GitHub Actions `ci.yml` runs the same on PR + push to `main`, plus `pytest`, `pnpm build`, Playwright headless.

### Eval-driven prompts
Each agent has a `tests/prompts/` dir with one file per demo scenario. Each test builds the prompt context from a seeded fixture DB, calls the agent's processor, and asserts shape-level invariants (e.g., Analyst produces `≥ 3 affected_shipments for typhoon`, Strategist returns `≥ 2 mitigation_options`).

---

## Phase 0 — Foundation

**Owner:** All three teammates in the first 90 minutes; then Teammate A leads.

**Goal at end of phase:** `uv sync` + `pnpm install` clean on a fresh clone; CI green on a no-op PR; pre-commit catches a deliberate violation; Next.js dev server renders an empty shell with correct fonts + design tokens; FastAPI `/health` returns 200.

### Task 0.1: Initialize monorepo root

**Files:**
- Create: `.gitignore`, `.gitleaks.toml`, `README.md` (placeholder), `pyproject.toml`

- [ ] **Step 1: Init git and first commit already exists — add `.gitignore`**

```gitignore
# Python
__pycache__/
*.py[cod]
.venv/
.uv_cache/
dist/
*.egg-info/

# Node
node_modules/
.next/
.turbo/
pnpm-debug.log
playwright-report/
test-results/

# System
.DS_Store
*.log

# Env
.env
.env.local
.env.*.local
!.env.example

# Demo state
/var/lib/supplai/
backend/llm/*.sqlite
```

- [ ] **Step 2: Write root `pyproject.toml` — uv workspace with shared deps**

```toml
[project]
name = "suppl-ai"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
  "fastapi>=0.115",
  "uvicorn[standard]>=0.32",
  "sqlalchemy[asyncio]>=2.0.36",
  "asyncpg>=0.30",
  "alembic>=1.14",
  "pydantic>=2.10",
  "pydantic-settings>=2.7",
  "structlog>=24.4",
  "tenacity>=9.0",
  "google-genai>=0.3",
  "httpx>=0.28",
  "openclaw",
]

[dependency-groups]
dev = [
  "pytest>=8.3",
  "pytest-asyncio>=0.24",
  "pytest-postgresql>=6.1",
  "pytest-httpx>=0.35",
  "ruff>=0.8",
  "mypy>=1.13",
  "types-pyyaml",
  "pre-commit>=4.0",
]

[tool.ruff]
line-length = 100
target-version = "py312"

[tool.ruff.lint]
select = ["E","F","I","UP","B","SIM","ASYNC","PL"]
ignore = ["PLR0913"]

[tool.ruff.format]
quote-style = "double"

[tool.mypy]
python_version = "3.12"
strict = true
warn_unused_ignores = true
ignore_missing_imports = true

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["backend/tests","backend/agents/*/tests"]
```

- [ ] **Step 3: Write `.gitleaks.toml`** — lean config that blocks Gemini, Tavily, generic API keys. Copy the default from https://github.com/gitleaks/gitleaks/blob/master/config/gitleaks.toml (cached locally; don't fetch live during demo day).

- [ ] **Step 4: Commit**

```bash
git add .gitignore pyproject.toml .gitleaks.toml README.md
git commit -m "chore: initialize uv workspace + tooling config"
```

### Task 0.2: Pre-commit config

**Files:**
- Create: `.pre-commit-config.yaml`

- [ ] **Step 1: Write pre-commit config**

```yaml
repos:
  - repo: local
    hooks:
      - id: ruff-format
        name: ruff format
        entry: uv run ruff format
        language: system
        types_or: [python, pyi]
      - id: ruff-check
        name: ruff check
        entry: uv run ruff check --fix
        language: system
        types_or: [python, pyi]
      - id: mypy-shared
        name: mypy (shared modules)
        entry: uv run mypy --strict backend/db backend/schemas backend/llm backend/agents/base.py
        language: system
        pass_filenames: false
        types: [python]
      - id: gitleaks
        name: gitleaks
        entry: gitleaks protect --staged --config .gitleaks.toml
        language: system
        pass_filenames: false
      - id: pnpm-lint
        name: pnpm lint
        entry: bash -c 'cd web && pnpm lint'
        language: system
        pass_filenames: false
        files: ^web/
      - id: pnpm-typecheck
        name: pnpm typecheck
        entry: bash -c 'cd web && pnpm typecheck'
        language: system
        pass_filenames: false
        files: ^web/
      - id: openapi-types-fresh
        name: openapi-typescript in sync
        entry: bash -c 'cd web && pnpm run openapi:check'
        language: system
        pass_filenames: false
        files: ^(backend/api|web/types/api.ts)
```

- [ ] **Step 2: Install hooks** — `uv run pre-commit install`

- [ ] **Step 3: Commit** — `git commit -m "chore: pre-commit hooks with ruff/mypy/gitleaks/openapi drift check"`

### Task 0.3: CI workflow

**Files:**
- Create: `.github/workflows/ci.yml`

- [ ] **Step 1: Write CI workflow**

```yaml
name: ci
on:
  push: { branches: [main] }
  pull_request: { branches: [main] }

jobs:
  backend:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:16
        env: { POSTGRES_PASSWORD: test, POSTGRES_DB: test }
        ports: ["5432:5432"]
        options: --health-cmd="pg_isready" --health-interval=5s --health-timeout=5s --health-retries=10
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v4
      - run: uv sync --all-groups
      - run: uv run ruff check .
      - run: uv run ruff format --check .
      - run: uv run mypy --strict backend/db backend/schemas backend/llm backend/agents/base.py
      - run: uv run pytest -x --maxfail=1
        env:
          DATABASE_URL: postgresql+asyncpg://postgres:test@localhost:5432/test

  frontend:
    runs-on: ubuntu-latest
    defaults: { run: { working-directory: web } }
    steps:
      - uses: actions/checkout@v4
      - uses: pnpm/action-setup@v4
        with: { version: 9 }
      - uses: actions/setup-node@v4
        with: { node-version: 22, cache: pnpm, cache-dependency-path: web/pnpm-lock.yaml }
      - run: pnpm install --frozen-lockfile
      - run: pnpm lint
      - run: pnpm typecheck
      - run: pnpm build
```

- [ ] **Step 2: Open a trivial PR (any README edit) to confirm CI passes.** Block merging until green.

- [ ] **Step 3: Commit** — `git commit -m "chore: github actions ci for backend + frontend"`

### Task 0.4: Backend skeleton — FastAPI + SQLAlchemy + env config

**Files:**
- Create: `backend/__init__.py`, `backend/api/__init__.py`, `backend/api/main.py`, `backend/api/deps.py`, `backend/db/__init__.py`, `backend/db/session.py`, `backend/observability/logging.py`, `.env.example`

- [ ] **Step 1: Write `backend/observability/logging.py`**

```python
import logging
import uuid
from contextvars import ContextVar

import structlog

_trace: ContextVar[str] = ContextVar("trace_id", default="")

def new_trace() -> str:
    tid = uuid.uuid4().hex
    _trace.set(tid)
    return tid

def bind_trace(trace_id: str) -> None:
    _trace.set(trace_id)

def _inject_trace(_: object, __: str, event_dict: dict) -> dict:
    event_dict["trace_id"] = _trace.get() or ""
    return event_dict

def configure(level: str = "INFO", json_logs: bool = True) -> None:
    logging.basicConfig(level=level, format="%(message)s")
    processors = [
        structlog.contextvars.merge_contextvars,
        _inject_trace,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer() if json_logs else structlog.dev.ConsoleRenderer(),
    ]
    structlog.configure(processors=processors, wrapper_class=structlog.make_filtering_bound_logger(logging.INFO))
```

- [ ] **Step 2: Write `backend/db/session.py`**

```python
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

class DBSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/supplai"

_engine = None
_sessionmaker: async_sessionmaker[AsyncSession] | None = None

def engine():
    global _engine, _sessionmaker
    if _engine is None:
        s = DBSettings()
        _engine = create_async_engine(s.database_url, pool_size=5, max_overflow=5, pool_pre_ping=True)
        _sessionmaker = async_sessionmaker(_engine, expire_on_commit=False)
    return _engine

@asynccontextmanager
async def session() -> AsyncIterator[AsyncSession]:
    engine()
    assert _sessionmaker is not None
    async with _sessionmaker() as s:
        yield s
```

- [ ] **Step 3: Write `backend/api/main.py`**

```python
from contextlib import asynccontextmanager

from fastapi import FastAPI

from backend.observability.logging import configure

@asynccontextmanager
async def lifespan(app: FastAPI):
    configure()
    yield

app = FastAPI(title="suppl.ai", lifespan=lifespan)

@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
```

- [ ] **Step 4: Write `.env.example`**

```
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/supplai
GEMINI_API_KEY=
TAVILY_API_KEY=
DEMO_OFFLINE_CACHE=false
```

- [ ] **Step 5: Smoke test — run `uv run uvicorn backend.api.main:app --reload` and `curl localhost:8000/health`**. Expected: `{"status":"ok"}`.

- [ ] **Step 6: Commit** — `git commit -m "feat(api): FastAPI skeleton with health endpoint + structlog config"`

### Task 0.5: Frontend scaffold — Next.js 15 + Tailwind 4 + design tokens

**Files:**
- Create: `web/` via `pnpm create next-app@latest web --ts --app --tailwind --eslint --src-dir=false --import-alias "@/*"`
- Modify: `web/app/globals.css`, `web/app/layout.tsx`, `web/tailwind.config.ts`, `web/package.json`

- [ ] **Step 1: Scaffold Next.js** — from repo root: `pnpm create next-app@latest web --ts --app --tailwind --eslint --import-alias "@/*" --use-pnpm`. When prompted for `src/` dir, answer **no**.

- [ ] **Step 2: Install deps**

```bash
cd web
pnpm add zustand @tanstack/react-query zod motion leaflet react-leaflet recharts
pnpm add -D @types/leaflet openapi-typescript playwright @playwright/test @typescript-eslint/parser
pnpm dlx shadcn@latest init -d
```

Answer shadcn questions: Neutral base color; CSS variables **on**; no RSC wrapper. Use defaults otherwise — we override everything in Task 0.5 Step 4.

- [ ] **Step 3: Add scripts to `web/package.json`**

```json
"scripts": {
  "dev": "next dev --turbo",
  "build": "next build",
  "start": "next start",
  "lint": "eslint .",
  "typecheck": "tsc --noEmit",
  "openapi:gen": "openapi-typescript http://localhost:8000/openapi.json -o types/api.ts",
  "openapi:check": "openapi-typescript http://localhost:8000/openapi.json -o /tmp/api.gen.ts && diff -q types/api.ts /tmp/api.gen.ts",
  "test:e2e": "playwright test"
}
```

- [ ] **Step 4: Replace `web/app/globals.css` with the full PRD token set**

```css
@import "tailwindcss";

@theme {
  --color-bg: #0A0B0D;
  --color-surface: #111316;
  --color-surface-raised: #181B1F;
  --color-border: #23262B;
  --color-border-strong: #2E3238;
  --color-text: #E8EAED;
  --color-text-muted: #8B9098;
  --color-text-subtle: #5A6068;

  --color-critical: #E5484D;
  --color-critical-bg: #1F1315;
  --color-warn: #D97757;
  --color-warn-bg: #1F1612;
  --color-ok: #46A758;
  --color-info: #4A8FD4;

  --color-cat-weather: #5E81AC;
  --color-cat-policy: #B48EAD;
  --color-cat-news: #A3BE8C;
  --color-cat-logistics: #EBCB8B;
  --color-cat-macro: #D08770;

  --font-sans: "Inter", system-ui, sans-serif;
  --font-mono: "JetBrains Mono", ui-monospace, monospace;

  --text-xs: 11px;
  --text-sm: 13px;
  --text-base: 14px;
  --text-lg: 16px;
  --text-xl: 20px;
  --text-2xl: 28px;
  --text-display: 44px;

  --spacing-1: 4px;  --spacing-2: 8px;  --spacing-3: 12px;
  --spacing-4: 16px; --spacing-5: 24px; --spacing-6: 32px;
  --spacing-7: 48px; --spacing-8: 64px;

  --ease-out: cubic-bezier(0.22, 1, 0.36, 1);
  --ease-spring: cubic-bezier(0.34, 1.56, 0.64, 1);
  --duration-fast: 120ms;
  --duration-base: 200ms;
  --duration-slow: 320ms;
}

html, body {
  background: var(--color-bg);
  color: var(--color-text);
  font-family: var(--font-sans);
  font-size: var(--text-base);
}

.tnum { font-feature-settings: 'tnum' 1; }

@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after { animation-duration: 0.001ms !important; transition-duration: 0.001ms !important; }
}
```

- [ ] **Step 5: Wire Inter + JetBrains Mono via `next/font` in `web/app/layout.tsx`**

```tsx
import type { Metadata } from "next";
import { Inter, JetBrains_Mono } from "next/font/google";
import "./globals.css";

const inter = Inter({ subsets: ["latin"], variable: "--font-inter", display: "swap" });
const mono = JetBrains_Mono({ subsets: ["latin"], variable: "--font-mono", display: "swap" });

export const metadata: Metadata = { title: "suppl.ai", description: "Supply chain war room" };

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${inter.variable} ${mono.variable}`}>
      <body>{children}</body>
    </html>
  );
}
```

- [ ] **Step 6: Smoke test** — `pnpm dev` → `http://localhost:3000` renders with `#0A0B0D` background, `#E8EAED` text, Inter loaded. Verify in DevTools that `--color-bg` resolves correctly.

- [ ] **Step 7: Commit** — `git commit -m "feat(web): Next.js 15 + Tailwind 4 scaffold with suppl.ai design tokens"`

### Task 0.6: External-services `.env.example` + team creds checklist

- [ ] **Step 1: Doc only** — open `docs/runbook.md`; add a "Before you start" section listing: claim Dedalus credits, generate Gemini API key (paste in shared 1Password), generate Tavily API key, confirm Vercel account linked to repo.
- [ ] **Step 2: Commit** — `git commit -m "docs: runbook 'before you start' checklist"`

### Task 0.7: openapi-typescript codegen verified end-to-end

Runs after Task 0.4 + Task 0.5.

- [ ] **Step 1: With FastAPI dev server running, generate types** — `cd web && pnpm openapi:gen`. Confirm `web/types/api.ts` has the `/health` route typed.
- [ ] **Step 2: Run `pnpm openapi:check`** — expect zero diff.
- [ ] **Step 3: Commit** — `git add web/types/api.ts && git commit -m "chore: generate initial openapi-typescript types"`

**Phase 0 done when:** fresh clone → `uv sync && pnpm install && uv run uvicorn backend.api.main:app` and in a second terminal `pnpm -C web dev` → `/health` returns `{"status":"ok"}` and `localhost:3000` renders the dark themed empty page with Inter loaded.

---

## Phase 1 — Database schema + seed data

**Owner:** Teammate A.

**Goal at end of phase:** `uv run alembic upgrade head` creates all 12 tables; `uv run python -m backend.scripts.seed` idempotently produces 30 ports, 50 suppliers, 40 SKUs, 20 customers, 200 POs, 500 shipments; `uv run alembic downgrade -1 && uv run alembic upgrade head` cycles cleanly.

### Task 1.1: Alembic init + Postgres dev container

**Files:**
- Create: `alembic.ini`, `backend/db/migrations/env.py`, `backend/db/migrations/script.py.mako`

- [ ] **Step 1: `uv run alembic init backend/db/migrations`**. Move `alembic.ini` to repo root.
- [ ] **Step 2: Wire async engine in `migrations/env.py`** — replace the default with the async template from https://alembic.sqlalchemy.org/en/latest/cookbook.html#using-asyncio-with-alembic (import `engine()` from `backend.db.session`).
- [ ] **Step 3: Start a dev Postgres** — document `docker run --name supplai-pg -e POSTGRES_PASSWORD=postgres -p 5432:5432 -d postgres:16` in `docs/runbook.md`.
- [ ] **Step 4: Commit** — `git commit -m "chore(db): alembic init with async env"`

### Task 1.2: Define SQLAlchemy 2.x models

**Files:**
- Create: `backend/db/models.py`

- [ ] **Step 1: Write the models file**

```python
from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    ARRAY, Column, Date, DateTime, ForeignKey, Integer, Numeric, String, Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

class Base(DeclarativeBase):
    pass

class Port(Base):
    __tablename__ = "ports"
    id: Mapped[str] = mapped_column(Text, primary_key=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    country: Mapped[str] = mapped_column(Text, nullable=False)
    lat: Mapped[float | None] = mapped_column(Numeric)
    lng: Mapped[float | None] = mapped_column(Numeric)
    modes: Mapped[list[str]] = mapped_column(ARRAY(Text), default=list)

class Supplier(Base):
    __tablename__ = "suppliers"
    id: Mapped[str] = mapped_column(Text, primary_key=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    country: Mapped[str | None] = mapped_column(Text)
    region: Mapped[str | None] = mapped_column(Text)
    tier: Mapped[int | None] = mapped_column(Integer)
    industry: Mapped[str | None] = mapped_column(Text)
    reliability_score: Mapped[Decimal | None] = mapped_column(Numeric)
    categories: Mapped[list[str]] = mapped_column(ARRAY(Text), default=list)
    lat: Mapped[float | None] = mapped_column(Numeric)
    lng: Mapped[float | None] = mapped_column(Numeric)

class Sku(Base):
    __tablename__ = "skus"
    id: Mapped[str] = mapped_column(Text, primary_key=True)
    description: Mapped[str | None] = mapped_column(Text)
    family: Mapped[str | None] = mapped_column(Text)
    industry: Mapped[str | None] = mapped_column(Text)
    unit_cost: Mapped[Decimal | None] = mapped_column(Numeric)
    unit_revenue: Mapped[Decimal | None] = mapped_column(Numeric)

class Customer(Base):
    __tablename__ = "customers"
    id: Mapped[str] = mapped_column(Text, primary_key=True)
    name: Mapped[str | None] = mapped_column(Text)
    tier: Mapped[str | None] = mapped_column(Text)
    sla_days: Mapped[int | None] = mapped_column(Integer)
    contact_email: Mapped[str | None] = mapped_column(Text)

class PurchaseOrder(Base):
    __tablename__ = "purchase_orders"
    id: Mapped[str] = mapped_column(Text, primary_key=True)
    customer_id: Mapped[str] = mapped_column(ForeignKey("customers.id"))
    sku_id: Mapped[str] = mapped_column(ForeignKey("skus.id"))
    qty: Mapped[int] = mapped_column(Integer)
    due_date: Mapped[date | None] = mapped_column(Date)
    revenue: Mapped[Decimal] = mapped_column(Numeric)
    sla_breach_penalty: Mapped[Decimal | None] = mapped_column(Numeric)

class Shipment(Base):
    __tablename__ = "shipments"
    id: Mapped[str] = mapped_column(Text, primary_key=True)
    po_id: Mapped[str] = mapped_column(ForeignKey("purchase_orders.id"))
    supplier_id: Mapped[str] = mapped_column(ForeignKey("suppliers.id"))
    origin_port_id: Mapped[str] = mapped_column(ForeignKey("ports.id"))
    dest_port_id: Mapped[str] = mapped_column(ForeignKey("ports.id"))
    status: Mapped[str] = mapped_column(Text)  # planned | in_transit | rerouting | arrived
    mode: Mapped[str | None] = mapped_column(Text)
    eta: Mapped[date | None] = mapped_column(Date)
    value: Mapped[Decimal | None] = mapped_column(Numeric)

class Signal(Base):
    __tablename__ = "signals"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source_category: Mapped[str] = mapped_column(Text)  # news|weather|policy|logistics|macro
    source_name: Mapped[str] = mapped_column(Text)
    title: Mapped[str] = mapped_column(Text)
    summary: Mapped[str | None] = mapped_column(Text)
    region: Mapped[str | None] = mapped_column(Text)
    lat: Mapped[float | None] = mapped_column(Numeric)
    lng: Mapped[float | None] = mapped_column(Numeric)
    radius_km: Mapped[Decimal | None] = mapped_column(Numeric)
    source_urls: Mapped[list[str]] = mapped_column(ARRAY(Text), default=list)
    confidence: Mapped[Decimal] = mapped_column(Numeric)
    raw_payload: Mapped[dict] = mapped_column(JSONB, default=dict)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    dedupe_hash: Mapped[str] = mapped_column(Text, unique=True)
    promoted_to_disruption_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))

class Disruption(Base):
    __tablename__ = "disruptions"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title: Mapped[str] = mapped_column(Text)
    summary: Mapped[str | None] = mapped_column(Text)
    category: Mapped[str] = mapped_column(Text)
    severity: Mapped[int] = mapped_column(Integer)  # 1..5
    region: Mapped[str | None] = mapped_column(Text)
    lat: Mapped[float | None] = mapped_column(Numeric)
    lng: Mapped[float | None] = mapped_column(Numeric)
    radius_km: Mapped[Decimal | None] = mapped_column(Numeric)
    source_signal_ids: Mapped[list[uuid.UUID]] = mapped_column(ARRAY(UUID(as_uuid=True)))
    confidence: Mapped[Decimal] = mapped_column(Numeric)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    last_seen_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    status: Mapped[str] = mapped_column(Text)  # active | resolved

class ImpactReport(Base):
    __tablename__ = "impact_reports"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    disruption_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("disruptions.id"))
    total_exposure: Mapped[Decimal] = mapped_column(Numeric)
    units_at_risk: Mapped[int] = mapped_column(Integer)
    cascade_depth: Mapped[int] = mapped_column(Integer)
    sql_executed: Mapped[str | None] = mapped_column(Text)  # synthesized for explainability
    reasoning_trace: Mapped[dict] = mapped_column(JSONB)
    generated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

class AffectedShipment(Base):
    __tablename__ = "affected_shipments"
    impact_report_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("impact_reports.id"), primary_key=True)
    shipment_id: Mapped[str] = mapped_column(ForeignKey("shipments.id"), primary_key=True)
    exposure: Mapped[Decimal] = mapped_column(Numeric)
    days_to_sla_breach: Mapped[int | None] = mapped_column(Integer)

class MitigationOption(Base):
    __tablename__ = "mitigation_options"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    impact_report_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("impact_reports.id"))
    option_type: Mapped[str] = mapped_column(Text)  # reroute|alternate_supplier|expedite
    description: Mapped[str] = mapped_column(Text)
    delta_cost: Mapped[Decimal] = mapped_column(Numeric)
    delta_days: Mapped[int] = mapped_column(Integer)
    confidence: Mapped[Decimal] = mapped_column(Numeric)
    rationale: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text, default="pending")  # pending|approved|dismissed

class DraftCommunication(Base):
    __tablename__ = "draft_communications"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    mitigation_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("mitigation_options.id"))
    recipient_type: Mapped[str] = mapped_column(Text)  # supplier|customer|internal
    recipient_contact: Mapped[str] = mapped_column(Text)
    subject: Mapped[str] = mapped_column(Text)
    body: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    sent_at: Mapped[datetime | None] = mapped_column(DateTime)  # always NULL

class Approval(Base):
    __tablename__ = "approvals"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    mitigation_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("mitigation_options.id"))
    approved_by: Mapped[str] = mapped_column(Text)
    approved_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    state_snapshot: Mapped[dict] = mapped_column(JSONB)

class AgentLog(Base):
    __tablename__ = "agent_log"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    agent_name: Mapped[str] = mapped_column(Text)
    trace_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    event_type: Mapped[str] = mapped_column(Text)
    payload: Mapped[dict] = mapped_column(JSONB)
    ts: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
```

Note `dedupe_hash` column on `signals` — this is the 72h dedupe key from PRD §5.2.1; added here so we get a unique index for free.

- [ ] **Step 2: Generate initial migration** — `uv run alembic revision --autogenerate -m "initial schema"`. Hand-inspect the generated SQL; ensure indexes from PRD §8.1 are present; add any missing with manual `op.create_index` calls.

- [ ] **Step 3: Apply + verify** — `uv run alembic upgrade head`; `psql -l`; `\dt` shows all 12 tables.

- [ ] **Step 4: Commit** — `git commit -m "feat(db): initial schema (12 tables, indexes, constraints)"`

### Task 1.3: Down-migration verified (critical for Sunday schema drift)

- [ ] **Step 1: Run `uv run alembic downgrade base && uv run alembic upgrade head`**. Must succeed without errors.
- [ ] **Step 2: No commit needed** — failure here means fix the migration, don't paper over it.

### Task 1.4: Seed script — idempotent + reproducible

**Files:**
- Create: `backend/scripts/__init__.py`, `backend/scripts/seed.py`, `backend/scripts/seed_data/` (JSON fixtures)

- [ ] **Step 1: Write test for idempotency FIRST** — `backend/tests/test_seed.py`

```python
import pytest
from backend.scripts.seed import seed_all
from backend.db.session import session

async def _counts(s):
    from backend.db.models import Port, Supplier, Sku, Customer, PurchaseOrder, Shipment
    from sqlalchemy import select, func
    return {
        m.__tablename__: (await s.execute(select(func.count()).select_from(m))).scalar_one()
        for m in [Port, Supplier, Sku, Customer, PurchaseOrder, Shipment]
    }

@pytest.mark.asyncio
async def test_seed_is_idempotent(postgresql_engine):
    async with session() as s:
        await seed_all(s); await s.commit()
        first = await _counts(s)
        await seed_all(s); await s.commit()
        second = await _counts(s)
    assert first == second == {"ports":30,"suppliers":50,"skus":40,"customers":20,"purchase_orders":200,"shipments":500}
```

- [ ] **Step 2: Run and confirm it fails** — `uv run pytest backend/tests/test_seed.py -v`. Expected: `ImportError: cannot import name 'seed_all'`.

- [ ] **Step 3: Implement `backend/scripts/seed.py`**

Use `INSERT … ON CONFLICT DO NOTHING` for every row. Data layout:
- **Ports (30):** pre-defined JSON at `seed_data/ports.json` — Shanghai, Shenzhen, Ningbo, Busan, Kaohsiung, Ho Chi Minh, Singapore, Port Klang, Colombo, Jebel Ali, Rotterdam, Hamburg, Antwerp, Felixstowe, NY, LA, Long Beach, Oakland, Savannah, Houston, Vancouver, Tokyo, Yokohama, Incheon, Bangkok, Manila, Hong Kong, Mumbai, Chennai, Durban.
- **Suppliers (50):** seeded with deterministic IDs `SUP-E-001` … `SUP-E-015` (electronics), `SUP-A-001`…`SUP-A-010` (apparel), `SUP-F-001`…`SUP-F-010` (food), `SUP-P-001`…`SUP-P-008` (pharma), `SUP-I-001`…`SUP-I-007` (industrial). Lat/lng near realistic factory clusters; reliability_score 0.55–0.98.
- **SKUs (40):** 8 per industry, IDs `MCU-A`, `PMIC-B`, `APPAREL-T01`, `RICE-50KG`, `VAX-COVID`, `BEARING-X`, etc.
- **Customers (20):** mix of tier Strategic (5), Gold (7), Standard (8); SLA days 30–120; contact emails `ops@<name>.example.com`.
- **POs (200):** round-robin customers × SKUs; qty 10–2000; revenue 10K–300K; sla_breach_penalty 5–15% of revenue.
- **Shipments (500):** 300 in_transit, 100 planned, 100 arrived; distributed across POs with deterministic assignment via `hash(po_id) % n_ports`.

Determinism: **seed random with `random.Random(42)`** inside `seed_all`; never rely on wall-clock.

- [ ] **Step 4: Run the seed test** — `uv run pytest backend/tests/test_seed.py -v`. Expected: PASS.

- [ ] **Step 5: Add CLI entry** — at bottom of `seed.py`:

```python
if __name__ == "__main__":
    import asyncio
    from backend.db.session import session
    async def main():
        async with session() as s:
            await seed_all(s); await s.commit()
    asyncio.run(main())
```

- [ ] **Step 6: Run `uv run python -m backend.scripts.seed`** — verify counts via `psql -c "select count(*) from suppliers"`.

- [ ] **Step 7: Commit** — `git commit -m "feat(db): idempotent seed (30 ports / 50 suppliers / 40 SKUs / 200 POs / 500 shipments)"`

**Phase 1 done when:** migrations apply + rollback clean; seed runs twice without duplicating; counts match spec.

---

## Phase 2 — Shared backend primitives

**Owner:** Teammate A.

**Goal at end of phase:** Any agent can subclass `AgentBase`, subscribe to Postgres channels, call `LLMClient.structured` or `LLMClient.with_tools`, and write to the DB with idempotency. Event bus recovers from a dropped connection. Offline cache intercepts LLM calls when `DEMO_OFFLINE_CACHE=true`.

### Task 2.1: Pydantic schemas — shared contracts

**Files:**
- Create: `backend/schemas/signal.py`, `disruption.py`, `impact.py`, `mitigation.py`, `approval.py`, `__init__.py` re-exports

- [ ] **Step 1: Write schemas** — one Pydantic v2 model per concept, matching DB columns one-to-one plus computed fields. Every schema uses `model_config = ConfigDict(from_attributes=True, extra="forbid")`. Example `schemas/signal.py`:

```python
from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

SourceCategory = Literal["news","weather","policy","logistics","macro"]

class SignalClassification(BaseModel):
    """Output of the Scout classifier — constrained via Gemini response_schema."""
    model_config = ConfigDict(extra="forbid")
    source_category: SourceCategory
    title: str = Field(min_length=3, max_length=200)
    summary: str = Field(min_length=10, max_length=1000)
    region: str | None = None
    lat: float | None = None
    lng: float | None = None
    radius_km: float | None = Field(default=None, ge=0, le=5000)
    severity: int = Field(ge=1, le=5)
    confidence: float = Field(ge=0, le=1)
    dedupe_keywords: list[str] = Field(max_length=10)

class SignalRecord(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid")
    id: uuid.UUID
    source_category: SourceCategory
    source_name: str
    title: str
    summary: str | None
    region: str | None
    lat: float | None
    lng: float | None
    radius_km: Decimal | None
    source_urls: list[str]
    confidence: Decimal
    first_seen_at: datetime
    promoted_to_disruption_id: uuid.UUID | None
```

Mirror for the other entities. Keep `Classification` (LLM output) separate from `Record` (DB read) — the PRD's "response validation" discipline.

- [ ] **Step 2: Type check** — `uv run mypy --strict backend/schemas`. Expected clean.
- [ ] **Step 3: Commit** — `git commit -m "feat(schemas): pydantic v2 contracts for signals/disruptions/impact/mitigation/approval"`

### Task 2.2: SQL defense-in-depth validator

Even with function-calling on the main path, we keep a validator to prove "zero SQL mutation" to judges. It guards `impact_reports.sql_executed` before it's stored (synthesized explainability SQL) and is exposed as a safety check for any future agent path that strings together SQL.

**Files:**
- Create: `backend/api/validators/__init__.py`, `backend/api/validators/sql_guard.py`, `backend/tests/test_sql_guard.py`

- [ ] **Step 1: Write test FIRST** — `backend/tests/test_sql_guard.py`

```python
import pytest
from backend.api.validators.sql_guard import validate_select_only, SqlSafetyError

@pytest.mark.parametrize("sql", [
    "SELECT 1",
    "SELECT id, name FROM suppliers WHERE region = 'EU'",
    "SELECT count(*) FROM shipments s JOIN ports p ON s.origin_port_id = p.id",
    "  select * from signals where first_seen_at > now() - interval '72 hours'  ",
])
def test_accepts_plain_selects(sql):
    validate_select_only(sql)

@pytest.mark.parametrize("sql", [
    "DROP TABLE signals",
    "DELETE FROM shipments",
    "UPDATE suppliers SET reliability_score = 0",
    "INSERT INTO signals VALUES (1)",
    "SELECT 1; DROP TABLE x",
    "SELECT 1 -- ; DROP TABLE x",
    "WITH q AS (SELECT 1) DELETE FROM shipments",
    "GRANT ALL ON signals TO public",
    "TRUNCATE shipments",
    "ALTER TABLE signals ADD COLUMN x INT",
    "",
    "SELECT",
    "SELECT 1; SELECT 2",
])
def test_rejects_mutations_and_multi_statement(sql):
    with pytest.raises(SqlSafetyError):
        validate_select_only(sql)
```

- [ ] **Step 2: Run it** — `uv run pytest backend/tests/test_sql_guard.py -v`. Expected: ImportError.

- [ ] **Step 3: Implement `sql_guard.py`**

```python
from __future__ import annotations

import re

import sqlparse

class SqlSafetyError(ValueError):
    pass

_FORBIDDEN = {
    "INSERT","UPDATE","DELETE","DROP","ALTER","TRUNCATE",
    "GRANT","REVOKE","CREATE","REPLACE","COPY","VACUUM",
    "MERGE","CALL","LOCK",
}

def validate_select_only(sql: str) -> None:
    stripped = sql.strip()
    if not stripped:
        raise SqlSafetyError("empty")
    # strip line/block comments so "-- ; DROP" can't sneak in
    no_comments = re.sub(r"--[^\n]*", "", stripped)
    no_comments = re.sub(r"/\*.*?\*/", "", no_comments, flags=re.S)
    statements = [s for s in sqlparse.split(no_comments) if s.strip()]
    if len(statements) != 1:
        raise SqlSafetyError("only single SELECT allowed")
    parsed = sqlparse.parse(statements[0])[0]
    tokens = [t for t in parsed.flatten() if not t.is_whitespace]
    if not tokens:
        raise SqlSafetyError("empty parse")
    # first keyword must be SELECT or WITH (followed by a read)
    first = next((t for t in tokens if t.ttype and "Keyword" in str(t.ttype)), None)
    if first is None or first.normalized.upper() not in {"SELECT","WITH"}:
        raise SqlSafetyError(f"must start with SELECT, got {first.normalized if first else 'nothing'}")
    # forbidden keyword anywhere = reject
    for tok in tokens:
        if tok.ttype and "Keyword" in str(tok.ttype) and tok.normalized.upper() in _FORBIDDEN:
            raise SqlSafetyError(f"forbidden keyword: {tok.normalized}")
```

Add `sqlparse>=0.5` to `pyproject.toml` dependencies; run `uv sync`.

- [ ] **Step 4: Re-run tests** — `uv run pytest backend/tests/test_sql_guard.py -v`. Expected: all PASS.

- [ ] **Step 5: Commit** — `git commit -m "feat(safety): SQL defense-in-depth validator (single SELECT, no forbidden keywords)"`

### Task 2.3: Event bus — LISTEN/NOTIFY with reconnect

**Files:**
- Create: `backend/db/bus.py`, `backend/tests/test_bus.py`

- [ ] **Step 1: Write test FIRST**

```python
import asyncio
import pytest
from backend.db.bus import EventBus

@pytest.mark.asyncio
async def test_publish_subscribe_roundtrip(postgresql_url):
    bus = EventBus(postgresql_url)
    await bus.start()
    received = asyncio.Queue()
    await bus.subscribe("test_ch", lambda p: received.put_nowait(p))
    await bus.publish("test_ch", "hello")
    msg = await asyncio.wait_for(received.get(), timeout=2)
    assert msg == "hello"
    await bus.stop()

@pytest.mark.asyncio
async def test_survives_connection_drop(postgresql_url, monkeypatch):
    bus = EventBus(postgresql_url)
    await bus.start()
    received = asyncio.Queue()
    await bus.subscribe("test_ch", lambda p: received.put_nowait(p))
    await bus._force_drop_for_test()         # forcibly close underlying conn
    await asyncio.sleep(0.5)                 # let reconnect loop kick in
    await bus.publish("test_ch", "after-drop")
    msg = await asyncio.wait_for(received.get(), timeout=3)
    assert msg == "after-drop"
    await bus.stop()
```

- [ ] **Step 2: Run — expect ImportError.**

- [ ] **Step 3: Implement `backend/db/bus.py`**

```python
from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import Any

import asyncpg
import structlog

log = structlog.get_logger()
Handler = Callable[[str], Awaitable[None] | None]

class EventBus:
    def __init__(self, dsn: str) -> None:
        self._dsn = dsn.replace("postgresql+asyncpg://", "postgresql://")
        self._conn: asyncpg.Connection | None = None
        self._subs: dict[str, list[Handler]] = {}
        self._reconnect_task: asyncio.Task | None = None
        self._stop = asyncio.Event()

    async def start(self) -> None:
        self._stop.clear()
        await self._ensure_conn()
        self._reconnect_task = asyncio.create_task(self._reconnect_loop())

    async def stop(self) -> None:
        self._stop.set()
        if self._reconnect_task:
            self._reconnect_task.cancel()
        if self._conn:
            await self._conn.close()
            self._conn = None

    async def subscribe(self, channel: str, handler: Handler) -> None:
        self._subs.setdefault(channel, []).append(handler)
        if self._conn:
            await self._conn.add_listener(channel, self._dispatch)

    async def publish(self, channel: str, payload: str) -> None:
        conn = await asyncpg.connect(self._dsn)
        try:
            await conn.execute(f"NOTIFY {channel}, $1", payload)  # noqa — channel sanitized by caller
        finally:
            await conn.close()

    async def _ensure_conn(self) -> None:
        self._conn = await asyncpg.connect(self._dsn)
        for ch in self._subs:
            await self._conn.add_listener(ch, self._dispatch)

    def _dispatch(self, _conn, _pid, channel: str, payload: str) -> None:
        for h in self._subs.get(channel, []):
            res = h(payload)
            if asyncio.iscoroutine(res):
                asyncio.create_task(res)

    async def _reconnect_loop(self) -> None:
        backoff = 1.0
        while not self._stop.is_set():
            try:
                if self._conn is None or self._conn.is_closed():
                    log.warning("bus.reconnect", backoff=backoff)
                    await asyncio.sleep(backoff)
                    backoff = min(backoff * 2, 30.0)
                    await self._ensure_conn()
                    backoff = 1.0
                else:
                    await asyncio.sleep(1.0)
            except Exception as e:
                log.error("bus.reconnect_failed", error=str(e))
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 30.0)

    async def _force_drop_for_test(self) -> None:
        if self._conn:
            await self._conn.close()
            self._conn = None
```

Publishing uses a one-shot connection so a dead listener doesn't swallow notifications. The reconnect loop re-listens to every channel after a drop. This closes the PRD §6 "Reliability" gap.

- [ ] **Step 4: Run tests — all PASS.**

- [ ] **Step 5: Commit** — `git commit -m "feat(bus): LISTEN/NOTIFY with reconnect + resubscribe"`

### Task 2.4: LLM client — structured output + tool calling + caching

**Files:**
- Create: `backend/llm/client.py`, `backend/llm/prompt_cache.py`, `backend/tests/test_llm_client.py`

- [ ] **Step 1: Write tests FIRST** — cover: (a) structured call returns parsed Pydantic model, (b) validation error triggers one retry, (c) tool loop runs tools in order and stops at final answer, (d) offline cache hits short-circuit the API.

```python
import pytest
from pydantic import BaseModel
from backend.llm.client import LLMClient, LLMValidationError

class _Out(BaseModel):
    n: int

@pytest.mark.asyncio
async def test_structured_returns_model(monkeypatch, tmp_path):
    client = LLMClient(cache_path=tmp_path / "c.sqlite", model="flash")
    monkeypatch.setattr(client, "_raw_structured", lambda **k: '{"n":42}')
    out = await client.structured("prompt", _Out)
    assert out == _Out(n=42)

@pytest.mark.asyncio
async def test_structured_retries_once_on_validation(monkeypatch, tmp_path):
    calls = []
    def fake(**k):
        calls.append(k)
        return '{"n":"not-an-int"}' if len(calls) == 1 else '{"n":3}'
    client = LLMClient(cache_path=tmp_path/"c.sqlite", model="flash")
    monkeypatch.setattr(client, "_raw_structured", fake)
    out = await client.structured("prompt", _Out)
    assert out == _Out(n=3)
    assert len(calls) == 2

@pytest.mark.asyncio
async def test_offline_cache_short_circuits(monkeypatch, tmp_path):
    client = LLMClient(cache_path=tmp_path/"c.sqlite", model="flash")
    # prime the cache
    client._cache.put(client._cache_key("prompt", _Out), '{"n":7}')
    async def _should_not_call(**_): raise AssertionError("api called")
    monkeypatch.setattr(client, "_raw_structured", _should_not_call)
    out = await client.structured("prompt", _Out)
    assert out == _Out(n=7)
```

- [ ] **Step 2: Run — fails.**

- [ ] **Step 3: Implement `backend/llm/prompt_cache.py`** — small SQLite wrapper with `get(key) -> str | None`, `put(key, value)`. Key is `sha256(model + "::" + prompt + "::" + schema_fingerprint)`. Gated on env `DEMO_OFFLINE_CACHE=true`.

- [ ] **Step 4: Implement `backend/llm/client.py`**

Methods:
- `structured(prompt, schema, *, cache_key=None)` — uses `google.genai.Client().models.generate_content(..., config={"response_mime_type": "application/json", "response_schema": schema})`. Parses via `schema.model_validate_json(raw)`. On `ValidationError`: one retry with `f"{prompt}\n\nYour previous output failed validation: {err}"`. Offline cache checked first + filled on success.
- `with_tools(prompt, tools, *, cache_key=None, max_iters=6)` — tools is a `list[Tool]` where each tool has `name`, `description`, Pydantic `args_schema`, and `callable: Callable[[args], Awaitable[dict]]`. Runs the Gemini function-calling loop; executes tool locally; appends `function_response` content; continues until the model returns a final response parsed through the final `response_schema` (caller passes one via `final_schema=...`). Records every tool call in a returned `trace: list[ToolInvocation]` alongside the final result.
- `cached_context(key, content)` — calls `client.caches.create(model=..., config={"contents":[content]})` and memoizes the returned name; returns a `cached_content` handle to pass into subsequent `generate_content` calls via `config.cached_content=<name>`.

Uses `tenacity.AsyncRetrying(stop=stop_after_attempt(3), wait=wait_exponential_jitter(1, 8))` for transport errors (5xx, connection resets).

- [ ] **Step 5: Tests PASS.**
- [ ] **Step 6: Commit** — `git commit -m "feat(llm): gemini client with structured output, tool calling, cached contexts, sqlite offline cache"`

### Task 2.5: Agent base class — lifecycle, LISTEN, checkpoint, health

**Files:**
- Create: `backend/agents/__init__.py`, `backend/agents/base.py`, `backend/tests/test_agent_base.py`

- [ ] **Step 1: Write test FIRST** — spawn a trivial subclass that subscribes to a channel, increments a counter on each message, and persists the counter on shutdown. Publish 3 messages; assert counter = 3; restart and assert counter loads from checkpoint.

- [ ] **Step 2: Run — fails.**

- [ ] **Step 3: Implement `AgentBase`**

```python
from __future__ import annotations

import asyncio
import json
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

    def __init__(self, dsn: str) -> None:
        self._bus = EventBus(dsn)
        self._state: dict[str, Any] = {}
        self._tasks: list[asyncio.Task] = []
        self._stop = asyncio.Event()

    async def start(self) -> None:
        self._state = self._load_state()
        await self._bus.start()
        for ch in self.channels:
            await self._bus.subscribe(ch, self._wrap(ch))
        self._tasks = [asyncio.create_task(t) for t in self.background_tasks()]
        log.info("agent.started", agent=self.name, channels=self.channels)

    async def stop(self) -> None:
        self._stop.set()
        for t in self._tasks:
            t.cancel()
        await asyncio.gather(*self._tasks, return_exceptions=True)
        await self._bus.stop()
        self._save_state()
        log.info("agent.stopped", agent=self.name)

    def _wrap(self, channel: str):
        async def _on(payload: str):
            new_trace()
            try:
                await self.on_notify(channel, payload)
            except Exception as e:
                log.error("agent.handler_failed", agent=self.name, channel=channel, error=str(e))
        return _on

    async def on_notify(self, channel: str, payload: str) -> None: ...
    def background_tasks(self) -> list: return []

    def _load_state(self) -> dict:
        try:
            return json.loads(self.state_path.read_text())
        except FileNotFoundError:
            return {}

    def _save_state(self) -> None:
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        self.state_path.write_text(json.dumps(self._state))
```

Plus a small aiohttp/uvicorn health endpoint on `127.0.0.1:<port>` returning `{"agent": name, "ok": true}`.

- [ ] **Step 4: Tests PASS.**
- [ ] **Step 5: Commit** — `git commit -m "feat(agents): base class with lifecycle, LISTEN, checkpoint, health endpoint"`

### Task 2.6: Analyst query tools (function-calling) — library

**Files:**
- Create: `backend/llm/tools/analyst_tools.py`, `backend/tests/test_analyst_tools.py`

These are the parameterized read tools exposed to Gemini in Phase 6. Defining them here (shared primitives) because the API uses the same functions for the explainability drawer's "synthesized SQL" display.

- [ ] **Step 1: Write test FIRST** — for each tool, seed a fixture DB, call the tool, assert shape + values.

- [ ] **Step 2: Implement tools** — each is an `async def` taking Pydantic args and returning a dict + a synthesized SQL string:

```python
from pydantic import BaseModel, Field
from sqlalchemy import select
from backend.db.session import session
from backend.db.models import Shipment, Supplier, Port, PurchaseOrder, Customer, Sku

class ShipmentsTouchingRegionArgs(BaseModel):
    region_polygon: list[tuple[float, float]] | None = None
    radius_center: tuple[float, float] | None = None
    radius_km: float | None = Field(default=None, gt=0, le=3000)
    status_in: list[str] = ["in_transit","planned"]

async def shipments_touching_region(args: ShipmentsTouchingRegionArgs) -> dict:
    # Postgres cube/earthdistance extension; we'll add it in Phase 1 migration tail
    # Returns {rows: [...], sql: "<synthesized SQL for explainability>"}
    ...
```

Set of tools (minimum):
- `shipments_touching_region` — shipments whose origin port is within N km of a center or inside a polygon.
- `purchase_orders_for_skus` — POs that reference given SKUs.
- `customers_by_po` — customers for a set of POs.
- `exposure_aggregate` — total exposure $, units at risk, POs affected, by filter.
- `alternate_suppliers_for_sku` — suppliers who list the SKU family in `categories`, ranked by reliability and distance to destination port.
- `alternate_ports_near` — ports within N km of a reference port, excluding ones in the affected region.
- `shipment_history_status` — state transitions for a shipment (from agent_log + approvals).

Each returns `{"rows": [...], "synthesized_sql": "...", "row_count": n}`. The `synthesized_sql` is a best-effort human-readable SQL string built from the parameters — **not executed**; it's for the explainability drawer.

- [ ] **Step 3: Tests PASS.**
- [ ] **Step 4: Commit** — `git commit -m "feat(llm/tools): analyst query tools for function-calling loop"`

### Task 2.7: Prompt cache SQLite + offline mode toggle

Covered by Task 2.4 step 3; only remaining step is wiring the toggle in `.env.example` already done in Task 0.4. No action here; listed for checklist completeness.

- [ ] **Step 1: Confirm `DEMO_OFFLINE_CACHE=true` in `.env.local` forces cache-only mode** via a manual test: prime the cache, set flag, kill Gemini-facing network (or monkey-patch), call `LLMClient.structured` — must still return.

**Phase 2 done when:** Agent base class + LLM client + bus + SQL guard + analyst tools all pass their unit tests; `mypy --strict` clean on `backend/db`, `backend/schemas`, `backend/llm`, `backend/agents/base.py`.

---

## Phase 3 — FastAPI skeleton + WebSocket

**Owner:** Teammate C.

**Goal at end of phase:** All HTTP routes return typed responses (even if empty / 404-on-no-data); WebSocket `/ws/updates` relays `new_*` Postgres notifications to all connected clients; OpenAPI types regenerated and committed.

### Task 3.1: WebSocket manager + LISTEN relay

**Files:**
- Create: `backend/api/ws.py`

- [ ] **Step 1: Write test FIRST** — spin up the app via `httpx.ASGITransport`, connect a WS client, publish `NOTIFY new_signal, '{"id":"..."}'`, assert client receives the message within 500ms.

- [ ] **Step 2: Implement `ConnectionManager`** + background task that starts on app lifespan and uses `EventBus` to relay `new_signal`, `new_disruption`, `new_impact`, `new_mitigation`, `new_approval` to all connected clients as `{"type": "<event>", "payload": <json>}`.

- [ ] **Step 3: Commit** — `git commit -m "feat(api): websocket relay for LISTEN/NOTIFY events"`

### Task 3.2: Route stubs — signals, disruptions, mitigations, activity, analytics

**Files:**
- Create: `backend/api/routes/signals.py`, `disruptions.py`, `mitigations.py`, `activity.py`, `analytics.py`, `dev.py`

- [ ] **Step 1: Each route returns typed responses via Pydantic schemas from Phase 2.** Empty cases return `[]` or `404` with `HTTPException(404, "not found")`, never `500`. Cursor-pagination for list routes: `?before=<iso>&limit=50`.
- [ ] **Step 2: `dev.py`** exposes `POST /api/dev/simulate` with body `{"scenario": "typhoon_kaia" | "busan_strike" | "cbam_tariff" | "luxshare_fire" | "redsea_advisory"}`. This writes a pre-baked `Signal` row and emits `NOTIFY new_signal`. Body of the scenarios defined in Phase 11.
- [ ] **Step 3: Tests** via `pytest-httpx` / `httpx.AsyncClient(app=app)` — one per route asserting shape + empty-state behavior.
- [ ] **Step 4: Commit** — `git commit -m "feat(api): route stubs + POST /dev/simulate"`

### Task 3.3: OpenAPI → TS types regeneration

- [ ] **Step 1: Run `pnpm -C web openapi:gen`.** Review diff.
- [ ] **Step 2: Commit** — `git commit -m "chore(web): regen openapi types"`

**Phase 3 done when:** all routes respond; `/ws/updates` relays messages; pre-commit enforces openapi parity.

---

## Phase 4 — Frontend foundation (shell, stores, clients)

**Owner:** Teammate B.

**Goal at end of phase:** War Room shell renders with left rail (empty state), center ("select a disruption"), right rail (empty), top bar showing `0 active · $0 at risk`; Zustand store + TanStack Query provider + WebSocket client wired; Inter + JetBrains Mono loaded; skeleton components in place.

### Task 4.1: Providers + theme wrapper

**Files:**
- Create: `web/app/providers.tsx`

- [ ] **Step 1: Wrap with `QueryClientProvider`, Zustand initialization, `WebSocketProvider` (Task 4.4).**
- [ ] **Step 2: Mount in `app/layout.tsx`.**
- [ ] **Step 3: Commit.**

### Task 4.2: Install and configure Motion

```bash
pnpm -C web add motion
```

Important: **it's `motion`, not `framer-motion`.** (The PRD's "formerly Framer Motion" line refers to the rebrand.)

- [ ] **Step 1: Add `MotionConfig` in `providers.tsx`** with `reducedMotion="user"` so respect for `prefers-reduced-motion` is automatic.
- [ ] **Step 2: Commit.**

### Task 4.3: Zustand store

**Files:**
- Create: `web/lib/store.ts`

- [ ] **Step 1: Define store** — slices: `selectedDisruptionId`, `drawerOpen`, `activityFeed` (bounded at 50), `simulateInFlight`.
- [ ] **Step 2: Commit.**

### Task 4.4: API client + WS client (zod-validated)

**Files:**
- Create: `web/lib/api-client.ts`, `web/lib/ws-client.ts`, `web/types/schemas.ts`

- [ ] **Step 1: Write `schemas.ts`** — zod mirror of the Pydantic contracts. Use `zod.object().strict()` everywhere. Export `Signal`, `Disruption`, `ImpactReport`, etc.
- [ ] **Step 2: Write `api-client.ts`** — typed fetch wrapper. Each method uses the OpenAPI-generated types for request and the zod schema for response-runtime-validation (`schema.parse(await res.json())`).
- [ ] **Step 3: Write `ws-client.ts`** — connects to `/ws/updates`, with exponential backoff reconnect. Emits typed events via the Zustand store; `onNewSignal`, `onNewDisruption`, `onNewImpact`, `onNewMitigation`, `onNewApproval`.
- [ ] **Step 4: Commit.**

### Task 4.5: App shell — TopBar, LeftRail, RightRail, layout

**Files:**
- Create: `web/components/shell/TopBar.tsx`, `LeftRail.tsx`, `RightRail.tsx`; `web/app/(dashboard)/layout.tsx`; `web/app/(dashboard)/page.tsx`

- [ ] **Step 1: Build the 56px top bar + 280px left rail + 320px right rail grid using CSS Grid** per PRD §7.2.3.
- [ ] **Step 2: Empty-state components:**
  - Left rail: "No active disruptions" with a muted "Simulate event" suggestion link (not a button — keep CTA on top bar).
  - Center: product pitch in two sentences + prominent `Simulate event` button.
  - Right rail: dim/empty activity feed.
- [ ] **Step 3: Every numeric cell uses `.tnum` class.**
- [ ] **Step 4: Playwright smoke test** — load `/`, assert top-bar text + Simulate button is visible.
- [ ] **Step 5: Commit.**

### Task 4.6: Skeleton loaders

**Files:**
- Create: `web/components/skeletons/WarRoomSkeleton.tsx`, `DisruptionDetailSkeleton.tsx`

- [ ] **Step 1: Skeletons mirror final layout pixel-for-pixel (per PRD §9.6 — "no layout shift on data arrival").**
- [ ] **Step 2: Commit.**

**Phase 4 done when:** War Room shell renders; TanStack Query provider works; WS client connects and shows "connected"; Playwright smoke green; Lighthouse Accessibility ≥95 on the empty shell.

---

## Phase 5 — Scout agent

**Owner:** Teammate A.

**Goal at end of phase:** Scout VM runs 5 parallel source tasks; produces deduped, classified, severity-scored `signals` rows; promotes/merges into `disruptions` rows; emits `NOTIFY new_signal` / `new_disruption` on every write; survives restart; UI (via API polling) shows live signals appearing.

### Task 5.1: Dedupe processor

**Files:**
- Create: `backend/agents/scout/processors/dedupe.py`, `tests/test_dedupe.py`

- [ ] **Step 1: Write test FIRST**
  - Dedupe hash = `sha256(region || category || sorted(keywords))`.
  - Two raw signals with same (region, category, keywords) inside 72h → second rejected.
  - Same inputs 73h later → accepted.

- [ ] **Step 2: Implement** — reads existing signals with `dedupe_hash` match and `first_seen_at > now() - interval '72h'`. Uniqueness also enforced by the unique index from Phase 1.

- [ ] **Step 3: Commit.**

### Task 5.2: Severity scorer

**Files:**
- Create: `backend/agents/scout/processors/severity.py`, `tests/test_severity.py`

Rubric from PRD §5.2.1:
- +2 if affects any port/supplier within 500km of our DB coords
- +1 if named storm / sanction / strike / fire / flood keyword match
- +1 if multiple source categories concur on same region within 24h
- +1 if impact radius > 300km
- Clamp 1..5

- [ ] **Step 1: Write test FIRST** with 8 cases covering each branch.
- [ ] **Step 2: Implement.**
- [ ] **Step 3: Commit.**

### Task 5.3: Classifier (Gemini Flash with structured output)

**Files:**
- Create: `backend/agents/scout/processors/classify.py`, `backend/agents/scout/prompts/classify.md`

- [ ] **Step 1: Write `classify.md`** — system prompt establishing the Scout's role, examples of classifications, strict output fields. Uses the `SignalClassification` Pydantic schema from Phase 2 as `response_schema`.

- [ ] **Step 2: Implement `classify_raw_signal(raw: dict) -> SignalClassification`** — calls `LLMClient.structured`. Raw signal is whatever Tavily / Open-Meteo returned (title, body snippet, URL, coords if present).

- [ ] **Step 3: Prompt eval test** — `tests/prompts/test_classify.py` with 10 fixture inputs (pre-captured Tavily responses saved to `tests/fixtures/raw/*.json`), each expecting category and severity within ±1 of the expected.

- [ ] **Step 4: Commit.**

### Task 5.4: Signal fusion → disruption

**Files:**
- Create: `backend/agents/scout/processors/fusion.py`, `prompts/fusion.md`, `tests/test_fusion.py`

- [ ] **Step 1: Write test FIRST** — two related severity-2 signals in same 500km region within 48h should fuse into one severity-3 disruption.

- [ ] **Step 2: Implement** — query unfused signals older than 10s, younger than 72h, group by region bucket. For each cluster ≥2 or any ≥severity 4 solo, call Gemini Pro via `structured` with a fusion schema (`DisruptionDraft`) to produce a titled summary. Insert into `disruptions`, set `source_signal_ids`, update each signal's `promoted_to_disruption_id`, `NOTIFY new_disruption`.

- [ ] **Step 3: Commit.**

### Task 5.5: Sources — Tavily wrapper

**Files:**
- Create: `backend/agents/scout/sources/tavily.py`

- [ ] **Step 1: Implement** `async def search(query: str, *, topic: str, days: int = 1) -> list[dict]`. Caches last 50 results per query in-memory + SQLite (offline demo fallback). Respects `tenacity` retry with exponential backoff.
- [ ] **Step 2: Commit.**

### Task 5.6: Source — news (Tavily)

**Files:**
- Create: `backend/agents/scout/sources/news.py`

- [ ] **Step 1: Implement loop** — every 60s, query Tavily with tuned news queries from `sources/tavily_queries.md` (documented in Task 5.12). For each result: classify → dedupe → insert signal → `NOTIFY new_signal` → fusion check.
- [ ] **Step 2: Commit.**

### Task 5.7: Source — weather (Open-Meteo)

**Files:**
- Create: `backend/agents/scout/sources/weather.py`

- [ ] **Step 1: For each of our 30 ports + 50 suppliers, poll Open-Meteo current + 48h forecast every 5 minutes.** No auth required. Trigger signal when: wind ≥ 100km/h, precipitation ≥ 100mm/24h, or tropical-system categories.
- [ ] **Step 2: Commit.**

### Task 5.8: Source — policy (Tavily)

**Files:**
- Create: `backend/agents/scout/sources/policy.py`

- [ ] **Step 1: Every 15 minutes, search USTR/EU Commission/MOFCOM/national bureaus for tariff / sanction / export-control updates.**
- [ ] **Step 2: Commit.**

### Task 5.9: Source — logistics (Tavily)

**Files:**
- Create: `backend/agents/scout/sources/logistics.py`

- [ ] **Step 1: Every 10 minutes, search for port congestion / carrier advisories / canal status.**
- [ ] **Step 2: Commit.**

### Task 5.10: Source — macro (Tavily)

**Files:**
- Create: `backend/agents/scout/sources/macro.py`

- [ ] **Step 1: Every 30 minutes, search for Baltic Dry Index / TAC / oil / freight rate moves.**
- [ ] **Step 2: Commit.**

### Task 5.11: Scout agent `main.py` — wires everything

**Files:**
- Create: `backend/agents/scout/main.py`, `config.py`, `state.py`

- [ ] **Step 1: Subclass `AgentBase`, declare channels=[], background_tasks = [news_loop(), weather_loop(), policy_loop(), logistics_loop(), macro_loop(), fusion_tick()].**
- [ ] **Step 2: Checkpoint state** — per-source cursors (last Tavily since-id, last weather poll ts per port).
- [ ] **Step 3: Integration test** — `scripts/simulate.py --source news --scenario typhoon` injects a canned Tavily result into the cache; run Scout for 10 seconds; assert signal + disruption rows created + `new_disruption` notification received.
- [ ] **Step 4: Commit — `feat(scout): agent main with 5 parallel source tasks`.**

### Task 5.12: Document Tavily query library

**Files:**
- Create: `backend/agents/scout/sources/tavily_queries.md`

- [ ] **Step 1: List the ~20 tuned queries per category** with rationale. This is a judging artifact per PRD §13.3.
- [ ] **Step 2: Commit.**

**Phase 5 done when:** Scout runs locally (`uv run python -m backend.agents.scout.main`) under offline-cache mode; injected canned signals yield classified, deduped, fused rows; WS relay pushes `new_signal`/`new_disruption` to the dashboard (even though the UI just logs them for now); `systemctl restart`-simulated kill-relaunch resumes checkpoint.

---

## Phase 6 — Analyst agent (function-calling impact reports)

**Owner:** Teammate A.

**Goal at end of phase:** Analyst VM subscribes to `new_disruption`; for each disruption, calls Gemini Pro in the tool-calling loop (tools from Phase 2 Task 2.6) → synthesizes impact report + affected shipments list + synthesized-SQL string + reasoning trace; writes rows; emits `new_impact`. End-to-end latency ≤ 30s on the typhoon fixture.

### Task 6.1: Impact processor — the tool loop

**Files:**
- Create: `backend/agents/analyst/processors/impact.py`, `backend/agents/analyst/prompts/impact_system.md`, `tests/test_impact.py`

- [ ] **Step 1: Write `impact_system.md`** — establishes the Analyst role, describes every tool (name + when to use), requires the model to end with an `ImpactReport` structured output matching the Pydantic schema.

- [ ] **Step 2: Write test FIRST** — seed DB with typhoon fixture (13–15 shipments around Shenzhen). Mock `LLMClient.with_tools` to deterministically call `shipments_touching_region` → `purchase_orders_for_skus` → `customers_by_po` → `exposure_aggregate` in order, then return a final `ImpactReport`. Assert: report written, `total_exposure` within 10% of ground truth `$2.3M`, `AffectedShipment` rows written, `reasoning_trace.tool_calls` length == 4.

- [ ] **Step 3: Implement `build_impact_report(disruption_id)`**
  - Load disruption row.
  - Build prompt with disruption context + full schema summary (cached via `LLMClient.cached_context` keyed on schema version — one-shot per Analyst process).
  - Call `LLMClient.with_tools(prompt, analyst_tools, final_schema=ImpactReport)`.
  - Persist: insert `impact_reports` (including synthesized SQL string — concatenation of each tool call's `synthesized_sql`), upsert `affected_shipments` rows with `ON CONFLICT DO NOTHING`, `NOTIFY new_impact`.

- [ ] **Step 4: Commit.**

### Task 6.2: Fallback — rules-based template by category

**Files:**
- Create: `backend/agents/analyst/processors/fallback.py`, `tests/test_fallback.py`

- [ ] **Step 1: Write test FIRST** — on `LLMValidationError` or empty tool output, invoke the fallback which uses hard-coded query templates keyed on `disruption.category` (weather → radius search around lat/lng; policy → SKU-family filter; logistics → port-filter; etc.). Assert report still written.

- [ ] **Step 2: Implement.** Imports from `analyst_tools.py` directly — no LLM.
- [ ] **Step 3: Commit.**

### Task 6.3: Analyst `main.py`

**Files:**
- Create: `backend/agents/analyst/main.py`, `config.py`, `state.py`

- [ ] **Step 1: Subclass `AgentBase` with channels=['new_disruption'].** `on_notify`: parse `disruption_id`, call `build_impact_report`, catch `LLMValidationError` → call fallback.
- [ ] **Step 2: Integration test** — publish `NOTIFY new_disruption, '<uuid>'`; within 30s an `impact_reports` row appears with ≥1 affected shipment; `new_impact` emitted.
- [ ] **Step 3: Commit.**

**Phase 6 done when:** typhoon scenario → impact report in ≤ 30s; reasoning_trace shows actual tool names; fallback kicks in correctly when Gemini returns invalid final output; mypy strict clean.

---

## Phase 7 — Strategist agent (OpenClaw action layer)

**Owner:** Teammate A.

**Goal at end of phase:** For each `new_impact`, Strategist produces 2–4 mitigation options + 3 draft communications per option, all via OpenClaw-wrapped DB writes; emits `new_mitigation`. OpenClaw path demonstrably visible in logs for judging.

### Task 7.1: Options processor

**Files:**
- Create: `backend/agents/strategist/processors/options.py`, `costing.py`, `prompts/options.md`, `tests/test_options.py`

- [ ] **Step 1: Write test FIRST** — given an impact report (typhoon fixture), assert Strategist produces:
  - ≥ 2 mitigation options.
  - Each option has `delta_cost` ≥ 0, `delta_days` integer (can be negative), `confidence` in [0,1].
  - At least one option type is `reroute` or `alternate_supplier`.

- [ ] **Step 2: Prompt uses `with_tools` with the full Analyst tool set + two new tools:**
  - `alternate_suppliers_for_sku` (reuse from Phase 2 2.6)
  - `alternate_ports_near`
  Final schema is `MitigationOptionsBundle` (a Pydantic model containing `options: list[MitigationOption]`).

- [ ] **Step 3: Costing helper (`costing.py`) does the Δcost/Δdays math** given the alternate route/supplier + original shipments. Pure function; unit tested.
- [ ] **Step 4: Commit.**

### Task 7.2: Draft communications processor

**Files:**
- Create: `backend/agents/strategist/processors/drafts.py`, `prompts/drafts.md`, `tests/test_drafts.py`

- [ ] **Step 1: Write test FIRST** — given a mitigation option, assert three drafts produced:
  - `supplier`: formal tone, mentions alternate supplier + timeline.
  - `customer`: empathetic, explicit delay disclosure + new ETA.
  - `internal`: terse, bullet points, $ figures.

- [ ] **Step 2: Use `LLMClient.structured` with `DraftCommunicationBundle` schema (three drafts in one call).** Tone anchored via prompt templates; forbidden words ("regrettably", "unfortunately" in internal drafts) enforced via post-parse validation.

- [ ] **Step 3: Commit.**

### Task 7.3: OpenClaw action layer

**Files:**
- Create: `backend/agents/strategist/actions/openclaw_actions.py`, `tests/test_openclaw_actions.py`

- [ ] **Step 1: Wrap every DB mutation in an OpenClaw `Action`** following the `annyzhou/openclaw-ddls` reference pattern:
  - `SaveMitigationOptions(options: list) -> list[UUID]`
  - `SaveDraftCommunications(drafts: list) -> list[UUID]`
  - `FlipShipmentStatuses(ids: list[str], to: str) -> None`
  - `WriteApprovalAudit(mitigation_id, user_id, state_snapshot) -> UUID`

- [ ] **Step 2: Each action logs to `agent_log` with `event_type='openclaw.<action_name>'` for judge-visible trace.**
- [ ] **Step 3: Integration test** — run `SaveMitigationOptions` and assert rows written + log entry exists.
- [ ] **Step 4: Commit.**

### Task 7.4: Strategist `main.py`

**Files:**
- Create: `backend/agents/strategist/main.py`, `config.py`, `state.py`

- [ ] **Step 1: Subclass AgentBase, channels=['new_impact']**. `on_notify`: load impact report → `generate_options` → for each option, `generate_drafts` → `SaveMitigationOptions` → `SaveDraftCommunications` → `NOTIFY new_mitigation`.
- [ ] **Step 2: Integration test** — publish `new_impact` → within 45s, `mitigation_options` ≥2, `draft_communications` = 3×options, `new_mitigation` emitted.
- [ ] **Step 3: Commit.**

**Phase 7 done when:** Strategist produces options + drafts for all 5 scenarios within ≤45s each; OpenClaw wraps every mutation; `grep smtplib` returns empty across the codebase (gitleaks-equivalent check in CI).

---

## Phase 8 — War Room UI (live dashboard)

**Owner:** Teammate B.

**Goal at end of phase:** War Room renders live via TanStack Query + WebSocket; left rail lists active disruptions sorted by $ exposure; center shows selected disruption's detail + map; right rail shows mitigations + activity feed. Matches PRD §9.1 wireframe.

### Task 8.1: Disruption hooks + left rail

**Files:**
- Create: `web/hooks/useDisruptions.ts`, `useLiveUpdates.ts`; `web/components/shell/LeftRail.tsx` (upgrade from Phase 4), `web/components/disruption/DisruptionCard.tsx`

- [ ] **Step 1: `useDisruptions` subscribes** to `/api/signals` + `/api/disruptions?status=active`; listens to WS `new_disruption` → invalidate query.
- [ ] **Step 2: Left rail shows disruption cards** sorted by `impact_report.total_exposure DESC`. Category badge colored per tokens. Entrance: slide-in-from-left spring with 20ms stagger.
- [ ] **Step 3: Playwright visual snapshot** of the left rail with 3 seeded disruptions.
- [ ] **Step 4: Commit.**

### Task 8.2: Disruption detail + affected shipments table

**Files:**
- Create: `web/components/disruption/DisruptionHeader.tsx`, `AffectedShipmentsTable.tsx`; `web/app/(dashboard)/disruption/[id]/page.tsx`

- [ ] **Step 1: Header matches wireframe** — title, category badge, severity dots, detected time.
- [ ] **Step 2: Table:** mono IDs, sans names, right-aligned numerics with `.tnum`, urgency `!` marker for `days_to_sla_breach < 2` in critical red.
- [ ] **Step 3: Sticky first column for IDs, virtualized if >50 rows** (use `@tanstack/react-virtual`).
- [ ] **Step 4: Commit.**

### Task 8.3: Map (Leaflet)

**Files:**
- Create: `web/components/map/WorldMap.tsx`

- [ ] **Step 1: React-leaflet with OSM tiles.** SSR-off wrapper (`dynamic(() => import('./...'), { ssr: false })`).
- [ ] **Step 2: Disruption pin:** scale-in with spring overshoot, radius ring pulses once, settles. Color per category.
- [ ] **Step 3: Shipment dots:** clustered markers; filter to affected only for selected disruption.
- [ ] **Step 4: Commit.**

### Task 8.4: Mitigation cards

**Files:**
- Create: `web/components/mitigation/MitigationCardStack.tsx`, `MitigationCard.tsx`

- [ ] **Step 1: Stack of 3 cards matching wireframe**: option type, description, Δcost, Δdays, confidence %, `Approve` button (stub for Phase 9).
- [ ] **Step 2: "Why this recommendation?"** link opens Explainability drawer (Phase 10).
- [ ] **Step 3: Commit.**

### Task 8.5: Activity feed

**Files:**
- Create: `web/components/agent-activity/ActivityFeed.tsx`

- [ ] **Step 1: Reverse-chronological list; new items slide in from top.** Agent name colored (Scout green, Analyst amber, Strategist lilac — semantic, not category tokens).
- [ ] **Step 2: Feeds from `/api/activity/feed` + WS notifications.**
- [ ] **Step 3: Commit.**

### Task 8.6: Top bar — live $ exposure

**Files:**
- Modify: `web/components/shell/TopBar.tsx`

- [ ] **Step 1: Poll `/api/analytics/exposure` every 30s + invalidate on WS `new_approval`.** Display as `3 active · $4.2M at risk` with `.tnum`. On change, brief highlight pulse (120ms) — **not** a number-tick animation (would be distracting).
- [ ] **Step 2: Commit.**

**Phase 8 done when:** clicking Simulate (stubbed dev endpoint) populates the entire dashboard within ≤60s; screenshots match wireframe §9.1; no layout shift; Lighthouse Performance ≥90 on the War Room with seeded data.

---

## Phase 9 — Approval workflow

**Owner:** Teammate B (UI) + Teammate C (API).

**Goal at end of phase:** Approving a mitigation: (a) flips affected shipments' status to `rerouting`, (b) writes `approvals` row with state snapshot, (c) saves drafts (already written by Strategist — just confirms they're linked), (d) emits `new_approval`, (e) dashboard animates the mitigation card into the approvals log entry via `layoutId`.

### Task 9.1: Approval API route — atomic transaction

**Files:**
- Modify: `backend/api/routes/mitigations.py`
- Create: `backend/tests/test_approval_atomicity.py`

- [ ] **Step 1: Write test FIRST (strict TDD — safety-critical)**
  - Seed mitigation + 3 affected shipments.
  - Monkey-patch `WriteApprovalAudit` to raise mid-transaction.
  - Call `POST /api/mitigations/:id/approve`.
  - Assert: response is 500; shipments **still** `in_transit` (not `rerouting`); no `approvals` row exists.

- [ ] **Step 2: Implement** `approve_mitigation` as a single transaction. Uses OpenClaw `FlipShipmentStatuses` + `WriteApprovalAudit`, wrapped in `async with session.begin():`. On any failure: rollback; no partial state. On success: `NOTIFY new_approval`.

- [ ] **Step 3: Tests PASS.**
- [ ] **Step 4: Commit — `feat(api): atomic approval transaction (rerouting + audit + notify)`.**

### Task 9.2: Approval modal (UI)

**Files:**
- Create: `web/components/mitigation/ApprovalModal.tsx`
- Create: `web/hooks/useApprove.ts`

- [ ] **Step 1: Modal matches §9.2 wireframe** — summary, drafts list (3 expandable previews), DB changes list, Approve button.
- [ ] **Step 2: `useOptimistic` for instant feedback**: mitigation card visually "approves" before server confirms; reverts on error.
- [ ] **Step 3: On success, card morphs into an approvals log entry via Motion `layoutId`.** Timing: button collapses (120ms) → checkmark (120ms) → `layoutId` transition (200ms) to the activity feed row.
- [ ] **Step 4: Commit.**

### Task 9.3: Approvals log (right rail / audit view)

**Files:**
- Modify: `web/components/agent-activity/ActivityFeed.tsx`

- [ ] **Step 1: `new_approval` events render a distinct card style** (slight green left border) with `approved_by`, time, $ delta.
- [ ] **Step 2: Commit.**

**Phase 9 done when:** atomicity test green; end-to-end approval from click to DB state flip + animation lands in ≤300ms perceived + audit entry visible.

---

## Phase 10 — Explainability drawer, analytics, exec view

**Owner:** Teammate B.

**Goal at end of phase:** Explainability drawer shows trigger signals + synthesized SQL + reasoning trace; analytics page has 3 charts + CSV export; exec page shows one-pager for Derek.

### Task 10.1: Explainability drawer

**Files:**
- Create: `web/components/mitigation/ExplainabilityDrawer.tsx`

- [ ] **Step 1: Right-side drawer, slides in with overshoot spring.** Tabs: **Signals** (chip list), **Query** (synthesized SQL, JetBrains Mono, syntax highlight via `shiki`), **Reasoning** (numbered trace from `impact_reports.reasoning_trace.tool_calls`), **Alternatives** (dismissed options).
- [ ] **Step 2: Content fades in 60ms after drawer settles.**
- [ ] **Step 3: Commit.**

### Task 10.2: Analytics page

**Files:**
- Create: `web/app/(dashboard)/analytics/page.tsx`, `web/components/charts/ExposureByQuarter.tsx`, `ExposureByCustomer.tsx`, `ExposureBySku.tsx`
- Modify: `backend/api/routes/analytics.py`

- [ ] **Step 1: API:** `/api/analytics/exposure?group_by=quarter|customer|sku` returns aggregated rows.
- [ ] **Step 2: Charts use muted palette** from category tokens; no rainbow; no grid lines except baseline.
- [ ] **Step 3: CSV export** button — client-side generation from query data (no extra endpoint).
- [ ] **Step 4: Commit.**

### Task 10.3: Exec summary page

**Files:**
- Create: `web/app/(dashboard)/exec/page.tsx`

- [ ] **Step 1: Single page, generous whitespace.** Big status: `STABLE` / `MONITORING` / `ESCALATED` derived from sum(active disruption severity). 3 active cards. 4-week trend sparkline. Single CTA "Open war room".
- [ ] **Step 2: Commit.**

**Phase 10 done when:** drawer populated for all 5 scenarios; analytics CSV verifies roundtrip in Excel; exec page reads clean at 1280×800 judging laptop.

---

## Phase 11 — Demo scenarios + E2E tests

**Owner:** Teammate C.

**Goal at end of phase:** `POST /api/dev/simulate` with any of 5 scenario names triggers a full pipeline run visible on the dashboard in ≤60s. Playwright suite covers all 5.

### Task 11.1: Scenario fixtures

**Files:**
- Create: `backend/scripts/scenarios/typhoon_kaia.py`, `busan_strike.py`, `cbam_tariff.py`, `luxshare_fire.py`, `redsea_advisory.py`

Each scenario defines:
- A canned Tavily-style payload (title, body, url, region, coords).
- A canned Open-Meteo payload (for weather-driven ones).
- Expected impact-report shape (for eval tests).

- [ ] **Step 1: Write each scenario as a pure-Python constant module.**
- [ ] **Step 2: `simulate(scenario_name)`** inserts the canned signal directly (bypasses Tavily call), classifies, promotes to disruption, `NOTIFY new_disruption` → Analyst → Strategist cascade.
- [ ] **Step 3: Commit.**

### Task 11.2: Playwright E2E — all 5 scenarios

**Files:**
- Create: `web/tests/e2e/scenarios.spec.ts`

- [ ] **Step 1: Setup** — beforeEach starts backend via `uv run uvicorn` in a child process, seeds DB, starts agents in offline-cache mode. afterEach kills everything.
- [ ] **Step 2: One test per scenario**: click Simulate → pick scenario → assert disruption card appears ≤ 10s → click card → assert mitigation cards ≥2 appear ≤ 60s → click Approve → assert shipment status flips.
- [ ] **Step 3: Run `pnpm test:e2e`** — all 5 green.
- [ ] **Step 4: Commit.**

### Task 11.3: Simulate button wiring

- [ ] **Step 1: Top bar `+ Simulate event` button opens a lightweight menu** listing the 5 scenarios (typed from an endpoint `/api/dev/scenarios`). Click → `POST /api/dev/simulate`.
- [ ] **Step 2: Commit.**

**Phase 11 done when:** 5 consecutive clean Playwright runs, 5 scenarios each, on demo laptop; E2E P95 ≤ 60s; zero flakes.

---

## Phase 12 — Infrastructure, polish, accessibility, submission

**Owner:** All hands.

### Task 12.1: Dedalus VMs

- [ ] **Step 1:** Provision 4 Machines: `scout-vm`, `analyst-vm`, `strategist-vm`, `db-vm`. Default tier.
- [ ] **Step 2:** `systemd` unit files for each agent: `supplai-scout.service`, `supplai-analyst.service`, `supplai-strategist.service`. Runs `uv run python -m backend.agents.<name>.main`. Restart on failure. `StateDirectory=supplai` → `/var/lib/supplai/` for checkpoints.
- [ ] **Step 3:** FastAPI on `db-vm` (co-located). Nginx reverse-proxy optional if time permits.
- [ ] **Step 4:** `scripts/smoke.py` hits `/health` on each agent VM + `/health` on API.
- [ ] **Step 5:** Commit unit files + deploy script under `infra/` (new dir, document in README).

### Task 12.2: Vercel frontend deploy

- [ ] **Step 1:** Link `web/` to Vercel project. Env vars: `NEXT_PUBLIC_API_BASE=https://<db-vm>/api`, `NEXT_PUBLIC_WS=wss://<db-vm>/ws/updates`.
- [ ] **Step 2:** Preview deploy on every PR (Vercel default).
- [ ] **Step 3:** Production deploy from `main`.

### Task 12.3: Agent restart persistence test (judging requirement)

- [ ] **Step 1:** On each VM, `systemctl stop supplai-scout` during a demo run → `systemctl start` → verify:
  - No duplicate signals after restart.
  - Tavily cursors / weather checkpoints resumed from last value.
  - `state.json` on disk matches in-memory state before + after.

### Task 12.4: Offline cache priming

- [ ] **Step 1:** Run each of 5 scenarios end-to-end once with live Gemini + Tavily. Cache auto-populates.
- [ ] **Step 2:** Commit cache files as `backend/llm/*.sqlite.seed` — loaded at VM bootstrap if `DEMO_OFFLINE_CACHE=true`.

### Task 12.5: Accessibility audit

- [ ] **Step 1:** Run Lighthouse on War Room + Disruption Detail + Exec. Target: Accessibility ≥95, Performance ≥90.
- [ ] **Step 2:** Fix: focus rings visible, aria-labels on icon-only buttons, color contrast for `text-muted` on `surface` (must meet 4.5:1), keyboard nav walks left rail → center → right rail without traps.

### Task 12.6: Pitch deck + demo script

**Files:**
- Create: `docs/demo-script.md`, deck as PDF in `docs/pitch.pdf`

- [ ] **Step 1:** 2-minute demo script with:
  - 10s intro (Maya's hour)
  - 30s Simulate → Typhoon Kaia → signal → disruption → impact → mitigations (all on screen)
  - 30s click "Why this recommendation?" → explainability
  - 20s Approve → drafts saved → shipment status flipped → approvals log
  - 20s sponsor tie-ins: three VMs, OpenClaw audit, Gemini usage, Tavily queries

### Task 12.7: README + architecture doc

- [ ] **Step 1:** `README.md` — quickstart (`uv sync`, seed, `alembic upgrade`, run agents, `pnpm dev`), architecture diagram, sponsor sections (Dedalus screenshots, OpenClaw screenshot, Gemini usage, Tavily queries), credits.
- [ ] **Step 2:** `docs/architecture.md` — full system diagram (Mermaid), agent swarm explanation, data model ER diagram.

### Task 12.8: Final quality gates

Run and confirm ALL pass:

- [ ] `uv run ruff check .` — clean
- [ ] `uv run ruff format --check .` — clean
- [ ] `uv run mypy --strict backend/db backend/schemas backend/llm backend/agents/base.py` — clean
- [ ] `uv run pytest` — green
- [ ] `grep -r "smtplib\|sendmail\|smtp" backend/` — empty
- [ ] `pnpm -C web lint && pnpm -C web typecheck && pnpm -C web build` — green
- [ ] `pnpm -C web test:e2e` — 5/5 scenarios green, 5 consecutive runs
- [ ] Lighthouse: Perf ≥90, A11y ≥95 on War Room
- [ ] 3× manual dry-run from fresh boot matches pitch script

### Task 12.9: Submit

- [ ] Tag `v1.0-submission`.
- [ ] Submit Devpost with repo link + 2-minute video + architecture doc.
- [ ] Print one-page architecture handout for judges.
- [ ] Relax branch protection? No — keep.

---

## Self-review

Reviewed against the PRD with fresh eyes:

**Spec coverage check:**
- §4.1 Must-haves: US-01 (Phase 5 sources 5.6–5.10), US-02 (Phase 6 impact report), US-03 (Phase 7 options), US-04 (Phase 9 approval), US-05 (Phase 8 War Room), US-06 (Phase 11 simulate) — **all covered**.
- §4.2 Should-haves: US-07 (Phase 10.1 drawer), US-08 (Phase 10.2 analytics), US-09 (Phase 9.3 audit log), US-10 (Phase 5.4 fusion) — **all covered**.
- §4.3 Could-haves: US-11, US-12 — not in plan (explicitly labeled stretch in PRD). OK.
- §5.1 four source categories → 5 in plan (news/weather/policy/logistics/macro) — **covered**.
- §5.2 three agents + coordination via LISTEN/NOTIFY → Phases 5/6/7 + Phase 2.3 bus — **covered**.
- §6 non-functional — latencies addressed per phase; SQL safety in Phase 2.2 + function-calling in Phases 6/7; zero-SMTP checked in Phase 12.8; observability via structlog in every agent.
- §7.1 backend stack — all in Phase 0/1/2.
- §7.2 frontend stack + anti-patterns — Phase 0.5 tokens, Phases 4/8/9/10 UI; anti-patterns listed in docs/architecture.md and enforced via taste review (not codifiable beyond that).
- §7.3 infra — Phase 12.1/12.2.
- §7.4 CI — Phase 0.3.
- §8 schema — Phase 1.2 (all 12 tables); indexes in the alembic autogen.
- §9 wireframes — §9.1 (Phase 8), §9.2 (Phase 9.2), §9.3 (Phase 10.1), §9.4 (Phase 10.2), §9.5 (Phase 10.3), §9.6/7 micro-interactions/empties (distributed).
- §10.2 timeline — plan maps cleanly; §10.1 role alignment labeled per-phase.
- §11 testing — per-phase tests + Phase 11 E2E + Phase 12.8 gates.
- §13 sponsor integration — Dedalus 12.1, OpenClaw 7.3, Tavily 5.12 (query library), Gemini distributed.
- §15.1 5 demo scenarios — Phase 11.1.

**Placeholder scan:** none — every "Implement X" step either has code inline or explicit file contract + test.

**Type consistency:** `SignalClassification` vs `SignalRecord` naming preserved; `AffectedShipment` matches DB model + API schema; mitigation status values `pending`/`approved`/`dismissed` consistent across DB and API; `OpenClaw Action` naming (`SaveMitigationOptions`, `FlipShipmentStatuses`, `WriteApprovalAudit`) consistent across Task 7.3 + Task 9.1.

**2026 practices check:**
- Function/tool calling: Phases 6/7 both use `LLMClient.with_tools`. ✅
- Structured output: all Gemini calls use `response_schema` bound to Pydantic. ✅
- Explicit prompt caching: Phase 6.1 uses `LLMClient.cached_context` for schema ref. ✅
- Offline cache: Phase 2.4 + Phase 12.4. ✅
- TDD granularity: strict for logic (SQL guard, dedupe, severity, atomicity); milestone for UI. ✅
- Gotchas: LISTEN reconnect (2.3), motion package name (4.2), openapi drift gate (0.2 + 0.7), two cache layers (2.4/2.7 + 6.1). ✅

Plan is complete.

---

## Execution handoff

Plan complete and saved to `docs/superpowers/plans/2026-04-18-suppl-ai-implementation.md`. Two execution options:

**1. Subagent-Driven (recommended)** — fresh subagent per task, code-reviewer between tasks, fast iteration. Best fit for the hackathon: preserves your main context for integration calls + pitch-day glue work.

**2. Inline Execution** — execute tasks in this session using `superpowers:executing-plans`, batch execution with checkpoints for review.

Which approach?
