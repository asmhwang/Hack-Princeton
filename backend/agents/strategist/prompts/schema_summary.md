# suppl.ai DB Schema Summary (Strategist cached context)

Fed once per Strategist process into
`LLMClient.cached_context(key="strategist_schema_v1", content=...)` so every
`with_tools` call reuses the same Gemini cached-content handle.

## Tables the Strategist reads

### `impact_reports` / `affected_shipments`
- `impact_reports.id UUID PK`, `disruption_id UUID FK`, `total_exposure`,
  `units_at_risk`, `cascade_depth`, `sql_executed TEXT`, `reasoning_trace JSONB`.
- `affected_shipments(impact_report_id, shipment_id)` — exposure per shipment.

### `disruptions` (read-only)
- `category ∈ {weather, policy, news, logistics, macro, industrial}`, `severity INT`,
  `lat / lng / radius_km`, `region`.

### `shipments`
- `id TEXT PK`, `po_id`, `supplier_id`, `origin_port_id`, `dest_port_id`,
  `status ∈ {planned, in_transit, rerouting, arrived}`, `mode`, `eta DATE`, `value NUMERIC`.

### `suppliers`, `ports`, `skus`, `purchase_orders`, `customers`
- See Analyst schema; same tables. Use `alternate_suppliers_for_sku`,
  `alternate_ports_near` to query candidates.

## Tables the Strategist writes

### `mitigation_options` (one row per option)
- `id UUID PK`, `impact_report_id UUID FK`, `option_type TEXT`, `description TEXT`,
  `delta_cost NUMERIC ≥ 0`, `delta_days INT`, `confidence NUMERIC in [0,1]`,
  `rationale TEXT`, `status ∈ {pending, approved, dismissed}` default `pending`.

### `draft_communications` (three per mitigation — supplier / customer / internal)
- `id UUID PK`, `mitigation_id UUID FK`, `recipient_type TEXT`, `recipient_contact TEXT`,
  `subject`, `body`, `created_at`, `sent_at` — **always NULL** (never sent).

### `agent_log` (OpenClaw action trace)
- Every mutation emits `event_type='openclaw.<ActionName>'` with the
  inbound args / output IDs in `payload JSONB` for judge-visible depth.

## Event bus

- Subscribes to **`new_impact`** — payload is JSON
  `{"id": <impact_uuid>, "disruption_id": <uuid>, "total_exposure": <decimal-string>}`.
- Emits **`new_mitigation`** after persistence with
  `{"impact_report_id": <uuid>, "mitigation_ids": [<uuid>, ...]}`.

## Conventions

- Dollar amounts `NUMERIC`; serialize `Decimal → str` to preserve precision.
- Never call INSERT/UPDATE/DELETE directly — wrap all writes in
  `backend.agents.strategist.actions.openclaw_actions`.
- `draft_communications.sent_at` is always NULL — no SMTP, ever.
