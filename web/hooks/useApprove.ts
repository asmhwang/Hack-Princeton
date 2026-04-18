"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "@/lib/api-client";
import { queryKeys } from "@/lib/query-keys";

export function useApprove(disruptionId: string | null) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (mitigationId: string) => apiClient.approveMitigation(mitigationId),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.exposure });
      void queryClient.invalidateQueries({ queryKey: queryKeys.activity });
      if (disruptionId) {
        void queryClient.invalidateQueries({ queryKey: queryKeys.mitigations(disruptionId) });
        void queryClient.invalidateQueries({ queryKey: queryKeys.impact(disruptionId) });
      }
    },
  });
}
