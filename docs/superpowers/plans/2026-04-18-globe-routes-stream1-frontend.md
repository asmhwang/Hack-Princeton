# Stream 1 — Frontend + contract shims

> **Partner stream:** `2026-04-18-globe-routes-stream2-backend.md` (teammate)
> **Context:** Two bugs on the War Room dashboard:
> 1. Active-disruptions sidebar + bottom list show "No active disruptions" even though the top bar counter (22 active) is correct. Root cause: `disruptionSchema` in `web/types/schemas.ts` is `.strict()` and the backend sends fields (`source_signal_ids`, `confidence`) the schema doesn't know about — zod throws, React Query returns empty.
> 2. Globe uses hard-coded `demoRoutes` instead of real shipment routes from the DB.

## Owner

You (frontend). No backend edits — only read backend's OpenAPI spec when integrating.

## Shared API contract — **FROZEN**

**Do not change without pinging Stream 2.** Stream 2 implements the endpoint against this shape.

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

### 1. Loosen zod schemas — **fixes Bug 1 immediately**

File: `web/types/schemas.ts`

- [ ] `disruptionSchema`: remove `.strict()` (or swap to `.passthrough()`). Also add `source_signal_ids: z.array(z.string()).optional()` and `confidence: z.number().optional().nullable()` so we don't drop useful fields silently.
- [ ] `signalSchema`: remove `.strict()`. The backend `SignalRecord` carries a pile of fields the frontend doesn't care about (`source_name`, `summary`, `lat`, `lng`, `radius_km`, `source_urls`, `confidence`, `raw_payload`, `dedupe_hash`, `promoted_to_disruption_id`) — all should be allowed through. Also: swap `source_url` → `source_urls: z.array(z.string()).optional()` if we want to actually use it, or leave the existing `source_url` as-is and let it be undefined.
- [ ] `affectedShipmentSchema`: make `sku`, `customer_name`, `po_number`, `origin`, `destination`, `status` **optional** — backend's `AffectedShipmentEntry` only sends `shipment_id`, `exposure`, `days_to_sla_breach`. Without this the impact-report parse fails and the affected-shipments table silently stays empty. Remove `.strict()`.
- [ ] `impactReportSchema`: remove `.strict()`. Fields in backend `ImpactReportRecord` not yet in the zod schema: `id`, `generated_at` (both already present actually — verify). Also: `cascade_depth` exists in both.
- [ ] `mitigationOptionSchema`: remove `.strict()`. Backend adds `drafts: list[DraftCommunicationRecord]` via `MitigationWithDrafts` that frontend might not know about.

After this, refresh the dashboard. Sidebar + bottom disruption list should populate.

### 2. Add `activeRouteSchema` and Type

File: `web/types/schemas.ts`

- [ ] Define `activeRouteSchema` matching the contract above.
- [ ] Export `ActiveRoute` type alias via `z.infer`.

### 3. API client + hook

File: `web/lib/api-client.ts`

- [ ] Add `getActiveRoutes(): Promise<ActiveRoute[]>` calling `/api/disruptions/active/routes`, validated by `activeRouteSchema.array()`, with fallback `[]`.

File: `web/lib/query-keys.ts`

- [ ] Add `activeRoutes: ["disruptions", "active", "routes"] as const`.

File: `web/hooks/useActiveRoutes.ts` (new)

- [ ] Export `useActiveRoutes()` hook with:
  - `queryKey: queryKeys.activeRoutes`
  - `refetchInterval: 20_000` (polling fallback if WS drops)
- [ ] Invalidation: wire into the existing `useLiveUpdates` pipeline so that `new_disruption`, `new_impact`, and `new_mitigation` WS events all invalidate `queryKeys.activeRoutes` (in addition to whatever they already invalidate).

### 4. `ActiveRoute → GlobeRoute` adapter

File: `web/components/globe/routes.ts`

- [ ] Add `routesFromActiveRoutes(rows: ActiveRoute[]): GlobeRoute[]`. Map fields 1:1 (they're close). The only non-trivial bits:
  - `GlobeRoute.id` ← `ActiveRoute.id` (or fall back to a composite if needed)
  - `GlobeRoute.origin` ← `ActiveRoute.origin_name`
  - `GlobeRoute.destination` ← `ActiveRoute.destination_name`
  - `GlobeRoute.recommendation` / `reason` don't have contract fields — synthesize or leave empty strings (these render in the hover tooltip / detail panel).

### 5. Wire into the War Room page

File: `web/app/(dashboard)/page.tsx`

- [ ] Import `useActiveRoutes` + `routesFromActiveRoutes`.
- [ ] Replace the `<InteractiveGlobePanel routes={demoRoutes} ... />` call:
  ```tsx
  const { data: activeRoutes = [] } = useActiveRoutes();
  const routes = activeRoutes.length > 0 ? routesFromActiveRoutes(activeRoutes) : demoRoutes;
  // ... <InteractiveGlobePanel routes={routes} ... />
  ```
- [ ] Keep `demoRoutes` as the fallback — with an empty active set (cold-start or post-clear), globe should still look populated rather than empty.

### 6. Mock for local testing before Stream 2 lands

To unblock yourself if you finish Phase 1 before the backend endpoint exists:

- [ ] In `getActiveRoutes`, after the `fetch` call, if the response is 404, return a hand-rolled list of 2–3 `ActiveRoute` objects (e.g. Shenzhen→LA typhoon, Busan→Seattle strike) so the globe renders real-looking data during dev. Flag the mock with `// TODO: remove once Stream 2 ships /api/disruptions/active/routes`.

## Definition of done

- [ ] Dashboard sidebar shows the full active-disruptions list (22 rows if seeded that high).
- [ ] Bottom "Active disruptions" table shows rows instead of the empty state.
- [ ] Globe shows real route arcs for each affected shipment across active disruptions, colored by category/status.
- [ ] Empty state (0 active disruptions) falls back to `demoRoutes` so it still looks alive.
- [ ] `pnpm lint` + `pnpm typecheck` clean.
- [ ] Dev server hot-reloads without errors.

## Coordination

- **Contract lock**: see top of file. Do not edit without Stream 2 ack.
- **Mock behavior**: when Stream 2 ships the real endpoint, remove the 404 mock path from `getActiveRoutes`.
- **Testing end-to-end**: after both streams merge, run `uv run python -m backend.scripts.seed_scenario --all --status active`, reload the dashboard, verify the globe fills with non-zero-length arcs.
