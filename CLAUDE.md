# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**suppl.ai** — agentic supply chain crisis-management dashboard for HackPrinceton Spring '26. A three-agent swarm (Scout, Analyst, Strategist) monitors global supply chain signals, assesses impact, and drafts mitigations for one-click human approval. Not a chatbot — an operator war room.

## Monorepo Structure

```
backend/          # Python 3.12 agents + FastAPI
  agents/
    scout/        # Monitors signals (news, weather, policy, logistics, macro)
    analyst/      # Impact assessment via text-to-SQL
    strategist/   # Mitigation drafting + DB action layer (OpenClaw)
  api/            # FastAPI HTTP/WebSocket layer
  db/             # SQLAlchemy models, Alembic migrations
  scripts/        # seed.py (idempotent, rerunnable)
web/              # Next.js 15 (App Router) + TypeScript
  app/
    (dashboard)/  # War Room, disruption detail, analytics, exec view
  components/
    ui/           # shadcn primitives, heavily customized
    disruption/
    mitigation/
    map/
    agent-activity/
    charts/
  lib/            # api-client.ts, ws-client.ts, store.ts (Zustand)
  types/          # Generated from FastAPI OpenAPI schema via openapi-typescript
```

## Commands

### Backend
```bash
uv sync                          # install deps (use uv, not pip)
uv run ruff check .              # lint
uv run ruff format .             # format
uv run mypy --strict backend/db backend/api/schemas  # typecheck shared modules
uv run pytest                    # all tests
uv run pytest tests/test_foo.py  # single test file
uv run pytest -k "test_name"     # single test by name
uv run alembic upgrade head      # run migrations
uv run python scripts/seed.py    # seed demo data (idempotent)
```

### Frontend
```bash
pnpm install
pnpm dev          # dev server
pnpm lint         # ESLint
pnpm typecheck    # tsc --noEmit
pnpm build        # production build
pnpm test:e2e     # Playwright e2e (requires running backend)
```

## Architecture

### Agent Communication Pattern
Agents communicate **only through Postgres** — no direct RPC between agents. Event bus is `pg LISTEN/NOTIFY` on channels: `new_signal`, `new_disruption`, `new_impact`, `new_mitigation`, `new_approval`. This is the "swarm discipline" — enforce it rigorously.

### Agent Structure (each agent follows this)
```
agents/<name>/
  main.py          # entrypoint, asyncio event loop
  config.py        # pydantic-settings env vars
  sources/         # Scout only: one module per signal category
  processors/      # pure functions → test these at 70%+ coverage
  prompts/         # prompt templates as .md files (versioned, diff-friendly)
  state.py         # checkpoint r/w to /var/lib/supplai/state.json
  tests/
```

### Scout Agent
- 5 parallel `asyncio` tasks, each on its own cadence (news 60s, weather 5min, policy 15min, logistics 10min, macro 30min)
- Uses Gemini Flash for classification (high-volume, cheap)
- Dedupes by `{region, category, keyword hash}` within 72h
- Signal fusion: two related low-severity signals → one higher-severity disruption

### Analyst Agent
- Triggered by `new_disruption` LISTEN events
- Text-to-SQL: Gemini Pro generates SQL from disruption context + full schema
- **SQL safety critical**: validator must reject everything that isn't a single `SELECT`. Forbidden: `DROP`, `DELETE`, `UPDATE`, `INSERT`, `ALTER`, `TRUNCATE`, `GRANT`, statement terminators mid-query. On reject: retry with error context (max 3), then fall back to rules-based template keyed on disruption category.
- Stores `sql_executed` + `reasoning_trace` JSONB in `impact_reports` for explainability

### Strategist Agent
- Triggered by `new_impact` events
- Uses OpenClaw for all DB mutations (supplier lookup, draft_communications writes, shipment status flips, audit log entries) — this is a judging requirement (Eragon rubric)
- Uses Gemini Pro for multi-step reasoning
- **Never sends email**: `draft_communications.sent_at` is always NULL; zero SMTP libraries allowed in deps

### FastAPI Layer
Key routes:
```
GET  /api/signals?status=active
GET  /api/disruptions/:id/impact
GET  /api/disruptions/:id/mitigations
POST /api/mitigations/:id/approve      # flips shipment status, logs approval
POST /api/dev/simulate                 # demo trigger (5 pre-scripted scenarios)
WS   /ws/updates                       # live push to dashboard
```

### Database
- Postgres 16, async via asyncpg (agents) + SQLAlchemy async (API)
- All agent writes use `ON CONFLICT DO NOTHING` or content-hash dedupe for idempotency
- Agent checkpoint state lives on VM filesystem at `/var/lib/supplai/state.json`
- Approval action mutates: shipment `status → "rerouting"`, inserts into `approvals` table with `state_snapshot` JSONB

### Frontend State
- **Server state**: TanStack Query (cache, optimistic updates)
- **Client state**: Zustand store at `lib/store.ts`
- **API types**: generated from FastAPI OpenAPI via `openapi-typescript`; validated at runtime with zod
- **WebSocket**: `lib/ws-client.ts` subscribes to `new_signal`, `new_disruption`, etc. for live updates

## Design System

Design tokens are defined in `web/app/globals.css` as CSS variables. Key values:
- Background: `#0A0B0D`, Surface: `#111316`, Text: `#E8EAED`
- Category accents: weather `#5E81AC`, policy `#B48EAD`, news `#A3BE8C`, logistics `#EBCB8B`, macro `#D08770`
- Status: critical `#E5484D`, warn `#D97757`, ok `#46A758`
- 4px spacing base, tight type scale (11–44px), Inter + JetBrains Mono

**Aesthetic target**: Linear / Vercel / Stripe — calm, dense, details-obsessed. All dollar figures and IDs use `font-feature-settings: 'tnum'` to prevent layout jitter during live updates.

**Forbidden UI patterns**: purple-to-pink gradients, generic glassmorphism, emoji in headers/nav, default shadcn card+button stacks, drop shadows on flat elements, "AI" badges/sparkle icons, spinner loading states (use skeleton screens).

## Animation Principles
- Spring physics for entrances (`stiffness: 260, damping: 26`), `ease-out` for exits
- Duration: 120–320ms only
- New signal card: slides in from left with spring
- Approval: button collapses → morphs into approvals log entry via Motion `layoutId`
- Always respect `prefers-reduced-motion` (animations become instant)

## LLM Integration
- Direct `google-generativeai` SDK — no LangChain
- Prompts in versioned `.md` files in each agent's `prompts/` directory
- Offline fallback: cache `(prompt_hash, model_output)` in SQLite per VM
- All model outputs parsed into Pydantic models; invalid output → one retry with error context

## Quality Gates (must pass before submission)
- `ruff` + `mypy --strict` clean on shared modules
- Zero SQL mutations possible through Analyst path
- Zero SMTP imports in codebase (`grep smtplib` returns empty)
- E2E Playwright: all 5 simulate scenarios complete in ≤ 60s
- Lighthouse Performance ≥ 90, Accessibility ≥ 95 on War Room

## External Services
- **Gemini API** (Flash for Scout, Pro for Analyst/Strategist)
- **Tavily API** (news, policy, logistics, macro search)
- **Open-Meteo** (weather, no auth)
- Dedalus Machines: `scout-vm`, `analyst-vm`, `strategist-vm`, `db-vm`
- Frontend on Vercel; DB on Dedalus or Neon (decide in first hour by latency test)
