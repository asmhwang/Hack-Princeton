"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "@/lib/api-client";
import { queryKeys } from "@/lib/query-keys";
import { useWarRoomStore } from "@/lib/store";

export function useSimulate() {
  const queryClient = useQueryClient();
  const setSimulateInFlight = useWarRoomStore((state) => state.setSimulateInFlight);

  return useMutation({
    mutationFn: (scenario: string) => apiClient.simulate(scenario),
    onMutate: () => setSimulateInFlight(true),
    onSettled: () => {
      setSimulateInFlight(false);
      void queryClient.invalidateQueries({ queryKey: queryKeys.disruptions() });
      void queryClient.invalidateQueries({ queryKey: queryKeys.exposure });
      void queryClient.invalidateQueries({ queryKey: queryKeys.activity });
    },
  });
}
