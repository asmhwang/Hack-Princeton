"use client";

import { useState, type ReactNode } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MotionConfig } from "motion/react";
import { useLiveUpdates } from "@/lib/ws-client";

function LiveUpdatesProvider({ children }: { children: ReactNode }) {
  useLiveUpdates();
  return children;
}

export function Providers({ children }: { children: ReactNode }) {
  const [queryClient] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            staleTime: 15_000,
            retry: 1,
            refetchOnWindowFocus: false,
          },
        },
      }),
  );

  return (
    <QueryClientProvider client={queryClient}>
      <MotionConfig reducedMotion="user" transition={{ duration: 0.2, ease: "easeOut" }}>
        <LiveUpdatesProvider>{children}</LiveUpdatesProvider>
      </MotionConfig>
    </QueryClientProvider>
  );
}
