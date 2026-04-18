# suppl.ai DB Schema Summary (Analyst cached context)

This document is fed once per Analyst process into
`LLMClient.cached_context(key="analyst_schema_v1", content=...)` so every
`with_tools` call reuses the same Gemini cached-content handle.

## Tables the Analyst reads

### `ports`
- `id TEXT PK` (e.g. `PORT-SZX`), `name`, `country`, `lat NUMERIC`, `lng NUMERIC`, `modes TEXT[]`
- ~30 rows. Lookup by id; filter by proximity via haversine in tools.

### `suppliers`
- `id TEXT PK` (e.g. `SUP-E-001`), `name`, `country`, `region`, `tier INT`, `industry`, `reliability_score NUMERIC`, `categories TEXT[]`, `lat`, `lng`
- ~50 rows. Industries: electronics, apparel, food, pharma, industrial.

### `skus`
- `id TEXT PK`, `description`, `family`, `industry`, `unit_cost`, `unit_revenue`

### `customers`
- `id TEXT PK`, `name`, `tier TEXT` (gold|silver|bronze), `sla_days INT`, `contact_email`

### `purchase_orders`
- `id TEXT PK`, `customer_id FK`, `sku_id FK`, `qty INT`, `due_date DATE`, `revenue NUMERIC`, `sla_breach_penalty NUMERIC`
- ~200 rows.

### `shipments`
- `id TEXT PK` (e.g. `SHP-00001`), `po_id FK`, `supplier_id FK`, `origin_port_id FK`, `dest_port_id FK`
- `status` ∈ `{planned, in_transit, rerouting, arrived}` (Analyst focuses on in_transit/planned)
- `mode TEXT`, `eta DATE`, `value NUMERIC`
- ~500 rows.

### `disruptions` (read-only for Analyst; written by Scout)
- `id UUID PK`, `title`, `summary`, `category ∈ {weather, policy, news, logistics, macro, industrial}`
- `severity INT 1..5`, `region TEXT`, `lat NUMERIC`, `lng NUMERIC`, `radius_km NUMERIC`
- `source_signal_ids UUID[]`, `confidence NUMERIC`, `status ∈ {active, resolved}`

## Tables the Analyst writes

### `impact_reports` (one row per disruption)
- `id UUID PK`, `disruption_id UUID FK`, `total_exposure NUMERIC`, `units_at_risk INT`
- `cascade_depth INT 1..5`, `sql_executed TEXT` (concatenated synthesized SQL; display-only)
- `reasoning_trace JSONB` (tool_calls + final_reasoning)

### `affected_shipments` (one row per (impact_report_id, shipment_id))
- `impact_report_id UUID FK`, `shipment_id TEXT FK`, `exposure NUMERIC`, `days_to_sla_breach INT|NULL`
- PK = `(impact_report_id, shipment_id)`. Use `ON CONFLICT DO NOTHING` on retries.

## Event bus

The Analyst subscribes to channel **`new_disruption`** — payload is the UUID
of the newly-inserted disruption row. After the impact report persists, the
Analyst emits **`new_impact`** with payload
`{"id": "<impact_report_uuid>", "disruption_id": "<disruption_uuid>", "total_exposure": "<decimal-string>"}`.

## Conventions

- Dollar amounts are `NUMERIC`; serialized as Decimal → str to preserve precision.
- Coordinates are plain `NUMERIC(lat, lng)`, not PostGIS.
- IDs with `-` dashes are TEXT; UUIDs are Postgres `uuid` type.
- Dedupe + idempotency live at the DB layer — upserts use `ON CONFLICT DO NOTHING`.
