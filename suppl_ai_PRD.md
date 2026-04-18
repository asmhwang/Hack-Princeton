# suppl.ai — Product Requirements Document (PRD)

**Project:** suppl.ai — Agentic Supply Chain War Room
**Event:** HackPrinceton Spring '26 (April 17–19, 2026)
**Team size:** 3
**Industry focus:** Horizontal / general-purpose (any enterprise with global logistics exposure)
**Scope tier:** Ambitious (multi-source monitoring, multi-disruption, approval workflows, analytics)
**Document version:** 2.0
**Author:** Product lead (with Claude)

---

## 1. Executive Summary

suppl.ai is an agentic crisis-management dashboard for enterprise supply chain managers. It continuously monitors the world across news, weather, policy decisions, logistics feeds, and macro signals, joins those signals against a live inventory and logistics database, and proactively drafts mitigation strategies — reroutes, alternate suppliers, customer communications — that a human manager approves with one click.

The product replaces hours of frantic tab-switching during a crisis with a single war-room view that quantifies exposure in dollars, recommends specific actions with tradeoffs, and prepares approved actions for execution.

**Core differentiator:** Existing supply chain visibility tools (FourKites, project44) *show you* what's happening. suppl.ai *acts on it*. The difference between a weather app and an autopilot.

**Hackathon judging thesis:** The architecture is a genuine multi-agent swarm (Scout, Analyst, Strategist) with persistent state, running as coordinated Dedalus Machines — not three prompts to one LLM. Every mitigation carries an explainability trail: the source signals, the SQL query, the supplier scores that produced it.

---

## 2. Problem Statement & Context

### 2.1 The problem
When a supply chain event hits — a typhoon makes landfall, a major port goes on strike, a government announces new tariffs, a key supplier's plant catches fire — a logistics manager faces a chaotic hour of work:

1. Learns about the event from news, Slack, or a frantic call
2. Opens ERP / TMS to check which shipments are in the affected region
3. Opens a spreadsheet to cross-reference affected SKUs to customer POs and SLAs
4. Opens a supplier relationship tool to find alternates
5. Opens email to draft reroute requests, customer notifications, and internal escalations
6. Opens a finance tool or manually estimates the financial hit

This takes 2–6 hours for a major event. During that window, the disruption compounds, mitigation capacity gets booked by competitors, and customer SLAs tick toward breach.

### 2.2 Why horizontal (not vertical-specific)
Supply chain disruption is industry-agnostic. A pharma company tracking cold-chain shipments, a fashion brand with Bangladesh apparel suppliers, a food distributor facing a hurricane, and an automaker watching Red Sea shipping routes all face the same core workflow. Building horizontally:
- Expands the demo audience (every judge has intuition for shipping delays)
- Forces a clean abstraction (no industry-specific hacks)
- Makes seed data flexible — we can show one industry in demo but architecture supports any
- For the demo, we'll seed a realistic mixed-industry dataset: electronics, apparel, food, pharma, industrial parts. Judges see the system handle diverse scenarios.

### 2.3 Why agents, not a dashboard
A traditional dashboard requires the human to ask the right question. A disruption cascade (event → port closure → supplier delay → customer SLA breach) requires the system to proactively reason across domains. This is precisely the class of problem agents solve: continuous monitoring, multi-source reasoning, drafted actions.

---

## 3. Target Personas

### 3.1 Primary persona — Maya Chen, Senior Supply Chain Manager
- **Company:** Mid-cap enterprise with global supply base
- **Role:** Owns inbound logistics across multiple product lines; reports to VP Ops
- **Day-to-day tools:** ERP (SAP IBP or equivalent), Excel, Slack, email, WhatsApp with contract manufacturers
- **Pain:** "Every time something happens I'm in panic mode for half a day. By the time I've figured out what's at risk, the CFO is already asking for numbers I don't have yet."
- **Success looks like:** Hearing about a disruption and already having a mitigation plan open, with dollar figures, before the first exec email arrives.

### 3.2 Secondary persona — Derek Obi, VP of Operations
- **Role:** Maya's boss; consumes summaries, approves high-dollar reroutes
- **Needs:** One-page view of active disruptions + financial exposure for the Monday leadership sync
- **Pain:** Wants to know "are we okay?" without pinging three managers

### 3.3 Tertiary persona — Ankit Rao, Finance Business Partner
- **Role:** Models quarterly impact of supply events; joins calls mid-crisis
- **Needs:** Exportable financial exposure breakdown (by SKU, customer, quarter)
- **Pain:** Data always arrives in a format he has to rebuild from scratch

> **Design implication:** Primary build targets Maya (operator). Derek gets a read-only exec summary tab. Ankit gets a CSV/JSON export. For hackathon scope, build Maya fully; Derek and Ankit as thin slices.

---

## 4. User Stories & Acceptance Criteria

### 4.1 Must-have (P0) — demo-critical

**US-01 — Multi-source signal detection**
- As Maya, I want the system to continuously scan news, weather, regulatory feeds, and macro signals so I learn about supply-relevant events without manual searching.
- **Acceptance:** Scout agent ingests from ≥ 4 source categories (news, weather, policy/regulatory, logistics status); classifies events by region, severity (1–5), category; stores to DB with timestamps and source URLs.

**US-02 — Impact assessment**
- As Maya, I want the system to automatically identify which shipments, SKUs, and customer POs are affected by a signal so I don't query the database manually.
- **Acceptance:** Analyst agent produces structured impact report listing affected shipment IDs, SKUs, PO numbers, customer names, and dollar exposure within 30 seconds. Report includes generated SQL for traceability.

**US-03 — Mitigation drafts**
- As Maya, I want the system to draft specific mitigation options (reroute, switch supplier, expedite) with cost/time tradeoffs so I can decide rather than analyze.
- **Acceptance:** Strategist returns ≥ 2 mitigation options per affected cluster; each option includes incremental cost, delay/savings in days, and confidence score.

**US-04 — One-click approval**
- As Maya, I want to approve a mitigation with a single click and have the system prepare downstream actions (draft emails saved to DB, shipment status flipped to "rerouting") so mitigation time drops from hours to minutes.
- **Acceptance:** "Approve" button saves drafted emails to `draft_communications` table (never sends), flips shipment status, logs the approval with user ID and timestamp.

**US-05 — War room dashboard**
- As Maya, I want a single live view of all active events, affected shipments, and pending decisions so I have situational awareness.
- **Acceptance:** Dashboard renders within 2 seconds, auto-refreshes every 30 seconds, ranks events by dollar exposure.

**US-06 — Simulate event (demo mode)**
- As a judge, I want a deterministic trigger so the demo works reliably even if live feeds are quiet.
- **Acceptance:** "Simulate Event" button triggers one of 5 pre-scripted scenarios; full pipeline runs end-to-end in ≤ 60 seconds.

### 4.2 Should-have (P1)

**US-07 — Explainability panel** — per-recommendation drawer shows source URLs, agent reasoning trace, SQL executed.
**US-08 — Financial analytics** — charts by customer, SKU, quarter; CSV export.
**US-09 — Approval audit log** — immutable log of approvals with state snapshots.
**US-10 — Event merging** — Scout clusters related events (e.g., typhoon + resulting port closures) within 72h windows.

### 4.3 Could-have (P2) — stretch
**US-11 — Proactive risk scoring** for anticipated events (monsoon, known flashpoints).
**US-12 — Voice briefing** — 30-second audio summary.

### 4.4 Won't-have (non-goals)
- Real ERP integration — mocked only
- Real supplier API calls
- Actually sending emails — drafts saved to DB only
- Authentication — single hard-coded demo user
- Mobile-native app
- Production security, compliance, audit

---

## 5. Functional Requirements

### 5.1 Data sources — multi-signal monitoring

Scout does not just read news. It composes a risk picture from diverse, complementary sources:

| Source category | Specific feeds | Why it matters |
|---|---|---|
| **News & events** | Tavily search (tuned queries for port/supplier/logistics terms) | Breaking events, labor actions, accidents |
| **Weather** | Open-Meteo API (free, no auth) over supplier + port coordinates | Typhoons, hurricanes, floods, extreme heat affecting warehouses |
| **Policy & regulatory** | Tavily queries targeted at USTR, EU Commission, MOFCOM, national trade bureaus | Tariffs, export controls, sanctions, customs rule changes |
| **Logistics status** | Tavily queries for port congestion, carrier advisories, canal status | Suez/Panama disruptions, port dwell times, capacity alerts |
| **Macro signals** | Tavily queries for commodity / freight spikes (Baltic Dry, TAC, oil) | Early indicators even absent a named event |

Each source is a first-class Scout subroutine — not an afterthought. The UI surfaces source category in every signal card ("Weather" badge vs "Policy" badge vs "News" badge), which is both informative and visually rich for the demo.

### 5.2 Agent architecture — the swarm

Three coordinated agents, each running in its own Dedalus Machine (Linux VM), communicating via shared Postgres as source of truth and Postgres LISTEN/NOTIFY as the event bus.

#### 5.2.1 Scout Agent (monitoring)
- **Runtime:** Dedalus Machine #1, long-running Python process
- **Loop:** 5 parallel async tasks, one per source category, each on its own cadence (news 60s, weather 5min, policy 15min, logistics 10min, macro 30min)
- **Output:** `signals` table rows (signals may or may not be disruptions yet); separately, `disruptions` table for signals that cross severity threshold or merge into a named event
- **Model:** Gemini 2.x Flash for fast classification
- **Key behaviors:**
  - Dedupes: skips events already seen within 72h by `{region, category, keyword hash}`
  - Severity scoring: rubric-based — "does this affect any port/supplier in our DB? is it a rated storm? does it match a policy change keyword list?"
  - Signal fusion: two related low-severity signals (weather advisory + carrier slowdown in same region) merge into one higher-severity event
  - Persistent state on the VM: Tavily cursors, last-seen hashes, weather polling checkpoints — all survive restarts

#### 5.2.2 Analyst Agent (impact assessment)
- **Runtime:** Dedalus Machine #2, event-triggered
- **Loop:** Subscribes via LISTEN/NOTIFY to `new_disruption` events; wakes, generates SQL, executes, produces structured impact report
- **Output:** `impact_reports`, `affected_shipments` rows
- **Model:** Gemini 2.x Pro (SQL generation + reasoning)
- **Key behaviors:**
  - Text-to-SQL: structured prompt with full schema + disruption context → parameterized query
  - **SQL safety:** validator rejects anything that is not a single `SELECT`, that references forbidden statements (`DROP`, `DELETE`, `UPDATE`, `INSERT`, `ALTER`, `TRUNCATE`, `GRANT`), or that uses statement terminators mid-query. Rejected queries trigger a retry with error context in the prompt; after 3 retries, fall back to a rules-based query template keyed on disruption category.
  - Geographic reasoning: disruption polygon → supplier coords → shipments in transit touching that region → SKUs → POs → $ exposure
  - Quantifies: exposure $, units at risk, SLA breach risk (days to customer due date vs new ETA), cascade depth
  - Traceability: every report stores generated SQL + full reasoning trace in `impact_reports.reasoning_trace` JSONB

#### 5.2.3 Strategist Agent (mitigation)
- **Runtime:** Dedalus Machine #3, triggered by new impact reports
- **Loop:** Generates 2–4 mitigation options per impact report; drafts comms artifacts; saves as pending approval
- **Output:** `mitigation_options`, `draft_communications` rows (never sent — saved to DB only)
- **Model:** Gemini 2.x Pro (multi-step reasoning, tone-aware drafting)
- **Key behaviors:**
  - Options: queries alternate suppliers, alternate ports, expedited freight from seeded `suppliers` and `logistics_options`
  - Cost/benefit: Δcost, Δdays, Δrisk per option
  - Draft emails: supplier reroute request (formal), customer notification (empathetic), internal escalation (terse, data-heavy)
  - **Never sends** — `draft_communications.sent_at` is always NULL; no SMTP library in the codebase
  - **Action layer:** uses OpenClaw pattern (per Eragon `annyzhou/openclaw-ddls` example) for DB mutations — supplier lookup, mitigation calculation, draft save, audit entry. This is what proves "real work, not chat" for the Eragon rubric.

#### 5.2.4 Coordination & state
- **Source of truth:** Postgres — all agents read/write
- **Event bus:** Postgres LISTEN/NOTIFY (simple, zero infra overhead). Channels: `new_signal`, `new_disruption`, `new_impact`, `new_mitigation`, `new_approval`
- **Idempotency:** every agent is rerun-safe; writes use `ON CONFLICT DO NOTHING` or content-hash dedupe
- **Checkpointing:** each agent persists cursor state to its VM's local filesystem (`/var/lib/supplai/state.json`)
- **Structured logging:** every action logged to `agent_log` with `trace_id`

---

## 6. Non-Functional Requirements

| Category | Requirement |
|---|---|
| **Latency — Scout** | New signal persisted ≤ 5s after source return |
| **Latency — Analyst** | Impact report generated ≤ 30s after disruption persisted |
| **Latency — Strategist** | Mitigation options drafted ≤ 45s after impact report |
| **End-to-end demo** | Simulated event → approvable mitigations on screen ≤ 60s |
| **UI responsiveness** | Initial paint ≤ 2s; action feedback ≤ 200ms; animation targets 60fps |
| **Reliability** | Agents survive restart; no duplicate signals after crash |
| **Safety — SQL** | Analyst-generated SQL passes validator 100% of the time or is rejected and retried |
| **Safety — actions** | Zero actions execute without explicit approval. Emails are never sent — drafts saved to DB only |
| **Observability** | Every agent action logged with trace ID; dashboard Agent Activity feed visible |
| **Demo robustness** | Offline cache: if Tavily or Gemini fails, serve cached responses so demo never breaks |

---

## 7. Tech Stack — Detailed

### 7.1 Backend

#### 7.1.1 Language & framework
- **Python 3.12** across all agents and the API layer (single language for the team of 3)
- **FastAPI** for the HTTP/WebSocket layer between dashboard and Postgres
  - Async-native (matches agent style), auto-generated OpenAPI schema, great Pydantic integration, fast to build
  - Served on its own small Dedalus Machine or co-located with one of the agents
- **uv** for dependency management — 10–100× faster than pip, reproducible lockfile, ships with zero config. Use `uv sync` in CI and on VMs.
- **Ruff** for lint + format (replaces black + isort + flake8, single tool)
- **mypy --strict** on shared modules (db, schemas, agent contracts)

#### 7.1.2 Agent implementation pattern

Every agent is a Python service following this structure:

```
agents/<agent_name>/
  __init__.py
  main.py                 # entrypoint, event loop
  config.py               # env vars via pydantic-settings
  sources/                # for Scout: one module per source category
  processors/             # pure functions, testable
  prompts/                # prompt templates as .txt or .md (versioned)
  state.py                # checkpoint read/write
  tests/
```

- Agents use `asyncio` event loops; one coroutine per background task
- Agents communicate strictly through Postgres (no direct agent-to-agent RPC) — this is the "swarm" discipline
- Structured logging via `structlog` with JSON output; every log line carries `trace_id`, `agent`, `event_type`

#### 7.1.3 Database

- **Postgres 16**, hosted on a small Dedalus Machine or on Neon (free tier — decide in first hour based on latency test)
- **SQLAlchemy 2.x (async)** + **asyncpg** driver for the API; raw asyncpg in agents for minimal overhead
- **Alembic** for schema migrations (even for a hackathon — prevents Sunday-morning schema drift)
- **Connection pooling:** `asyncpg.create_pool(min=2, max=10)` per agent; FastAPI uses SQLAlchemy's async pool
- **Seed data** loaded via a single `scripts/seed.py` — idempotent, rerunnable, produces reproducible demo state

#### 7.1.4 LLM orchestration
- **Direct Gemini API calls** via `google-generativeai` Python SDK — no LangChain or heavy framework overhead
- Prompts live in versioned `.md` files in `prompts/` directories — easier to diff and iterate than Python strings
- **Prompt caching**: cache `(prompt_hash, model_output)` in a small SQLite DB on each VM for offline demo fallback and to avoid re-billing identical calls during dev
- **Retry/timeout:** `tenacity` with exponential backoff (3 attempts, 60s total budget per call)
- **Response validation:** every model output parsed into a Pydantic model; invalid outputs trigger one retry with error context, then fail gracefully

#### 7.1.5 Scheduling & background work
- Scout: in-process `asyncio.create_task` loops, each wrapped in try/except with restart-on-crash
- Analyst, Strategist: in-process PG LISTEN loop + worker coroutine
- No Celery, no Redis queue — keeps infra count low and swarm discipline clean

#### 7.1.6 Backend testing
- **pytest** + `pytest-asyncio` + `pytest-postgresql` (spins ephemeral PG for integration tests)
- **Fixtures** for seeded DB states corresponding to each of the 5 demo scenarios
- Coverage targets: 70%+ on `processors/` (pure logic), 50%+ elsewhere
- `pre-commit` hook runs ruff + mypy before every commit

#### 7.1.7 API surface (FastAPI routes)

```
GET  /api/signals?status=active             # Scout feed
GET  /api/disruptions/:id                   # detail
GET  /api/disruptions/:id/impact            # Analyst output
GET  /api/disruptions/:id/mitigations       # Strategist output
POST /api/mitigations/:id/approve           # triggers drafts + status flip
POST /api/mitigations/:id/dismiss
GET  /api/analytics/exposure                # for Ankit view
GET  /api/activity/feed                     # agent activity
POST /api/dev/simulate                      # demo trigger
WS   /ws/updates                            # live push to dashboard
```

WebSocket pushes new signals, impacts, and mitigations as they land, so the dashboard is reactive without polling.

### 7.2 Frontend

#### 7.2.1 Framework & core libraries
- **Next.js 15 (App Router)** with **TypeScript strict mode**
- **React 19** — use the stable concurrent features, `useOptimistic` for approval actions
- **Tailwind CSS 4** with custom design tokens (see §7.2.3)
- **shadcn/ui** as component primitives, then heavily customized — no vanilla shadcn aesthetic
- **Zustand** for client state (lighter than Redux, no boilerplate)
- **TanStack Query (React Query)** for server state, cache, optimistic updates
- **zod** for runtime validation of API responses — paired with TS types generated from FastAPI's OpenAPI schema via `openapi-typescript`
- **Leaflet + react-leaflet** for the map (confirmed)
- **Recharts** for analytics charts — override defaults aggressively to kill the generic look
- **Motion (formerly Framer Motion)** for animation primitives

#### 7.2.2 Design philosophy — "does not look AI-generated"

This is treated as a first-class requirement. The aesthetic target is **Linear / Vercel / Arc Browser / Stripe dashboard** — calm, confident, details-obsessed — not the generic shadcn-on-purple-gradient look that every hackathon ships.

**Mandatory skills to apply** (the team must actively consult these during frontend build):
- **`/ui-ux-pro-max`** — layout, hierarchy, whitespace discipline, professional dashboard patterns
- **`taste`** — color, typography, visual voice, restraint; rejects the "AI slop" defaults
- **`impeccable`** — finish quality, pixel alignment, micro-spacing, state coverage (hover, focus, active, disabled, loading, empty, error)
- **`emilkowalski-animation`** — motion feel, spring physics, timing curves, micro-interactions that feel alive instead of "animated"

Each frontend PR must be reviewed against these skills before merge. Teammate B owns this discipline.

**Anti-patterns forbidden:**
- Purple-to-pink gradients
- Generic glassmorphism without purpose
- Emoji in headers or nav
- Default shadcn card with default shadcn button stacked — every screen must have intentional composition
- Border radius on everything — mix sharp and rounded deliberately
- Drop shadows on flat things
- "AI" badges, sparkle icons, or robot avatars
- Decorative 3D illustrations
- Vague placeholder copy ("Lorem ipsum", "Your content here") — every screen is realistic during judging

#### 7.2.3 Design tokens

Defined in `app/globals.css` as CSS variables, consumed via Tailwind:

```css
:root {
  /* Neutrals — near-black to near-white, not pure */
  --bg: #0A0B0D;              /* page background */
  --surface: #111316;         /* card/panel */
  --surface-raised: #181B1F;  /* hover/elevated */
  --border: #23262B;
  --border-strong: #2E3238;
  --text: #E8EAED;
  --text-muted: #8B9098;
  --text-subtle: #5A6068;

  /* Status — earthy, not candy */
  --critical: #E5484D;
  --critical-bg: #1F1315;
  --warn: #D97757;
  --warn-bg: #1F1612;
  --ok: #46A758;
  --info: #4A8FD4;

  /* Category accents — muted, distinct */
  --cat-weather: #5E81AC;
  --cat-policy: #B48EAD;
  --cat-news: #A3BE8C;
  --cat-logistics: #EBCB8B;
  --cat-macro: #D08770;

  /* Type scale — tight ratio */
  --text-xs: 11px;
  --text-sm: 13px;
  --text-base: 14px;
  --text-lg: 16px;
  --text-xl: 20px;
  --text-2xl: 28px;
  --text-display: 44px;

  /* Spacing — 4px base */
  --space-1: 4px; --space-2: 8px; --space-3: 12px;
  --space-4: 16px; --space-5: 24px; --space-6: 32px;
  --space-7: 48px; --space-8: 64px;

  /* Motion */
  --ease-out: cubic-bezier(0.22, 1, 0.36, 1);
  --ease-spring: cubic-bezier(0.34, 1.56, 0.64, 1);
  --duration-fast: 120ms;
  --duration-base: 200ms;
  --duration-slow: 320ms;
}
```

**Typography**
- Display + UI: **Inter** (weights 400/500/600; use optical sizes via Inter Display for 24px+)
- Numerics: **Inter with `tnum` feature on** (`font-feature-settings: 'tnum'`) for all dollar figures, counts, timestamps — prevents the jiggle during live updates
- Code/IDs: **JetBrains Mono** at 12px for shipment IDs, trace IDs, SQL

**Layout**
- 12-column grid, but used sparingly — most layouts are flex with intentional breakpoints
- Dense by default; whitespace earned by content hierarchy, not decoration
- Fixed top bar 56px; left rail 280px; right rail 320px; center flex

#### 7.2.4 Animation principles (Emil Kowalski school)
- **Purposeful only.** Every animation earns its existence: state change, spatial continuity, feedback, or attention direction. No decorative motion.
- **Physics, not curves.** Spring (`stiffness: 260, damping: 26`) for entrances; `ease-out` for exits; never `linear`.
- **Short.** 120–320ms. If a user notices the duration, it's too long.
- **Layered.** List items stagger by 20ms. Parent fades before children slide.
- **Respect `prefers-reduced-motion`** — animations become instant.

Specific moments:
- New signal arrives: slides in from left with subtle spring, brief highlight pulse on the $ exposure in top bar
- Approval click: button collapses, mitigation card morphs into the approvals log row (layout animation via Motion's `layoutId`)
- Map pin for new disruption: scale-in with spring, radius ring pulses once then settles
- Loading states: **skeleton screens** styled identically to final content, not spinners
- Explainability drawer: slides from right with a slight overshoot, content fades in 60ms after

#### 7.2.5 Frontend file structure

```
web/
  app/
    (dashboard)/
      page.tsx                # War Room
      disruption/[id]/page.tsx
      analytics/page.tsx
      exec/page.tsx
    api/ (none — proxies to FastAPI)
    layout.tsx
    globals.css
  components/
    ui/                       # shadcn primitives, customized
    disruption/
    mitigation/
    map/
    agent-activity/
    charts/
  lib/
    api-client.ts             # typed fetch, zod-validated
    ws-client.ts
    store.ts                  # zustand
    design-tokens.ts          # TS export of CSS vars for JS access
  hooks/
  types/                      # generated from OpenAPI
  styles/
  tests/                      # Playwright e2e
```

#### 7.2.6 Frontend testing & quality
- **Playwright** e2e: load war room → click Simulate → assert mitigation card appears ≤ 60s (5 scenarios)
- **Lighthouse** CI target: Performance 90+, Accessibility 95+
- **Storybook** optional stretch — only if Teammate B has extra hours on Sunday
- **ESLint** with `@typescript-eslint/strict` + `eslint-plugin-react-hooks` + tailwind plugin
- **Prettier** paired with ESLint, run via `lint-staged` on pre-commit

### 7.3 Infrastructure & deployment

| Layer | Home | Notes |
|---|---|---|
| Scout agent | Dedalus Machine #1 (default tier) | Long-running asyncio loop |
| Analyst agent | Dedalus Machine #2 (default tier) | Event-triggered worker |
| Strategist agent | Dedalus Machine #3 (default tier) | Event-triggered worker + OpenClaw integration |
| Postgres | Dedalus Machine #4 OR Neon free tier | Decide in hour 1 by measuring latency from Dedalus network |
| FastAPI | Co-located on DB Dedalus VM (Machine #4) | Minimizes hop count |
| Next.js frontend | Vercel | Free tier sufficient; preview deploys on every PR |
| Env vars | `.env.local` for dev; Dedalus VM env vars for prod; Vercel dashboard for frontend | Never committed; `.env.example` in repo |

### 7.4 Repo, branching, CI/CD

- **Monorepo** with `backend/` and `web/` top-level
- **Trunk-based** — single `main` branch; short-lived feature branches merged via PR with at least one review
- **CI:** GitHub Actions runs on every PR — `uv sync && ruff && mypy && pytest` for backend; `pnpm install && lint && typecheck && build` for frontend
- **Pre-commit hooks** via `pre-commit` framework — ruff, prettier, secret scanner (gitleaks)
- **Conventional Commits** (`feat:`, `fix:`, `chore:`) — enables auto-generated changelog and makes judging-day git log readable
- **Branch protections:** `main` requires passing CI + 1 approval (relax if solo-debugging at 3am, re-enable for submission)
- **Secrets:** 1Password shared vault among the 3 teammates; never in env files committed

### 7.5 External services checklist

- [ ] Dedalus credits claimed at https://dedaluslabs.ai/hackprinceton-s26 for all 3 teammates ($150 total)
- [ ] Gemini API key from Google AI Studio
- [ ] Tavily API key (free tier)
- [ ] Open-Meteo — no auth required
- [ ] Vercel account (one teammate, link to repo)
- [ ] GitHub repo created during 4/17–4/19 window (per hackathon rules)

---

## 8. Data Model (Detailed)

### 8.1 Core schema

```sql
-- Geography
CREATE TABLE ports (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  country TEXT NOT NULL,
  lat DOUBLE PRECISION,
  lng DOUBLE PRECISION,
  modes TEXT[]
);

CREATE TABLE suppliers (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  country TEXT,
  region TEXT,
  tier INT,
  industry TEXT,
  reliability_score NUMERIC,
  categories TEXT[],
  lat DOUBLE PRECISION,
  lng DOUBLE PRECISION
);

CREATE TABLE skus (
  id TEXT PRIMARY KEY,
  description TEXT,
  family TEXT,
  industry TEXT,
  unit_cost NUMERIC,
  unit_revenue NUMERIC
);

CREATE TABLE customers (
  id TEXT PRIMARY KEY,
  name TEXT,
  tier TEXT,
  sla_days INT,
  contact_email TEXT
);

CREATE TABLE purchase_orders (
  id TEXT PRIMARY KEY,
  customer_id TEXT REFERENCES customers(id),
  sku_id TEXT REFERENCES skus(id),
  qty INT,
  due_date DATE,
  revenue NUMERIC,
  sla_breach_penalty NUMERIC
);

CREATE TABLE shipments (
  id TEXT PRIMARY KEY,
  po_id TEXT REFERENCES purchase_orders(id),
  supplier_id TEXT REFERENCES suppliers(id),
  origin_port_id TEXT REFERENCES ports(id),
  dest_port_id TEXT REFERENCES ports(id),
  status TEXT,
  mode TEXT,
  eta DATE,
  value NUMERIC
);

-- Agent outputs
CREATE TABLE signals (
  id UUID PRIMARY KEY,
  source_category TEXT,
  source_name TEXT,
  title TEXT,
  summary TEXT,
  region TEXT,
  lat DOUBLE PRECISION,
  lng DOUBLE PRECISION,
  radius_km NUMERIC,
  source_urls TEXT[],
  confidence NUMERIC,
  raw_payload JSONB,
  first_seen_at TIMESTAMP,
  promoted_to_disruption_id UUID
);

CREATE TABLE disruptions (
  id UUID PRIMARY KEY,
  title TEXT,
  summary TEXT,
  category TEXT,
  severity INT,
  region TEXT,
  lat DOUBLE PRECISION,
  lng DOUBLE PRECISION,
  radius_km NUMERIC,
  source_signal_ids UUID[],
  confidence NUMERIC,
  first_seen_at TIMESTAMP,
  last_seen_at TIMESTAMP,
  status TEXT
);

CREATE TABLE impact_reports (
  id UUID PRIMARY KEY,
  disruption_id UUID REFERENCES disruptions(id),
  total_exposure NUMERIC,
  units_at_risk INT,
  cascade_depth INT,
  sql_executed TEXT,
  reasoning_trace JSONB,
  generated_at TIMESTAMP
);

CREATE TABLE affected_shipments (
  impact_report_id UUID REFERENCES impact_reports(id),
  shipment_id TEXT REFERENCES shipments(id),
  exposure NUMERIC,
  days_to_sla_breach INT,
  PRIMARY KEY (impact_report_id, shipment_id)
);

CREATE TABLE mitigation_options (
  id UUID PRIMARY KEY,
  impact_report_id UUID REFERENCES impact_reports(id),
  option_type TEXT,
  description TEXT,
  delta_cost NUMERIC,
  delta_days INT,
  confidence NUMERIC,
  rationale TEXT,
  status TEXT
);

CREATE TABLE draft_communications (
  id UUID PRIMARY KEY,
  mitigation_id UUID REFERENCES mitigation_options(id),
  recipient_type TEXT,
  recipient_contact TEXT,
  subject TEXT,
  body TEXT,
  created_at TIMESTAMP DEFAULT NOW(),
  sent_at TIMESTAMP
);

CREATE TABLE approvals (
  id UUID PRIMARY KEY,
  mitigation_id UUID REFERENCES mitigation_options(id),
  approved_by TEXT,
  approved_at TIMESTAMP,
  state_snapshot JSONB
);

CREATE TABLE agent_log (
  id BIGSERIAL PRIMARY KEY,
  agent_name TEXT,
  trace_id UUID,
  event_type TEXT,
  payload JSONB,
  ts TIMESTAMP DEFAULT NOW()
);

-- Indexes
CREATE INDEX idx_signals_first_seen ON signals(first_seen_at DESC);
CREATE INDEX idx_disruptions_status ON disruptions(status);
CREATE INDEX idx_shipments_status ON shipments(status);
CREATE INDEX idx_shipments_origin ON shipments(origin_port_id);
CREATE INDEX idx_agent_log_trace ON agent_log(trace_id);
```

### 8.2 Seed data volumes (multi-industry)
- Ports: 30 globally distributed (Asia, EU, NA, with key chokepoints)
- Suppliers: 50 spanning electronics (15), apparel (10), food (10), pharma (8), industrial (7)
- SKUs: 40 (8 per industry)
- Customers: 20 (tier mix)
- POs: 200
- Shipments: 500 (status mix: 60% in_transit, 20% planned, 20% arrived)

---

## 9. UI / UX Wireframes

### 9.1 War Room (home)

```
┌────────────────────────────────────────────────────────────────────────────┐
│ ▌ suppl.ai      Maya Chen            3 active · $4.2M at risk    ⚙  │
│                                                  [+ Simulate event]       │
├───────────────┬─────────────────────────────────────────┬──────────────────┤
│ ACTIVE (3)    │ Typhoon Kaia                            │ PENDING          │
│               │ Weather · Severity 4 · Detected 14:00   │                  │
│ ■ Typhoon Kaia│                                         │ Reroute 14       │
│   $2.3M · 14  │ ┌─────────────────────────────────────┐ │ shipments via    │
│   Weather     │ │                                     │ │ Ho Chi Minh      │
│               │ │   [ map of South China Sea,         │ │ +$180K · -5d     │
│ ■ Busan strike│ │     typhoon cone shaded,            │ │ ▸ Approve        │
│   $1.4M · 8   │ │     14 shipment dots in red ]       │ │                  │
│   Logistics   │ │                                     │ │ Alt supplier     │
│               │ └─────────────────────────────────────┘ │ Luxshare → VN    │
│ ■ EU tariff   │                                         │ +$42K · same day │
│   $0.5M · 5   │ AFFECTED SHIPMENTS · 14                 │ ▸ Approve        │
│   Policy      │ ─────────────────────────────────────── │                  │
│               │ SHP-0441  MCU-A  ACME      $180K   3d   │ ACTIVITY         │
│ + simulate    │ SHP-0442  MCU-A  ACME      $180K   3d   │                  │
│               │ SHP-0448  PMIC   BETA      $95K    1d!  │ 14:02 Strategist │
│               │ ... 11 more                             │  drafted 3 mit.  │
│               │                                         │ 14:01 Analyst    │
│               │ MITIGATIONS · 3                         │  ran SQL         │
│               │ ─────────────────────────────────────── │ 14:00 Scout      │
│               │ ┌──────────┬──────────┬──────────┐      │  detected Kaia   │
│               │ │ Reroute  │ Alternate│ Expedite │      │ 13:58 Scout      │
│               │ │ HCM      │ supplier │ air      │      │  weather poll    │
│               │ │ +$180K   │ +$42K    │ +$1.1M   │      │                  │
│               │ │ -5d      │ 0d       │ -8d      │      │                  │
│               │ │ 87%      │ 72%      │ 95%      │      │                  │
│               │ │ Approve  │ Approve  │ Approve  │      │                  │
│               │ └──────────┴──────────┴──────────┘      │                  │
│               │                                         │                  │
│               │ Why this recommendation? ▸              │                  │
└───────────────┴─────────────────────────────────────────┴──────────────────┘
```

Design notes:
- Category badges on left rail colored per design tokens (weather blue, policy lilac, logistics amber)
- Dollar exposure in top bar uses tabular numerics so it doesn't jiggle on updates
- Shipment table uses mono font for IDs, sans for names
- "1d!" urgency markers — subtle red but not alarming

### 9.2 Approval modal

```
┌──────────────────────────────────────────────────────────┐
│  Reroute 14 shipments via Ho Chi Minh                 ×  │
├──────────────────────────────────────────────────────────┤
│                                                          │
│  14 shipments · $2.3M value                              │
│  +$180K incremental · 5 days recovered · 87% confidence  │
│                                                          │
│  This will prepare drafts (never send)                   │
│  ─ Supplier email to Luxshare Vietnam          [view]    │
│  ─ Customer notification to ACME Corp          [view]    │
│  ─ Internal escalation to Derek Obi            [view]    │
│                                                          │
│  Database changes                                        │
│  ─ 14 shipments → status "rerouting"                     │
│  ─ Approval entry logged                                 │
│                                                          │
│                        [ Cancel ]  [ Approve & prepare ] │
└──────────────────────────────────────────────────────────┘
```

### 9.3 Explainability drawer

Slides from right. Content:
- **Trigger signals** — chips with category + source + time
- **Impact query** — syntax-highlighted SQL in JetBrains Mono
- **Reasoning** — numbered steps from Analyst/Strategist trace
- **Alternatives considered** — options that lost, with why

### 9.4 Analytics (Ankit)
Three charts on a grid: exposure by quarter (area), exposure by customer tier (bar), exposure by SKU family (bar). CSV export top-right. Charts use muted palette; no rainbow defaults.

### 9.5 Exec summary (Derek)
Single page, generous whitespace. Big status line ("Supply chain is STABLE / MONITORING / ESCALATED"), 3 active disruption cards, 4-week trend sparkline. One CTA: "Open war room".

### 9.6 Micro-interactions
- New signal card slides in from left with spring; category badge fades in 40ms after
- Approval button: click → collapses to checkmark → morphs into approvals log entry via shared `layoutId`
- Map disruption pin: scale-in with overshoot, single radial pulse, settle
- Skeleton loaders exactly match final layout — no layout shift on data arrival
- Hover: 1px border color shift, not a shadow bloom
- Focus rings: 2px offset, brand color at 60% opacity — visible but not shouty

### 9.7 Empty & error states (first-class)
- Empty war room: explains the product in 2 sentences + prominent Simulate button
- Failed signal fetch: inline banner with retry, source category dimmed in left rail
- Agent offline: status dot in activity feed shifts to red with tooltip

---

## 10. Project Organization & Timeline

### 10.1 Team roles (3 people)

| Role | Owner | Scope |
|---|---|---|
| **Agents & infra** | Teammate A | 3 Dedalus VMs, all agents, Postgres, event bus, OpenClaw integration, seed data loader |
| **Frontend & UX** | Teammate B | Next.js app, all 5 screens, Leaflet map, design system, animations — owns the "does not look AI-generated" outcome |
| **API, demo, glue** | Teammate C | FastAPI layer, SQL validator, prompt engineering, demo scenarios, pitch deck, README |

### 10.2 Hour-by-hour plan (36h)

**Fri 5pm–10pm · Kickoff + foundation (5h)**
- Team sync, PRD skim, roles confirmed
- Create GitHub repo (within hackathon window per rules)
- Claim Dedalus credits (all 3), provision 4 VMs, SSH works
- Gemini + Tavily hello-world calls verified
- Postgres up; schema migrated; 10-supplier smoke seed
- `uv` + `ruff` + `mypy` + `pre-commit` configured
- Next.js scaffold with design tokens in place, empty layout renders
- Decide Postgres location (Dedalus vs Neon) by latency test

**Fri 10pm–Sat 3am · Parallel build (5h)**
- A: Scout skeleton — Tavily news loop + Gemini classify + signal insert
- B: War Room layout, left rail with mock data, Inter + tokens wired
- C: Seed loader expanded to 500 shipments; SQL validator library; Analyst prompt v1

**Sat 3am–9am · Sleep shift (6h) — rotate, one on-call**

**Sat 9am–3pm · Core functionality (6h)**
- A: Scout sources 2–5 (weather, policy, logistics, macro) added in parallel async tasks
- A: Analyst end-to-end (LISTEN → SQL → execute → impact report)
- B: War Room connected to live API; map with disruption markers; category badges
- C: Strategist options (rules + Gemini hybrid); draft comms templates

**Sat 3pm–9pm · Integration (6h)**
- End-to-end dry run: simulate → Scout → Analyst → Strategist → UI
- B: Approval modal + explainability drawer + animation polish
- A: OpenClaw integration for Strategist's DB action layer
- C: 5 demo scenarios scripted and tested

**Sat 9pm–Sun 3am · Polish (6h)**
- Bug bash, error states, offline cache
- B: Analytics tab, exec summary, final animation pass, accessibility audit
- C: Pitch deck + 2-minute script; README
- A: VM persistence test — kill + restart each agent, verify state survives

**Sun 3am–7am · Sleep shift (4h)**

**Sun 7am–9:30am · Final (2.5h)**
- 3× live dry run under demo conditions
- Lock repo, submit Devpost
- Print 1-page architecture handout for judges

### 10.3 Risk register

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| OpenClaw learning curve eats time | Med | High | 3h hard cap; fallback is plain Python action layer (still covers most of Eragon rubric) |
| Tavily rate limits mid-demo | Low | High | Cache last 20 results; demo mode uses cached |
| Gemini SQL output invalid | High | Med | Validator + retry + category-keyed template fallback |
| Dedalus VM coordination flaky | Med | High | Simple LISTEN/NOTIFY; health check; fallback to single-VM running all 3 agents while keeping 3-service code |
| Frontend looks generic | Med | Very High | Daily design review (hours 6, 18, 30) against the four skills; kill anything "shadcn default" |
| Animation perf on demo laptop | Low | Med | Profile on Sat evening; reduce to essential animations if <60fps |
| Team member stuck > 90 min | Med | High | Pair-unblock rule; no silent struggles |
| Live demo breaks | Low | Catastrophic | Simulate button is the demo; backup screenshot walkthrough as last resort |

---

## 11. Testing Strategy & Metrics

### 11.1 Test layers
- **Unit** — SQL validator, severity scorer, signal dedupe, mitigation math, Pydantic schema validation
- **Integration** — simulate event → assert signals row → disruption row → impact row → mitigation rows, all via ephemeral Postgres
- **Agent prompt evals** — for each of 5 demo scenarios, assert Analyst returns expected shipment count ±2, Strategist returns ≥2 options
- **E2E** — Playwright: Simulate click → mitigation card ≤ 60s on all 5 scenarios
- **Manual dry runs** — 3× on Sunday morning

### 11.2 Quality gates (must-pass before submission)
- E2E green, 5/5 scenarios, 5 consecutive runs
- Zero SQL mutations possible through Analyst path
- Zero SMTP calls in codebase (`grep smtplib; grep sendmail` returns empty)
- Dashboard initial paint < 2s on demo laptop
- `ruff` + `mypy --strict` clean on shared modules
- Lighthouse Performance ≥ 90, Accessibility ≥ 95 on War Room page

### 11.3 Demo-day metrics
- Time-to-insight (simulate click → $ exposure visible): target ≤ 45s
- Time-to-decision (simulate click → approval confirmed): target ≤ 90s including reading
- Judge sanity check — "would you click approve?": target 2/3 yes

---

## 12. Success Metrics & KPIs

### 12.1 Hackathon prize targets

| Prize | Target | How we demonstrate |
|---|---|---|
| Dedalus Best Agent Swarm ($500) | Win | 3 VMs running 3 distinct agents, swarm behavior documented, live in demo |
| Dedalus Best Use of Containers ($250×4) | Place | Persistent state across agent restarts shown live |
| Eragon OpenClaw (Mac Mini) | Win | Strategist uses OpenClaw for real DB mutations + draft prep; pitch emphasizes "Monday useful" |
| Best Business & Enterprise Hack | Win | Demo centers on Maya persona with dollar outcomes |
| MLH Best Use of Gemini | Place | Gemini meaningfully across all 3 agents — documented |
| **Stretch: Best Overall** | Long shot | Polish + narrative + judge reaction |

### 12.2 Product KPIs (if this shipped)

| KPI | Target at 3 months |
|---|---|
| Time-to-mitigation (detection → approved action) | < 5 min median (vs 2–6 hours baseline) |
| Disruption detection recall | > 90% |
| Mitigation acceptance rate | > 60% |
| False positive rate | < 15% |
| User NPS (logistics managers) | > 40 |
| Dollar exposure surfaced/month/customer | > $10M |

### 12.3 Technical KPIs

| KPI | Target |
|---|---|
| Agent uptime during demo | 100% |
| E2E latency P95 | < 60s |
| SQL validator false rejects | 0% |
| Dashboard errors during demo | 0 |

---

## 13. Sponsor Integration Notes

### 13.1 Dedalus (anchor — $750 combined target)
- All 3 teammates claim $50 credits at https://dedaluslabs.ai/hackprinceton-s26
- 3 Machines: `scout-vm`, `analyst-vm`, `strategist-vm` (+ optional `db-vm`), default tier
- Each VM runs a long-lived Python process with persistent state — Tavily cursors, seen-event hashes, prompt cache — all in `/var/lib/supplai/state.json`. Kill + restart = resumes cleanly. This is what the "needs a real OS" narrative rests on.
- README screenshots of `systemctl status supplai-scout` on each VM
- Reference example: https://github.com/annyzhou/openclaw-ddls

### 13.2 Eragon — OpenClaw
- Strategist uses OpenClaw for its action layer: reading suppliers, scoring alternatives, writing `draft_communications`, flipping shipment status, appending audit entries
- Rubric mapping:
  - **Depth of Action (30%)** — approvals mutate DB, prepare real email bodies (saved, not sent), and log audits. Not chat.
  - **Context Quality (30%)** — Strategist pulls from signals, disruptions, impact reports, suppliers, customers, shipments, POs. Seven sources.
  - **Workflow Usefulness (40%)** — Maya persona and "Monday morning" framing carried throughout pitch

### 13.3 Tavily
- Scout's primary search layer, used for 4 of 5 source categories (news, policy, logistics, macro)
- Query library documented in `agents/scout/sources/tavily_queries.md` — showcases the domain-specific prompting
- README screenshot of a Tavily response feeding the Gemini classifier

### 13.4 Gemini API (MLH)
- Flash: Scout classification (high-volume, cheap)
- Pro: Analyst SQL generation + Strategist reasoning/drafting
- README dedicates a section to Gemini usage per agent

---

## 14. Decisions Locked (from open questions)

| Question | Decision |
|---|---|
| Email "sending" | **Stop at DB draft.** `draft_communications` populated; `sent_at` always NULL; zero SMTP libraries in deps |
| Auth | **Skipped.** Hardcoded `Maya Chen` as current user |
| Map | **Leaflet + react-leaflet** with free OSM tiles |
| Agent language | **Python** across all 3 |
| Dedalus VM size | **Default tier** |

---

## 15. Appendix

### 15.1 Demo scenarios (5 pre-baked, multi-industry)

1. **Typhoon Kaia → Shenzhen port** — weather · Cat 3 · 14 electronics shipments · $2.3M · reroute to HCM or expedite air
2. **Dockworker strike → Busan** — logistics · 72h · 8 mixed shipments (apparel + food) · $1.4M · reroute to Kaohsiung
3. **EU CBAM tariff announcement** — policy · 5 industrial SKUs · $500K · switch to compliant supplier
4. **Luxshare plant fire** — industrial · single supplier · 6 electronics SKUs · $900K · activate backup
5. **Red Sea shipping advisory** — logistics · 20+ shipments rerouting Suez → Cape · $3.1M · accept delays vs expedite air selectively

### 15.2 Anti-patterns (do not ship)
- Multi-agent theater: three prompts dressed as three agents. Must be 3 processes, 3 VMs.
- Chatbot UI as primary interface. This is an operator dashboard.
- Fake numbers hardcoded in UI. Every $ computed from seeded shipments.
- Generic AI aesthetic — if a judge thinks "this looks like v0 output," we failed §7.2.2.
- Sending any real email.

### 15.3 One-sentence pitch
> "When the next disruption hits — typhoon, tariff, strike, fire — Maya won't spend six hours in Excel. She'll approve a drafted mitigation in sixty seconds, because three agents already did the work."

---

*End of PRD v2.0*
