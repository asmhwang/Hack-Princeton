# suppl.ai

**Agentic supply-chain war-room for HackPrinceton Spring '26.**

When the next disruption hits — typhoon, tariff, strike, fire — a logistics
manager won't spend six hours in Excel. She'll approve a drafted mitigation in
sixty seconds, because three agents already did the work.

suppl.ai monitors the world across news, weather, policy, logistics, and
macro signals, joins those signals against a live inventory and logistics
database, and proactively drafts mitigation strategies — reroutes, alternate
suppliers, customer communications — for one-click human approval.

**Differentiator.** Existing supply-chain visibility tools *show you* what's
happening. suppl.ai *acts on it*. Difference between a weather app and an
autopilot.

**Live demo:** https://suppl-ai-seven.vercel.app

## Architecture

Three-agent design — Scout (signal intake), Analyst (impact assessment),
Strategist (mitigation drafting). Agents communicate only through Postgres
(`LISTEN/NOTIFY`) — no direct RPC. Swarm discipline.

```
Signals (5 categories)            Disruptions       Impact + Mitigation
   │                                  │                     │
   ▼                                  ▼                     ▼
┌─────────┐  promotes   ┌──────────────┐    NOTIFY    ┌──────────────┐
│ Scout   │ ─────────►  │ Disruption   │ ──────────►  │ Analyst      │
│ Gemini  │             │ row + map    │              │ Gemini Pro   │
│ Flash   │             │ pin          │              │ tool-calling │
└─────────┘             └──────────────┘              └──────┬───────┘
                                                             │
                                                             ▼
                              ┌──────────────────┐    ┌──────────────┐
                              │ Approvals + WS   │ ◄─ │ Strategist   │
                              │ to dashboard     │    │ + OpenClaw   │
                              └──────────────────┘    └──────────────┘
```

For the hackathon demo, `POST /api/dev/simulate` writes the full inline
cascade (Signal → Disruption → ImpactReport → AffectedShipments →
MitigationOptions → DraftCommunications) so judges see the end-to-end story
in <1s without waiting on live agent loops.

## Stack

- **Backend** — Python 3.12, FastAPI, SQLAlchemy 2.x async, asyncpg, Pydantic v2
- **Database** — Postgres 16 (Neon serverless)
- **LLMs** — Gemini Flash (Scout classifier) + Gemini Pro (Analyst tool loop, Strategist drafting)
- **Frontend** — Next.js 16 + React 19 + Turbopack, Zustand, TanStack Query, Motion, react-globe.gl
- **Hosting** — Vercel (frontend), local uvicorn for backend (ngrok tunnel for the public demo)

## Quickstart

```bash
git clone git@github.com:asmhwang/Hack-Princeton.git && cd Hack-Princeton

# Backend deps
uv sync

# Env: copy template and fill in
cp .env.example .env
$EDITOR .env
# Required:
#   DATABASE_URL=postgresql+asyncpg://USER:PASS@<host>.neon.tech/dbname?ssl=require
#   GEMINI_API_KEYS=key1[,key2,...]   # comma-separated for rotation

# One-time DB setup (against Neon)
set -a; source .env; set +a
uv run alembic upgrade head
uv run python -m backend.scripts.seed   # 30 ports / 50 suppliers / 200 POs / 500 shipments

# Backend
uv run uvicorn backend.api.main:app --reload --port 8000   # http://localhost:8000

# Frontend (separate terminal)
pnpm -C web install
pnpm -C web dev                                            # http://localhost:3000
```

Fire a scenario via curl:

```bash
curl -X POST localhost:8000/api/dev/simulate \
  -H 'content-type: application/json' \
  -d '{"scenario":"typhoon_kaia"}'
```

Or click any scenario card in the UI.

## Demo scenarios

Five pre-baked scenarios trigger the full agent cascade through
`POST /api/dev/simulate`:

| ID                 | Category        | Epicenter        | Exposure         | Dominant mitigation        |
|--------------------|-----------------|------------------|------------------|----------------------------|
| `typhoon_kaia`     | weather (Cat 3) | Shenzhen         | $1.8M – $2.8M    | reroute via Ho Chi Minh    |
| `busan_strike`     | logistics (72h) | Busan            | $1.1M – $1.7M    | reroute to Kaohsiung       |
| `cbam_tariff`      | policy          | EU               | $350K – $700K    | switch compliant supplier  |
| `luxshare_fire`    | industrial      | Bắc Giang        | $700K – $1.1M    | activate backup supplier   |
| `redsea_advisory`  | logistics       | Bab-el-Mandeb    | $2.7M – $3.5M    | accept delays / expedite   |

Fixtures live in `backend/scripts/scenarios/`.

## Vercel deploy

The frontend is deployed from `web/` (Vercel project root directory =
`web`). The Vercel site needs a public HTTPS URL for the FastAPI backend —
for the hackathon we tunnel local uvicorn with ngrok.

```bash
# Terminal 1 — backend
set -a; source .env; set +a
uv run uvicorn backend.api.main:app --port 8000

# Terminal 2 — public tunnel
brew install ngrok                       # one-time
ngrok config add-authtoken <token>       # one-time
ngrok http 8000                          # prints https://<id>.ngrok-free.app

# Terminal 3 — point Vercel at the tunnel
cd web
vercel env rm NEXT_PUBLIC_API_BASE_URL production -y   # skip if first time
vercel env add NEXT_PUBLIC_API_BASE_URL production     # paste https://<id>.ngrok-free.app
vercel --prod
```

Do NOT set `NEXT_PUBLIC_WS_URL` separately — `web/lib/ws-client.ts` derives
`wss://<host>/ws/updates` from the base URL automatically.

Free-tier ngrok URLs change on restart; re-run the env update + `vercel --prod`
when the tunnel resets.

## Project structure

```
backend/
  agents/
    scout/       # 5 source pollers, Gemini Flash classifier
    analyst/     # Gemini Pro function-calling → impact report
    strategist/  # Gemini Pro → mitigation options + 3 drafts (OpenClaw)
    base.py      # shared lifecycle, LISTEN/NOTIFY reconnect, checkpoint
  api/
    main.py
    routes/      # signals / disruptions / mitigations / analytics / activity / dev
    _approval.py # atomic approval transaction
    validators/sql_guard.py   # single-SELECT defense-in-depth
  db/
    models.py    # SQLAlchemy 2.x async, 14 tables
    session.py
    bus.py       # LISTEN/NOTIFY with auto-reconnect+resubscribe
    migrations/  # Alembic
  llm/
    client.py    # Gemini wrapper: structured output + tool-calling + caching
    tools/analyst_tools.py    # 7 parameterized read tools for the Analyst loop
  schemas/       # Pydantic v2 contracts
  scripts/
    seed.py      # idempotent, deterministic (Random(42))
    scenarios/   # 5 demo fixtures
  tests/         # pytest-asyncio against supplai_test DB

web/
  app/(dashboard)/   # War Room, disruption detail, analytics, exec
  components/        # ui / disruption / mitigation / map / agent-activity / charts
  lib/api-client.ts  # typed fetch + zod runtime validation
  lib/ws-client.ts   # WS subscriber with auto-reconnect
  lib/store.ts       # Zustand
  types/api.ts       # generated from FastAPI OpenAPI via openapi-typescript
  tests/e2e/         # Playwright

docs/
  runbook.md
  superpowers/{plans,specs}/  # implementation plans + design specs
```

## Sponsor integrations

### Eragon — OpenClaw

Strategist wraps every DB mutation — supplier lookups,
`draft_communications` writes, shipment status flips, audit log entries — in
OpenClaw `Action` primitives. Approvals mutate DB + log audits + prepare real
email bodies (saved, never sent). "Not chat; real work."

### MLH — Gemini API

- **Flash** (cheap, high-volume): Scout classifier — one call per raw signal.
- **Pro** (reasoning): Analyst tool-calling loop + Strategist drafting.

All calls use Gemini 2.x `response_schema` for structured output (Pydantic-bound)
+ function-calling for DB reads (no raw text-to-SQL). Explicit cached prompts.
Offline SQLite cache `(prompt_hash, model_output)` for demo robustness.

### Tavily

Scout's primary search layer for 4 of 5 source categories (news, policy,
logistics, macro).

## Safety gates

1. **Zero SQL mutations.** Analyst uses Gemini function-calling with a fixed
   set of parameterized read tools — not raw text-to-SQL. Defense-in-depth:
   any synthesized SQL string is passed through `sql_guard.validate_select_only()`
   before persistence. Validator rejects non-SELECT, forbidden keywords,
   multi-statement, comment-hidden injection, and DoS functions
   (`pg_sleep`, `dblink`, `lo_import`, etc.).
2. **Zero emails sent.** `draft_communications.sent_at` is always NULL —
   enforced by Pydantic validator. No SMTP library in the dependency graph
   (`grep -r 'smtplib\|sendmail' backend/` returns empty).
3. **Atomic approvals.** `POST /api/mitigations/:id/approve` flips shipment
   statuses + writes audit + flips mitigation status + NOTIFYs in one
   transaction. Mid-transaction failure leaves zero partial state.
4. **Idempotent writes.** Every agent insert uses `ON CONFLICT DO NOTHING`
   or content-hash dedupe. Restart-safe.
5. **Event bus auto-reconnect.** `backend/db/bus.py` reconnects + resubscribes
   on Postgres `LISTEN/NOTIFY` connection loss.

## Commands reference

### Backend

```bash
uv sync                               # install deps
uv run ruff check .                   # lint
uv run ruff format .                  # format
uv run mypy --strict backend/db backend/api/schemas
uv run pytest                         # all tests
uv run pytest -k "approval"           # filter
uv run alembic upgrade head           # migrations
uv run python -m backend.scripts.seed
```

### Frontend

```bash
pnpm -C web install
pnpm -C web dev                       # Turbopack dev server
pnpm -C web lint
pnpm -C web typecheck                 # tsc --noEmit
pnpm -C web build
pnpm -C web openapi:gen               # regen web/types/api.ts from /openapi.json
pnpm -C web test:e2e                  # Playwright
```

## Design system

Design tokens live in `web/app/globals.css`. Aesthetic target: Linear /
Vercel / Stripe — calm, dense, details-obsessed. See `web/CLAUDE.md` for
forbidden patterns (no purple gradients, no default shadcn stacks, no AI
sparkle icons) and required ones (tabular numerics, skeleton screens, spring
physics, `prefers-reduced-motion` instant override).

## License

Unlicensed — hackathon submission only.
