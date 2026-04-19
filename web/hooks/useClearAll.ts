"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "@/lib/api-client";
import { useWarRoomStore } from "@/lib/store";

export function useClearAll() {
  const queryClient = useQueryClient();
  const setSelectedDisruptionId = useWarRoomStore((s) => s.setSelectedDisruptionId);

  return useMutation({
    mutationFn: () => apiClient.clearAll(),
    onSuccess: () => {
      setSelectedDisruptionId(null);
      void queryClient.invalidateQueries();
    },
  });
}
