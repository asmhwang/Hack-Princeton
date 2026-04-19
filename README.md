# suppl.ai

**Agentic supply-chain war-room for HackPrinceton Spring '26.**

When the next disruption hits — typhoon, tariff, strike, fire — a logistics manager won't spend six hours in Excel. She'll approve a drafted mitigation in sixty seconds, because three agents already did the work.

suppl.ai continuously monitors the world across news, weather, policy, logistics feeds, and macro signals, joins those signals against a live inventory and logistics database, and proactively drafts mitigation strategies — reroutes, alternate suppliers, customer communications — for one-click human approval.

**Differentiator.** Existing supply-chain visibility tools *show you* what's happening. suppl.ai *acts on it*. The difference between a weather app and an autopilot.

**Live demo:** https://suppl-ai-seven.vercel.app (frontend). Requires the backend to be reachable via a public HTTPS URL set in `NEXT_PUBLIC_API_BASE_URL` — see [Vercel deploy](#vercel-deploy).

## Architecture

Three coordinated Python agents running as separate Dedalus Machines, communicating only through Postgres (`LISTEN/NOTIFY`). No RPC between agents — swarm discipline.

```
┌──────────────────┐       ┌──────────────────┐       ┌──────────────────┐
│ Scout VM         │       │ Analyst VM       │       │ Strategist VM    │
│ (scout-vm)       │       │ (analyst-vm)     │       │ (strategist-vm)  │
│                  │       │                  │       │                  │
│ 5 parallel tasks │       │ Gemini Pro       │       │ Gemini Pro       │
│ Tavily + Weather │       │ function-calling │       │ OpenClaw actions │
│ Gemini Flash     │       │ tool loop        │       │ 3 draft comms    │
│ classifier       │       │                  │       │                  │
└────────┬─────────┘       └────────┬─────────┘       └────────┬─────────┘
         │ writes                   │ writes                   │ writes
         ▼                          ▼                          ▼
┌──────────────────────────────────────────────────────────────────────┐
│                     Postgres 16 (db-vm / Neon)                        │
│                                                                       │
│  signals → disruptions → impact_reports → mitigation_options         │
│                          affected_shipments   draft_communications    │
│                                               approvals               │
│                                                                       │
│  LISTEN/NOTIFY channels:                                              │
│  new_signal → new_disruption → new_impact → new_mitigation → approval │
└──────────────────────┬────────────────────────────────────────────────┘
                       │
                       ▼
              ┌────────────────┐
              │ FastAPI + WS   │
              │ relay (db-vm)  │
              └────────┬───────┘
                       │ /ws/updates + /api/*
                       ▼
              ┌────────────────┐
              │ Next.js 15     │
              │ War Room UI    │
              │ (Vercel)       │
              └────────────────┘
```

**Why agents, not a dashboard.** A traditional dashboard requires the human to ask the right question. A disruption cascade (event → port closure → supplier delay → customer SLA breach) requires the system to proactively reason across domains. Exactly the class of problem agents solve: continuous monitoring, multi-source reasoning, drafted actions.

## Quickstart

```bash
# Clone
git clone git@github.com:asmhwang/Hack-Princeton.git && cd Hack-Princeton

# Backend deps (Python 3.12 + uv)
uv sync --all-groups

# Dev Postgres (one teammate hosts; the others run their own identical container)
docker run --name supplai-pg \
  -e POSTGRES_PASSWORD=postgres -e POSTGRES_DB=supplai \
  -p 5432:5432 -d postgres:16

# Migrate + seed
uv run alembic upgrade head
uv run python -m backend.scripts.seed     # 30 ports / 50 suppliers / 40 SKUs / 200 POs / 500 shipments

# API keys (from shared 1Password vault)
cp .env.example .env.local
$EDITOR .env.local                          # fill GEMINI_API_KEY + TAVILY_API_KEY

# Backend (FastAPI + WebSocket)
uv run uvicorn backend.api.main:app --reload    # http://localhost:8000

# Frontend
pnpm -C web install
pnpm -C web dev --turbopack                     # http://localhost:3000
```

Fire a demo scenario end-to-end:

```bash
curl -X POST localhost:8000/api/dev/simulate \
  -H 'content-type: application/json' \
  -d '{"scenario":"typhoon_kaia"}'
```

## Project structure

```
backend/
  agents/
    scout/          # news, weather, policy, logistics, macro — Gemini Flash classifier
    analyst/        # Gemini Pro function-calling → impact report
    strategist/     # Gemini Pro → mitigation options + 3 drafts per option (OpenClaw)
    base.py         # shared lifecycle + LISTEN/NOTIFY reconnect + checkpoint
  api/
    main.py         # FastAPI app factory
    routes/         # signals / disruptions / mitigations / analytics / activity / dev
    _approval.py    # atomic approval transaction (all-or-nothing)
    validators/
      sql_guard.py  # single-SELECT defense-in-depth (token-level)
  db/
    models.py       # SQLAlchemy 2.x async, 14 tables
    session.py
    bus.py          # LISTEN/NOTIFY with auto-reconnect+resubscribe
    migrations/     # Alembic
  llm/
    client.py       # Gemini wrapper: structured output + tool-calling + caching
    tools/
      analyst_tools.py   # 7 parameterized query tools exposed via function-calling
  schemas/          # Pydantic v2 contracts (from-attributes + extra="forbid")
  scripts/
    seed.py         # idempotent, deterministic (Random(42))
    scenarios/      # 5 demo scenarios (typhoon_kaia, busan_strike, cbam_tariff,
                    #                    luxshare_fire, redsea_advisory)
  tests/            # pytest-asyncio; runs against supplai_test DB (auto-TRUNCATEd)

web/
  app/
    (dashboard)/    # War Room, disruption detail, analytics, exec
    globals.css     # full design-token set (no shadcn defaults leaking through)
  components/
    ui/             # heavily customized shadcn primitives
    disruption/  mitigation/  map/  agent-activity/  charts/  skeletons/
  lib/
    api-client.ts   # typed fetch + zod runtime validation
    ws-client.ts
    store.ts        # Zustand
  types/
    api.ts          # generated from FastAPI OpenAPI via openapi-typescript
  tests/e2e/        # Playwright — 5 scenarios × full pipeline

docs/
  superpowers/plans/
    2026-04-18-suppl-ai-implementation.md       # master plan (source of truth)
    2026-04-18-parallel-coordination.md         # team partition, contract freeze
    2026-04-18-plan-A-agents-infra.md           # Teammate A ownership
    2026-04-18-plan-B-frontend.md               # Teammate B ownership
    2026-04-18-plan-C-api-demo.md               # Teammate C ownership
  runbook.md                                    # env setup, blocked deps
```

## Vercel deploy

Frontend is deployed from `web/` (project linked via `vercel link`; `web/vercel.json` + `web/.env.example` checked in). Backend has no dedicated API VM in the current infra plan, so the Vercel site needs a public HTTPS URL for the FastAPI backend. For the hackathon demo, we tunnel the local backend with ngrok.

```bash
# Terminal 1 — FastAPI
uv run uvicorn backend.api.main:app --port 8000

# Terminal 2 — public tunnel
brew install ngrok                        # one-time
ngrok config add-authtoken <authtoken>    # one-time
ngrok http 8000                           # prints https://<id>.ngrok-free.app

# Terminal 3 — point Vercel at the tunnel
cd web
vercel env rm NEXT_PUBLIC_API_BASE_URL production -y   # skip if first time
vercel env add NEXT_PUBLIC_API_BASE_URL production     # paste https://<id>.ngrok-free.app (no path, no trailing slash)
vercel --prod
```

Do NOT set `NEXT_PUBLIC_WS_URL` separately — `web/lib/ws-client.ts` auto-derives `wss://<host>/ws/updates` from the base URL. Setting both double-appends the path.

Free-tier ngrok URLs change on restart; re-run `env rm` + `env add` + `vercel --prod` when the tunnel resets.

## Commands reference

### Backend

```bash
uv sync                          # install deps (use uv, not pip)
uv run ruff check .              # lint
uv run ruff format .             # format
uv run mypy --strict backend/db backend/schemas backend/llm backend/agents/base.py
uv run pytest                    # all tests
uv run pytest -k "approval"      # filter
uv run alembic upgrade head      # run migrations
uv run alembic downgrade -1      # roll back one revision
uv run python -m backend.scripts.seed          # idempotent seed
uv run python -m backend.agents.scout.main     # Scout agent (long-running)
```

### Frontend

```bash
pnpm -C web install
pnpm -C web dev --turbopack       # dev server
pnpm -C web lint                  # ESLint
pnpm -C web typecheck             # tsc --noEmit
pnpm -C web build                 # production build
pnpm -C web openapi:gen           # regen web/types/api.ts from live /openapi.json
pnpm -C web openapi:check         # assert TS types match live schema (pre-commit)
pnpm -C web test:e2e              # Playwright (backend + agents must be running)
```

## Parallel development

Three teammates, three partitioned tracks (see `docs/superpowers/plans/2026-04-18-parallel-coordination.md`):

| Plan | Owner | Charter |
|---|---|---|
| **A** | Agents & Infra | 3 agent processes, event bus, Gemini integration, Dedalus VMs |
| **B** | Frontend & UX | Next.js dashboard, 5 screens, map, animations, a11y |
| **C** | API, Demo & Glue | Pydantic schemas, FastAPI, SQL safety, demo scenarios, E2E, docs |

**Contract freeze points** (do not change without coordinating):
- Pydantic schemas under `backend/schemas/*` (shared contract)
- `LISTEN/NOTIFY` channel names + JSON payload shapes
- Demo scenario IDs: `typhoon_kaia`, `busan_strike`, `cbam_tariff`, `luxshare_fire`, `redsea_advisory`
- OpenAPI → TypeScript codegen pipeline (pre-commit hook catches drift)

**Branching:** `main` is integration. Feature branches named `<track>/<feature>` (e.g. `c/sql-guard`, `a/event-bus`, `b/war-room`). PR into `main`; CI must be green.

## Demo scenarios

Five pre-baked scenarios trigger the full agent cascade via `POST /api/dev/simulate`. Used for live judging + Playwright E2E.

| ID | Category | Epicenter | Expected $ exposure | Dominant mitigation |
|---|---|---|---|---|
| `typhoon_kaia` | weather (Cat 3) | Shenzhen | $1.8M-$2.8M | reroute via HCM |
| `busan_strike` | logistics (72h) | Busan | $1.1M-$1.7M | reroute to Kaohsiung |
| `cbam_tariff` | policy | EU | $350K-$700K | switch compliant supplier |
| `luxshare_fire` | industrial | Bắc Giang | $700K-$1.1M | activate backup supplier |
| `redsea_advisory` | logistics | Bab-el-Mandeb | $2.7M-$3.5M | accept delays / expedite air |

Scenario fixtures live in `backend/scripts/scenarios/`.

## Sponsor integrations

### Dedalus Labs

Three long-running Python processes, each on its own Dedalus Machine (`scout-vm`, `analyst-vm`, `strategist-vm`), plus `db-vm` hosting Postgres + FastAPI. Each agent persists checkpoint state (Tavily cursors, last-seen hashes, prompt cache) to `/var/lib/supplai/state.json`. `systemctl stop + start` resumes cleanly — this is what the "needs a real OS" narrative rests on.

Systemd unit files in `infra/` (courtesy of Plan A). Provisioning credits claimed at https://dedaluslabs.ai/hackprinceton-s26.

#### Three VMs running live

Bring the swarm up end-to-end with three commands:

```bash
# 1. Provision 4 Machines (idempotent; reuses existing by name)
export DEDALUS_API_KEY=...
uv run python infra/provision.py                # writes infra/machines.json

# 2. Deploy each agent (rsync + systemctl enable --now)
./infra/scripts/deploy.sh scout-vm scout
./infra/scripts/deploy.sh analyst-vm analyst
./infra/scripts/deploy.sh strategist-vm strategist

# 3. Verify /health on every VM (exit 0 iff all green)
uv run python scripts/smoke.py --inventory infra/machines.json
```

Sample output:

```
NAME         URL                              STATUS  OK    NOTE
scout        http://scout-vm:9101/health      200     yes
analyst      http://analyst-vm:9102/health    200     yes
strategist   http://strategist-vm:9103/health 200     yes
api          http://db-vm:8000/health         200     yes
```

**Judging gate — restart persistence (Task 12.3):**

```bash
uv run python scripts/restart_persistence_test.py --inventory infra/machines.json
```

Stops + starts each agent via `systemctl restart supplai-<agent>`, asserts the
on-disk `state.json` is byte-identical across the restart, and then waits 30s
to confirm no duplicate `content_hash` rows landed in `signals` — i.e. the
agent resumed from the checkpoint cursor instead of replaying history.

> Screenshot: `docs/screenshots/three-vms-live.png` (capture from the Dedalus
> dashboard once provisioned; showing 4 green Machines — scout, analyst,
> strategist, db).

### Eragon — OpenClaw

Strategist wraps every DB mutation — supplier lookups, `draft_communications` writes, shipment status flips, audit log entries — in OpenClaw `Action` primitives (see `annyzhou/openclaw-ddls` reference). This is the judging requirement: "not chat; real work."

Rubric mapping:
- **Depth of Action (30%)** — approvals mutate DB, prepare real email bodies (saved, never sent), log audits.
- **Context Quality (30%)** — Strategist joins signals + disruptions + impact reports + suppliers + customers + shipments + POs. Seven sources.
- **Workflow Usefulness (40%)** — Maya persona carried end-to-end: "Monday morning, typhoon hit, she approves three mitigations before her first coffee."

### MLH — Gemini API

- **Flash** (cheap, high-volume): Scout classifier — one call per raw signal.
- **Pro** (reasoning): Analyst tool-calling loop (impact report) + Strategist drafting (options + 3 comms per option).

All calls use Gemini 2.x `response_schema` for structured output (Pydantic-bound) + function-calling for DB reads (no raw text-to-SQL). Explicit `cached_contents` for the reusable schema reference. Offline SQLite cache `(prompt_hash, model_output)` for demo robustness if network drops.

### Tavily

Scout's primary search layer for 4 of 5 source categories (news, policy, logistics, macro). Tuned query library documented in `backend/agents/scout/sources/tavily_queries.md`.

## Safety gates

1. **Zero SQL mutations possible.** Analyst uses Gemini function-calling with a fixed set of parameterized read tools (`backend/llm/tools/analyst_tools.py`) — not raw text-to-SQL. Defense-in-depth: any synthesized SQL string is passed through `sql_guard.validate_select_only()` before being persisted to `impact_reports.sql_executed`. Validator rejects non-SELECT, forbidden keywords, multi-statement, comment-hidden injection, DoS functions (`pg_sleep`, `pg_advisory_lock`, `dblink`, `lo_import`, etc.).
2. **Zero emails sent.** `draft_communications.sent_at` is always NULL — enforced by Pydantic validator. Zero SMTP libraries in the dependency graph (`grep -r 'smtplib\|sendmail' backend/` returns empty).
3. **Atomic approvals.** `POST /api/mitigations/:id/approve` flips shipment statuses + writes audit + flips mitigation status + NOTIFYs — all or nothing. Mid-transaction failure leaves zero partial state (tested).
4. **Idempotent writes.** Every agent insert uses `ON CONFLICT DO NOTHING` or content-hash dedupe. Restart-safe.
5. **Event bus auto-reconnect.** Postgres `LISTEN/NOTIFY` drops silently on connection loss — `backend/db/bus.py` has an explicit reconnect+resubscribe loop.

## Quality gates (must pass before submission)

- [x] `uv run ruff check .` + `uv run ruff format --check .` clean
- [x] `uv run mypy --strict backend/db backend/schemas backend/llm backend/agents/base.py` clean
- [x] `uv run pytest` green
- [x] `grep -r "smtplib\|sendmail\|smtp" backend/` empty (only `tests/test_no_smtp.py` guard)
- [x] `pnpm -C web lint && pnpm -C web typecheck && pnpm -C web build` green
- [ ] `pnpm -C web test:e2e` — 5/5 scenarios, 5 consecutive runs (only smoke spec shipped; full C.9 suite pending)
- [x] Lighthouse Performance ≥90, Accessibility ≥95 on War Room (Perf 92 · A11y 100)
- [ ] 3× manual dry-run matches pitch script

## Design system

Design tokens live in `web/app/globals.css`. Aesthetic target: Linear / Vercel / Stripe — calm, dense, details-obsessed. See `web/CLAUDE.md` for forbidden patterns (no purple gradients, no default shadcn stacks, no AI sparkle icons) and required ones (tabular numerics, skeleton screens, spring physics, `prefers-reduced-motion` instant override).

## Contributing

This project is built for HackPrinceton Spring '26. Not actively maintained after submission.

Development workflow:

1. Read your plan file in `docs/superpowers/plans/` (A, B, or C).
2. Branch off `main`: `git checkout -b <track>/<feature>`.
3. Write tests first where the plan says strict TDD (SQL guard, event bus, approval atomicity, LLM parsing).
4. Open PR → green CI → merge → delete branch.

## License

Unlicensed — hackathon submission only.
