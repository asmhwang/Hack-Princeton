"use client";

import { useQuery } from "@tanstack/react-query";
import { apiClient } from "@/lib/api-client";
import { queryKeys } from "@/lib/query-keys";

export function useDisruptions(status = "active") {
  return useQuery({
    queryKey: queryKeys.disruptions(status),
    queryFn: () => apiClient.listDisruptions(status),
  });
}

export function useExposureSummary() {
  return useQuery({
    queryKey: queryKeys.exposure,
    queryFn: () => apiClient.getExposureSummary(),
    refetchInterval: 30_000,
  });
}

export function useDisruption(id: string | null) {
  return useQuery({
    queryKey: id ? queryKeys.disruption(id) : ["disruption", "none"],
    queryFn: () => (id ? apiClient.getDisruption(id) : Promise.resolve(null)),
    enabled: Boolean(id),
  });
}

export function useImpact(disruptionId: string | null) {
  return useQuery({
    queryKey: disruptionId ? queryKeys.impact(disruptionId) : ["impact", "none"],
    queryFn: () => (disruptionId ? apiClient.getImpact(disruptionId) : Promise.resolve(null)),
    enabled: Boolean(disruptionId),
  });
}

export function useMitigations(disruptionId: string | null) {
  return useQuery({
    queryKey: disruptionId ? queryKeys.mitigations(disruptionId) : ["mitigations", "none"],
    queryFn: () => (disruptionId ? apiClient.getMitigations(disruptionId) : Promise.resolve([])),
    enabled: Boolean(disruptionId),
  });
}

export function useActivityFeed() {
  return useQuery({
    queryKey: queryKeys.activity,
    queryFn: () => apiClient.getActivityFeed(),
  });
}

export function useAnalytics(range: string = "7d") {
  return useQuery({
    queryKey: queryKeys.analytics(range),
    queryFn: () => apiClient.getAnalytics(range),
  });
}
