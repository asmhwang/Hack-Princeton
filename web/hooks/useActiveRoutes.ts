"use client";

import { useQuery } from "@tanstack/react-query";
import { apiClient } from "@/lib/api-client";
import { queryKeys } from "@/lib/query-keys";

/**
 * Active shipment routes across all currently-active disruptions, for the
 * globe. Served by Stream 2's GET /api/disruptions/active/routes; while that
 * endpoint is 404 the api-client returns a hand-rolled mock set.
 *
 * Refetches every 20s as a polling fallback; live invalidation happens from
 * the WS `new_disruption` / `new_impact` / `new_mitigation` relay (see
 * useLiveUpdates).
 */
export function useActiveRoutes() {
  return useQuery({
    queryKey: queryKeys.activeRoutes,
    queryFn: () => apiClient.getActiveRoutes(),
    refetchInterval: 20_000,
  });
}
