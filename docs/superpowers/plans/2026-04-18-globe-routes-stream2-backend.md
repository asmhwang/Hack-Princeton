# Stream 2 — Backend data layer + reseed

> **Partner stream:** `2026-04-18-globe-routes-stream1-frontend.md` (owner)
> **Context:** Frontend globe needs to render real shipment routes across all active disruptions. Currently impossible because:
> 1. `prime_chain.py` sets `origin_port_id = dest_port_id = port_id` — every seeded shipment is a zero-length "route" sitting at the disruption centroid.
> 2. Backend's `AffectedShipmentEntry` ships only `shipment_id`, `exposure`, `days_to_sla_breach` — no coordinates, no origin/destination names.
> 3. No endpoint joins active disruptions to their affected shipments with port coords for the globe to consume.

## Owner

Teammate (backend). No frontend edits.

## Shared API contract — **FROZEN**

**Do not change without pinging Stream 1.** Stream 1 codes its zod schema + hook against this shape.

```
GET /api/disruptions/active/routes
→ list[ActiveRoute]

ActiveRoute {
  id: str                     // e.g. shipment_id (stable)
  disruption_id: UUID
  disruption_category: "weather" | "policy" | "news" | "logistics" | "macro" | "industrial"
  from: [lat: float, lng: float]     // origin port coords
  to:   [lat: float, lng: float]     // destination port coords
  origin_name: str            // port or city label for tooltips
  destination_name: str
  mode: "ocean" | "air" | "rail" | "truck"
  status: "blocked" | "watch" | "good"   // derived server-side: sev≥4 → blocked, sev==3 → watch, else good
  exposure: str               // decimal as string (matches the rest of the codebase)
  transit_days: int
  carrier: str
}
```

## Tasks

### 1. Per-scenario destinations

Goal: every seeded scenario has a geographically sensible **origin → destination** pair, not origin → origin.

Destinations to use (origin already exists at disruption centroid):

| Scenario          | Origin (existing)   | Destination (new)         | Dest lat, lng    |
|-------------------|---------------------|---------------------------|------------------|
| typhoon_kaia      | Shenzhen            | Los Angeles               | 34.05, -118.24   |
| busan_strike      | Busan               | Seattle                   | 47.61, -122.33   |
| cbam_tariff       | Shanghai (proxy)    | Rotterdam                 | 51.92, 4.48      |
| luxshare_fire     | Kunshan             | Hong Kong                 | 22.32, 114.17    |
| redsea_advisory   | Singapore           | Rotterdam                 | 51.92, 4.48      |

**Implementation options** (pick one):

- [ ] **Option A (minimal):** extend `ScenarioDisruption` in `backend/scripts/scenarios/_types.py` with `destination_name: str`, `destination_lat: float`, `destination_lng: float` fields. Populate in each of the 5 scenario files.
- [ ] **Option B (separate map):** new module `backend/scripts/scenarios/_destinations.py` exporting `DESTINATIONS: dict[str, tuple[str, float, float]]`. Less change to existing scenario dataclasses, easier to diff.

Either works. Option B is less invasive if you want to avoid touching the scenario files.

### 2. Modify `prime_chain.py` to use the destination

File: `backend/scripts/scenarios/prime_chain.py`

- [ ] Add a second `Port` row per scenario with id `PORT-PRIME-<SID[:4].upper()>-DEST`, using destination lat/lng + name from step 1.
- [ ] Shipment inserts: keep `origin_port_id = port_id` (existing), set `dest_port_id = dest_port_id` (new).
- [ ] **Keep shipment IDs stable** (`SHP-PRIME-TYPH-1`, etc.) so `scripts/prime_cache.py` and the frontend's `ACTIVE_SCENARIO_FIXTURES` keep working without changes.
- [ ] Idempotency: both `Port` rows use `on_conflict_do_nothing` — safe to re-run.

### 3. Historical fixtures mirror the same pattern

File: `backend/scripts/seed_helpers.py`

- [ ] Extend `seed_historical_prime_chain` signature with `destination_lat: float`, `destination_lng: float`, `destination_name: str` kwargs.
- [ ] Create the second `Port` row the same way.
- [ ] Flip `dest_port_id` on each shipment to the new port.

File: `backend/scripts/scenarios/demo_fixtures.py`

- [ ] Add destination fields to `HistoricalFixture` dataclass.
- [ ] Populate plausible destinations per historical fixture (e.g. Shanghai→Rotterdam for Typhoon Huan, Thailand→Tokyo for baht spike, etc.).

File: `backend/scripts/seed_history.py`

- [ ] Pass the new kwargs to `seed_historical_prime_chain`.

### 4. New endpoint: `GET /api/disruptions/active/routes`

File: `backend/api/routes/disruptions.py`

- [ ] Add an `ActiveRoute` Pydantic schema matching the frozen contract (put it in `backend/schemas/disruption.py` or a new `backend/schemas/route.py`).
- [ ] Route SQL — one query joining:
  ```
  disruptions ⨝ impact_reports (most recent per disruption)
              ⨝ affected_shipments
              ⨝ shipments
              ⨝ ports AS origin ON shipments.origin_port_id = origin.id
              ⨝ ports AS dest   ON shipments.dest_port_id = dest.id
              ⨝ suppliers (optional, for carrier name)
  WHERE disruptions.status = 'active'
  ```
- [ ] Derive:
  - `status`: `"blocked"` if `severity >= 4`, `"watch"` if `severity == 3`, else `"good"`.
  - `mode`: from `shipments.mode` (fall back to `"ocean"` if null).
  - `carrier`: from `suppliers.name` or fallback `"Unknown"`.
  - `transit_days`: `(shipments.eta - current_date).days` if ETA is in the future, else `0`.
- [ ] Return `list[ActiveRoute]`.

### 5. Wipe + reseed

- [ ] Truncate the prime-scoped rows so the new origin/dest shows up. Suggested:
  ```sql
  DELETE FROM affected_shipments WHERE shipment_id LIKE 'SHP-PRIME-%';
  DELETE FROM shipments WHERE id LIKE 'SHP-PRIME-%';
  DELETE FROM purchase_orders WHERE id LIKE 'PO-PRIME-%';
  DELETE FROM ports WHERE id LIKE 'PORT-PRIME-%';
  -- and so on for suppliers / skus / customers with PRIME prefix
  ```
- [ ] Rerun:
  ```
  uv run python -m backend.scripts.seed_history
  uv run python -m backend.scripts.seed_scenario --all --status active
  ```
- [ ] Spot-check: `SELECT id, origin_port_id, dest_port_id FROM shipments WHERE id LIKE 'SHP-PRIME-%';` — origin and dest should differ per scenario.

### 6. Contract self-test

- [ ] `curl http://localhost:8000/api/disruptions/active/routes | jq '.[0]'` — confirm shape matches the contract exactly.
- [ ] Run `pnpm -C web openapi:gen` on the frontend side so the types file picks up the new endpoint (informational; Stream 1 uses zod, not the generated types, but keeping `types/api.ts` fresh is the team convention).

## Definition of done

- [ ] `GET /api/disruptions/active/routes` returns a non-empty list with at least one `ActiveRoute` per currently-active disruption.
- [ ] Every returned route has `from ≠ to` (distinct origin/destination coords).
- [ ] `uv run ruff check` + `uv run mypy --strict backend/api/routes/disruptions.py backend/schemas` clean.
- [ ] `prime_cache.py` still runs end-to-end (shipment IDs unchanged, FKs intact).

## Coordination

- **Contract lock**: see top of file. Do not edit without Stream 1 ack.
- **Blast radius**: `prime_chain.py` is shared with `scripts/prime_cache.py`. Verify cache priming still works if you have a Gemini key handy; otherwise at least confirm prime_cache.py's imports haven't broken.
- **Shipment ID stability**: don't rename `SHP-PRIME-*` / `PO-PRIME-*` / `SUP-PRIME-*`. Frontend fixtures + cache keys assume those are stable.
