# Parallel Execution Coordination — suppl.ai

> Read this first. Then pick up your plan (A, B, or C).

**Master plan (source of truth for task specs):** `docs/superpowers/plans/2026-04-18-suppl-ai-implementation.md`

**Foundation already shipped (commits `bfbcb12`…`24e6dbf`):** repo tooling, CI, pre-commit hooks, Postgres schema, seed data (30 ports / 50 suppliers / 40 SKUs / 20 customers / 200 POs / 500 shipments), FastAPI `/health`, Next.js 15 shell with design tokens. Teammates start from `main`.

## Team partition

| Plan | Owner | Charter | Plan file |
|---|---|---|---|
| **A** | Agents & Infra | 3 agent processes (Scout → Analyst → Strategist), event bus, Gemini integration, Dedalus VMs | `2026-04-18-plan-A-agents-infra.md` |
| **B** | Frontend & UX | Next.js dashboard, all 5 screens, map, animations, a11y | `2026-04-18-plan-B-frontend.md` |
| **C** | API, Demo & Glue | FastAPI routes + WS, Pydantic schemas, SQL safety, demo scenarios, E2E, pitch/README | `2026-04-18-plan-C-api-demo.md` |

## Dependency DAG (critical path top-to-bottom)

```
              C.1 Pydantic schemas (frozen first)
                 ↙          ↓           ↘
     A.1 LLM client    C.2 FastAPI    B.1 TS types via openapi-gen
     A.2 Event bus      routes             ↓
     A.3 Agent base         ↓          B.2 App shell + WS client
         ↓             C.3 WS relay        ↓
     A.4 Scout              ↘          B.3 Left rail consuming /api/signals
         ↓                    ↘            ↓
     A.5 Analyst (needs C.4 SQL guard, C.5 analyst tools)
         ↓
     A.6 Strategist (needs openclaw dep resolved)
         ↓
     C.6 Demo scenarios + Simulate endpoint  →  B.4–B.8 full war room UI
         ↓
     C.7 Playwright e2e (requires A+B+C all done)
         ↓
     A.7/B.9/C.8 infra polish + pitch
```

## Contract freeze points (do not change without all 3 teammates acknowledging)

These are shared contracts. When you commit any of these, ping in Slack / post the commit SHA. Everyone rebases on it.

1. **Pydantic schemas** — owned by Plan C (Task 2.1). Plan A and Plan B consume them via `backend/schemas/*` and via generated TS types. Freeze by hour 4.

2. **Postgres `LISTEN/NOTIFY` channel names** — frozen now, do NOT change:
   ```
   new_signal
   new_disruption
   new_impact
   new_mitigation
   new_approval
   ```
   Payloads are JSON strings. Each channel's payload schema:
   - `new_signal`: `{"id": <uuid>, "source_category": <str>}`
   - `new_disruption`: `{"id": <uuid>, "severity": <int>}`
   - `new_impact`: `{"id": <uuid>, "disruption_id": <uuid>, "total_exposure": <decimal-str>}`
   - `new_mitigation`: `{"id": <uuid>, "impact_report_id": <uuid>}`
   - `new_approval`: `{"id": <uuid>, "mitigation_id": <uuid>}`

3. **OpenAPI → TypeScript types pipeline**:
   - When C adds/modifies a FastAPI route, C runs `pnpm -C web openapi:gen`, commits the diff in `web/types/api.ts`.
   - The pre-commit hook `openapi-types-fresh` fails CI if `api.ts` drifts from the live schema — keeps A and B honest.
   - B consumes types directly from `web/types/api.ts` via `import type { paths } from "@/types/api"`.

4. **Demo scenario identifiers** (Phase 11) — frozen now:
   ```
   typhoon_kaia
   busan_strike
   cbam_tariff
   luxshare_fire
   redsea_advisory
   ```
   C owns the Simulate endpoint; A's agents must cascade correctly for all 5.

5. **Agent DB write idempotency** — every agent write uses `ON CONFLICT DO NOTHING` or content-hash dedupe. Plan A enforces; Plan C's atomic approval transaction (Task 9.1) relies on this.

## Branching strategy

- `main` is the integration branch.
- Each teammate: `git checkout -b <track>/<feature>` e.g. `a/scout-weather`, `b/war-room-leftrail`, `c/sql-guard`.
- Open PRs into `main` when a Task (or cohesive Task group) is ready. No force-push to main.
- Keep PRs small — one Task or tightly-related group per PR.
- CI must be green before merging.

## Shared environment

- Dev Postgres: `docker run --name supplai-pg -e POSTGRES_PASSWORD=postgres -e POSTGRES_DB=supplai -p 5432:5432 -d postgres:16` (one teammate runs this locally; the others run their own identical container).
- `.env.local` (gitignored) with `GEMINI_API_KEY` and `TAVILY_API_KEY` — get from shared 1Password vault.
- Two Postgres DBs: `supplai` (dev data, manually seeded), `supplai_test` (pytest, auto-TRUNCATEd).
- After merging someone else's schema change: `uv run alembic upgrade head` to apply.

## Pairing + unblock rules (from PRD §10.3)

- If you're stuck >90 min: ping. No silent struggles.
- OpenClaw is a known-blocked dep (see `docs/runbook.md`). Plan A's Task 7.3 depends on Eragon providing install path.
- Frontend design review: Teammate B consults the `/ui-ux-pro-max`, `taste`, `impeccable`, `emilkowalski-animation` skills at hours 6, 18, 30. Kill anything that looks shadcn-default.

## Demo-day quality gates (Phase 12.8)

All three must pass for submission. Every teammate owns a slice:

- [ ] `uv run ruff check .` clean — **A + C**
- [ ] `uv run ruff format --check .` clean — **A + C**
- [ ] `uv run mypy --strict backend/db backend/schemas backend/llm backend/agents/base.py` clean — **A + C**
- [ ] `uv run pytest` green — **A + C**
- [ ] `grep -r "smtplib\|sendmail\|smtp" backend/` empty — **A**
- [ ] `pnpm -C web lint && pnpm -C web typecheck && pnpm -C web build` green — **B**
- [ ] `pnpm -C web test:e2e` 5/5 scenarios, 5 consecutive runs — **C** (runs backend + agents)
- [ ] Lighthouse Perf ≥90, A11y ≥95 on War Room — **B**
- [ ] 3× manual dry-run matches pitch script — **all**
