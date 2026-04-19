"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "@/lib/api-client";
import { queryKeys } from "@/lib/query-keys";
import { useWarRoomStore } from "@/lib/store";

export function useDeleteDisruption() {
  const queryClient = useQueryClient();
  const selectedDisruptionId = useWarRoomStore((s) => s.selectedDisruptionId);
  const setSelectedDisruptionId = useWarRoomStore((s) => s.setSelectedDisruptionId);

  return useMutation({
    mutationFn: (id: string) => apiClient.deleteDisruption(id),
    onSuccess: (_data, id) => {
      if (selectedDisruptionId === id) {
        setSelectedDisruptionId(null);
      }
      void queryClient.invalidateQueries({ queryKey: ["disruptions"] });
      void queryClient.invalidateQueries({ queryKey: queryKeys.disruption(id) });
      void queryClient.invalidateQueries({ queryKey: queryKeys.impact(id) });
      void queryClient.invalidateQueries({ queryKey: queryKeys.mitigations(id) });
      void queryClient.invalidateQueries({ queryKey: queryKeys.exposure });
      void queryClient.invalidateQueries({ queryKey: queryKeys.analytics });
      void queryClient.invalidateQueries({ queryKey: queryKeys.activity });
    },
  });
}
