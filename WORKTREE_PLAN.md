# WT `hp-analyst` — `a/analyst`

> **Parent plan:** `docs/superpowers/plans/2026-04-18-plan-A-agents-infra.md` (Task A.5)
> **Master task specs:** `docs/superpowers/plans/2026-04-18-suppl-ai-implementation.md`
>   - Task 6.1 Impact processor tool loop (line 1735)
>   - Task 6.2 Rules-based fallback by category (line 1752)
>   - Task 6.3 Analyst `main.py` (line 1762)
> **Coordination:** `docs/superpowers/plans/2026-04-18-parallel-coordination.md`
> **Branch:** `a/analyst` → PR into `main` (branched from `7c5a5b2`)
> **Est effort:** ~5h (strict TDD on tool loop)

## Charter

Analyst VM subscribes to `new_disruption`; for each disruption, runs Gemini Pro in the function-calling loop using the 7 analyst tools (shipped via `backend/llm/tools/analyst_tools.py`). Produces: `ImpactReport` + `AffectedShipment[]` + synthesized-SQL string (explainability) + reasoning trace. Writes rows; emits `new_impact`. End-to-end ≤ 30s on typhoon fixture.

All upstream deps shipped:
- `AgentBase`, `EventBus`, `LLMClient.with_tools`, `LLMClient.cached_context`
- 7 analyst tools in `backend/llm/tools/analyst_tools.py` (Plan C Task 2.6, commit `d01fc0b`)
- Pydantic schemas: `ImpactReport`, `AffectedShipment`, etc. in `backend/schemas/impact.py`
- SQL guard `backend/api/validators/sql_guard.py` for storing `impact_reports.sql_executed`

## Deliverables

| # | File | Type | Purpose |
|---|---|---|---|
| 1 | `backend/agents/analyst/__init__.py` | new | package marker |
| 2 | `backend/agents/analyst/processors/__init__.py` | new | package marker |
| 3 | `backend/agents/analyst/processors/impact.py` | new | `build_impact_report(disruption_id)` — tool loop + persist |
| 4 | `backend/agents/analyst/processors/fallback.py` | new | rules-based template per `disruption.category`; no LLM |
| 5 | `backend/agents/analyst/prompts/impact_system.md` | new | system prompt: Analyst role + tool descriptions + final schema ref |
| 6 | `backend/agents/analyst/prompts/schema_summary.md` | new | DB schema summary fed via `LLMClient.cached_context` once per process |
| 7 | `backend/agents/analyst/main.py` | new | `class AnalystAgent(AgentBase)` with `channels=["new_disruption"]`; `on_notify` orchestrates impact → fallback → NOTIFY |
| 8 | `backend/agents/analyst/config.py` | new | model choice (pro), max tool iters, schema-cache TTL |
| 9 | `backend/agents/analyst/state.py` | new | last-processed disruption cursor, tool-call counts |
| 10 | `backend/tests/test_impact.py` | new | TDD: mocked tool loop produces ImpactReport; `total_exposure` within ±10% of $2.3M; reasoning_trace len==4 |
| 11 | `backend/tests/test_fallback.py` | new | TDD: on `LLMValidationError`, fallback still writes report per category template |
| 12 | `backend/tests/test_analyst_main.py` | new | integration: publish `NOTIFY new_disruption, <uuid>` → row + `new_impact` within 30s |
| 13 | `backend/tests/fixtures/typhoon.py` | new (or augment) | seeds 13–15 shipments around Shenzhen with known ground-truth $2.3M exposure |

## TDD sequence

```
1. cd /Users/ahwang06/Documents/hackprinceton/hp-analyst

# Phase A: impact processor
2. Write backend/agents/analyst/prompts/impact_system.md (role + tool table + final schema).
3. Write backend/tests/fixtures/typhoon.py (seed helper: 13–15 shipments, known $2.3M ground truth).
4. Write backend/tests/test_impact.py per master plan §6.1 Step 2 (mock `LLMClient.with_tools`).
5. pytest → fails.
6. Implement backend/agents/analyst/processors/impact.py:
   - load_disruption(disruption_id) -> Disruption
   - build_prompt(disruption, cached_schema_handle) -> str
   - result, trace = await llm.with_tools(prompt, analyst_tools, final_schema=ImpactReport)
   - persist: impact_reports row + AffectedShipment upserts (ON CONFLICT DO NOTHING) + concatenate synthesized_sql.
   - NOTIFY new_impact with payload {"id": uuid, "disruption_id": uuid, "total_exposure": "<decimal>"}.
7. Green.

# Phase B: fallback
8. Write backend/tests/test_fallback.py.
9. Implement backend/agents/analyst/processors/fallback.py — rules-based templates per DisruptionCategory (weather: radius query, policy: SKU-family, logistics: port-filter, etc.) calling analyst_tools DIRECTLY, no LLM.
10. Green.

# Phase C: main.py + integration
11. Write backend/agents/analyst/main.py (subclass AgentBase, channels=["new_disruption"]).
12. Write backend/agents/analyst/state.py + config.py.
13. Write backend/tests/test_analyst_main.py: publish NOTIFY → assert row within 30s.
14. uv run pytest backend/tests/test_impact.py backend/tests/test_fallback.py backend/tests/test_analyst_main.py -v
15. uv run mypy --strict backend/agents/analyst
16. uv run ruff check backend/agents/analyst backend/tests

17. Commits:
    - "feat(analyst): impact processor with Gemini tool loop"
    - "feat(analyst): rules-based fallback by disruption category"
    - "feat(analyst): main agent wires tool loop + fallback + NOTIFY new_impact"

18. git push -u origin a/analyst
19. gh pr create --base main --title "feat(analyst): impact reports via Gemini tool-calling" --body "Closes tasks 6.1-6.3"
```

## `build_impact_report` contract

```python
async def build_impact_report(disruption_id: UUID) -> UUID:
    """Load disruption → run LLMClient.with_tools(analyst_tools, final_schema=ImpactReport)
       → persist impact_reports row + AffectedShipment upserts + NOTIFY new_impact.
       Returns impact_reports.id.
       Raises LLMValidationError (caller catches → invokes fallback)."""
```

Prompt body (concatenation):
1. `impact_system.md` (role + tool descriptions + ImpactReport schema ref).
2. **Cached context handle** to `schema_summary.md` via `LLMClient.cached_context("analyst_schema_v1", schema_md)` — memoized once per process.
3. Disruption context (title, category, severity, region_label, source_signal_ids).
4. Instruction: "End with a structured ImpactReport."

Tool set passed to `with_tools`: the 7 tools from `backend/llm/tools/analyst_tools.py`:
- `shipments_touching_region`
- `purchase_orders_for_skus`
- `customers_by_po`
- `exposure_aggregate`
- `alternate_suppliers_for_sku`
- `alternate_ports_near`
- `shipment_history_status`

Each tool returns `{"rows": [...], "synthesized_sql": "...", "row_count": N}`. Concatenate `synthesized_sql` across tool calls into `impact_reports.sql_executed` for the explainability drawer.

Persist steps (in a single DB tx):
```python
async with session.begin():
    ir = ImpactReport(... from result ..., sql_executed=synthesized_sql_concat, reasoning_trace={"tool_calls": [t.model_dump() for t in trace]})
    session.add(ir)
    for s in result.affected_shipments:
        stmt = insert(AffectedShipment).values(...).on_conflict_do_nothing(...)
        await session.execute(stmt)
await bus.publish("new_impact", json.dumps({"id": str(ir.id), "disruption_id": str(disruption_id), "total_exposure": str(ir.total_exposure)}))
```

## Fallback rules (by `DisruptionCategory`)

| Category | Template |
|---|---|
| `weather` | radius search around `disruption.centroid_lat/lng` at 500km → shipments → POs → customers → exposure |
| `policy` | filter shipments by `sku.category` matching disruption's affected SKU families |
| `logistics` | filter shipments by origin/destination `port_id` in `disruption.affected_port_ids` |
| `macro` | freight-rate / fuel proxy: mark all in-transit shipments as exposed to delta; low-confidence report |
| `labor` | same as logistics (port strike) |

Each template chains 3–4 `analyst_tools` calls directly (no LLM). Produces ImpactReport with `source="fallback"` in `reasoning_trace`.

## Ship/consume contracts

- **SHIPS**:
  - `AnalystAgent` — systemd unit `supplai-analyst.service` already on main (from WT3 `cf19e06`). `ExecStart=/usr/local/bin/uv run python -m backend.agents.analyst.main`.
  - `NOTIFY new_impact` on every impact report (success or fallback).
- **CONSUMES** (all on main):
  - `backend.agents.base.AgentBase` (channels=["new_disruption"])
  - `backend.db.bus.EventBus`
  - `backend.llm.client.LLMClient` (`.with_tools`, `.cached_context`, `.structured`)
  - `backend.llm.tools.analyst_tools` (7 tools)
  - `backend.schemas.{ImpactReport, AffectedShipment}` + `DisruptionRecord`, `DisruptionCategory`
  - `backend.db.session`
  - `backend.api.validators.sql_guard.SqlSafetyError` — validate the concatenated `sql_executed` before persist (defense in depth; guard rejects anything other than single SELECT).

## Definition of done

- [ ] `uv run pytest backend/tests/test_impact.py backend/tests/test_fallback.py backend/tests/test_analyst_main.py -v` green.
- [ ] `uv run mypy --strict backend/agents/analyst` clean.
- [ ] `uv run ruff check backend/agents/analyst backend/tests/test_impact.py backend/tests/test_fallback.py backend/tests/test_analyst_main.py` clean.
- [ ] Typhoon fixture: `NOTIFY new_disruption` → ImpactReport in `impact_reports` with `total_exposure` within ±10% of $2.3M within 30s.
- [ ] `reasoning_trace.tool_calls` length ≥3 on typhoon; matches tool names from `analyst_tools.py`.
- [ ] Fallback path: forcing `LLMValidationError` yields a report (possibly less detailed) — still written, `source="fallback"`.
- [ ] `impact_reports.sql_executed` non-empty and passes `SqlSafetyError`-style validation.
- [ ] `grep -r "smtplib\|sendmail\|smtp" backend/agents/analyst/` empty.
- [ ] PR merged into `main` before Strategist WT7 starts (Strategist subscribes to `new_impact`).

## Known gotchas

- **Gemini Pro vs Flash:** use **Pro** for Analyst tool loop (complex reasoning); Flash is fine for Scout classifier. Configure via `LLMClient(model="pro")`.
- **Tool loop max iterations:** `max_iters=6` default. If Gemini exceeds, `with_tools` raises — catch + invoke fallback.
- **Schema cache TTL:** `cached_context` creates a server-side cached-content handle. Gemini API minimum: ~32K tokens. If `schema_summary.md` below threshold, `cached_context` no-ops and returns empty string per WT2 plan — caller falls back to uncached prompt. Document behavior in logs.
- **`ImpactReport.total_exposure` is Decimal**; NOTIFY payload must `str(decimal)` to preserve precision — frozen in coordination doc §2.
- **Race on same `disruption_id`:** two Analyst instances could double-write. Use `INSERT ... ON CONFLICT (disruption_id) DO NOTHING` on `impact_reports` (one per disruption; the unique index enforces).
- **Reasoning trace size:** `trace` list can balloon. Truncate each tool's `rows` array to first 10 entries before persisting into `reasoning_trace` JSON — full data is already in `impact_reports.sql_executed` + `affected_shipments`.
- **Tool error handling:** if a tool callable raises, the loop should log + return `{"error": str}` as the function_response so Gemini can choose another tool — never crash the loop.
- **NOTIFY order matters for Plan B UI:** Plan B animates impact cards in arrival order. Ensure `new_impact` NOTIFY is the **last** thing after the tx commits.

## Out of scope

- Schema changes.
- Adding new analyst tools — would require coordination (all 3 plans).
- Strategist (Phase 7) — next WT.
- Live VM smoke test (Task 12.3) — future WT.

## Escalation

- Gemini consistently invalid JSON → check `response_schema` binding in `with_tools` (final_schema param). Do not disable retry. Escalate if persistent.
- Ground-truth typhoon exposure drifts from $2.3M → `fixtures/typhoon.py` seed may have changed in a teammate's PR. Re-verify with `exposure_aggregate` tool directly before debugging the LLM.
- OpenClaw NOT needed here (Strategist only).
