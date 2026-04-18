"use client";

import { ActivityFeed } from "@/components/agent-activity/ActivityFeed";
import { WsDot } from "@/components/shell/WsDot";
import { useWarRoomStore } from "@/lib/store";

function AgentChip({ label, color }: Readonly<{ label: string; color: string }>) {
  return (
    <span
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: 4,
        fontSize: 10,
        color: "var(--color-text-subtle)",
        fontFamily: "var(--font-mono)",
        textTransform: "uppercase",
        letterSpacing: "0.04em",
      }}
    >
      <span style={{ width: 5, height: 5, borderRadius: 5, background: color }} />
      {label.slice(0, 3)}
    </span>
  );
}

export function RightRail() {
  const connectionStatus = useWarRoomStore((s) => s.connectionStatus);

  return (
    <aside
      style={{
        height: "100%",
        display: "flex",
        flexDirection: "column",
        borderLeft: "1px solid var(--color-border)",
        background: "var(--color-surface)",
        overflow: "hidden",
      }}
    >
      <div
        style={{
          height: 44,
          minHeight: 44,
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          borderBottom: "1px solid var(--color-border)",
          padding: "0 14px",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <WsDot status={connectionStatus} />
          <h2
            style={{
              margin: 0,
              fontSize: 12,
              fontWeight: 500,
              textTransform: "uppercase",
              letterSpacing: "0.08em",
            }}
          >
            Agent activity
          </h2>
        </div>
        <div style={{ display: "flex", gap: 6 }}>
          <AgentChip label="Scout" color="var(--color-cat-logistics)" />
          <AgentChip label="Analyst" color="var(--color-cat-weather)" />
          <AgentChip label="Strategist" color="var(--color-cat-macro)" />
        </div>
      </div>
      <ActivityFeed />
    </aside>
  );
}
