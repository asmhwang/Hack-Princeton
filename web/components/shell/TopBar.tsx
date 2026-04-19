"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useMemo } from "react";
import { useExposureSummary } from "@/hooks/useDisruptions";
import { useSimulate } from "@/hooks/useSimulate";
import { formatCurrency } from "@/lib/format";
import { useWarRoomStore } from "@/lib/store";

const DEMO_SCENARIO = "typhoon_kaia";

const navItems = [
  { href: "/", label: "War Room" },
  { href: "/analytics", label: "Analytics" },
  { href: "/exec", label: "Exec" },
];

export function TopBar() {
  const { data } = useExposureSummary();
  const simulate = useSimulate();
  const connectionStatus = useWarRoomStore((state) => state.connectionStatus);
  const simulateInFlight = useWarRoomStore((state) => state.simulateInFlight);
  const pathname = usePathname();

  const summary = useMemo(() => {
    const active = data?.active_count ?? 0;
    const exposure = formatCurrency(data?.total_exposure ?? "0");
    return `${active} active | ${exposure} at risk`;
  }, [data]);

  return (
    <header className="grid h-14 grid-cols-[272px_minmax(0,1fr)_340px] border-b border-[var(--color-border)] bg-[var(--color-bg)] max-lg:h-auto max-lg:grid-cols-1">
      <div className="flex items-center border-r border-[var(--color-border)] px-4 max-lg:h-12 max-lg:border-r-0">
        <span className="text-[15px] font-semibold">suppl.ai</span>
      </div>

      <div className="flex items-center justify-between gap-4 px-5 max-lg:min-h-12 max-lg:flex-wrap max-lg:border-t max-lg:border-[var(--color-border)] max-lg:px-4 max-lg:py-2">
        <div className="flex items-center gap-5 max-lg:flex-wrap max-lg:gap-3">
          <nav className="flex items-center gap-4 text-sm">
            {navItems.map(({ href, label }) => {
              const active = href === "/" ? pathname === "/" : pathname.startsWith(href);
              return (
                <Link
                  key={href}
                  href={href}
                  className={`border-b py-1 transition-colors ${
                    active
                      ? "border-[var(--color-info)] text-[var(--color-text)]"
                      : "border-transparent text-[var(--color-text-muted)] hover:text-[var(--color-text)]"
                  }`}
                >
                  {label}
                </Link>
              );
            })}
          </nav>
          <span className="tnum text-sm font-medium text-[var(--color-text)]">{summary}</span>
        </div>

        <button
          type="button"
          onClick={() => simulate.mutate(DEMO_SCENARIO)}
          disabled={simulateInFlight}
          className="inline-flex h-8 items-center rounded border border-[var(--color-border-strong)] bg-[var(--color-surface-raised)] px-3 text-sm font-medium text-[var(--color-text)] transition-colors hover:border-[var(--color-text-muted)] disabled:cursor-not-allowed disabled:opacity-50"
        >
          {simulateInFlight ? "Simulating" : "Simulate event"}
        </button>
      </div>

      <div className="flex items-center justify-end border-l border-[var(--color-border)] px-4 max-lg:hidden">
        <span
          className={`text-xs ${
            connectionStatus === "connected"
              ? "text-[var(--color-ok)]"
              : connectionStatus === "connecting"
                ? "text-[var(--color-warn)]"
                : "text-[var(--color-text-muted)]"
          }`}
        >
          WebSocket: {connectionStatus}
        </span>
      </div>
    </header>
  );
}
