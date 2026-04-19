"use client";

import { useMemo } from "react";
import { motion, AnimatePresence, LayoutGroup } from "motion/react";
import { useActivityFeed } from "@/hooks/useDisruptions";
import { eventTime, formatRelativeTime } from "@/lib/format";
import { useClock } from "@/hooks/useClock";
import { useWarRoomStore } from "@/lib/store";
import type { ActivityItem } from "@/types/schemas";

const spring = { type: "spring" as const, stiffness: 260, damping: 26 };

function agentColor(agent: string): string {
  switch (agent) {
    case "Scout": return "var(--color-cat-logistics)";
    case "Analyst": return "var(--color-cat-weather)";
    case "Strategist": return "var(--color-cat-macro)";
    default: return "var(--color-text-subtle)";
  }
}

function mergeActivity(apiItems: ActivityItem[], localItems: ActivityItem[]) {
  const seen = new Set<string>();
  return [...localItems, ...apiItems].filter((item) => {
    if (seen.has(item.id)) return false;
    seen.add(item.id);
    return true;
  });
}

function ActivityItemRow({ item, isLast }: Readonly<{ item: ActivityItem; isLast: boolean }>) {
  const color = agentColor(item.agent);
  const sevBorder =
    item.severity === "critical" ? "var(--color-critical)"
    : item.severity === "warning" ? "var(--color-warn)"
    : item.severity === "success" ? "var(--color-ok)"
    : null;

  return (
    <div style={{ position: "relative", paddingLeft: 18, paddingBottom: 12 }}>
      {!isLast && (
        <div
          style={{
            position: "absolute",
            left: 5,
            top: 14,
            bottom: 0,
            width: 1,
            background: "var(--color-border)",
          }}
        />
      )}
      <div
        style={{
          position: "absolute",
          left: 2,
          top: 6,
          width: 7,
          height: 7,
          borderRadius: 7,
          background: color,
          border: "2px solid var(--color-surface)",
        }}
      />
      <div
        style={{
          borderLeft: sevBorder ? `2px solid ${sevBorder}` : "none",
          paddingLeft: sevBorder ? 8 : 0,
        }}
      >
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 8, marginBottom: 3 }}>
          <span
            style={{
              fontSize: 11,
              fontWeight: 500,
              color,
              fontFamily: "var(--font-mono)",
              textTransform: "uppercase",
              letterSpacing: "0.04em",
            }}
          >
            {item.agent}
          </span>
          <span className="tnum" style={{ fontSize: 10, color: "var(--color-text-subtle)", fontFamily: "var(--font-mono)" }}>
            {formatRelativeTime(eventTime(item.created_at))}
          </span>
        </div>
        <p style={{ margin: 0, fontSize: 12, lineHeight: "18px", color: "var(--color-text-muted)" }}>
          {item.message}
        </p>
      </div>
    </div>
  );
}

const EMPTY_ITEMS: ActivityItem[] = [
  { id: "empty-scout", agent: "Scout", message: "Waiting for source signals…", created_at: new Date(0).toISOString(), severity: "info" },
  { id: "empty-analyst", agent: "Analyst", message: "Standby", created_at: new Date(0).toISOString(), severity: "info" },
  { id: "empty-strategist", agent: "Strategist", message: "Standby", created_at: new Date(0).toISOString(), severity: "info" },
];

export function ActivityFeed() {
  useClock();
  const { data = [] } = useActivityFeed();
  const localActivity = useWarRoomStore((s) => s.activityFeed);
  const items = useMemo(
    () => mergeActivity(data, localActivity).slice(0, 50),
    [data, localActivity],
  );

  const displayItems = items.length === 0 ? EMPTY_ITEMS : items;

  return (
    <div style={{ flex: 1, overflow: "auto", padding: "10px 12px 20px", position: "relative" }}>
      <LayoutGroup>
        <AnimatePresence initial={false}>
          {displayItems.map((item, i) => (
            <motion.div
              key={item.id}
              layout
              layoutId={`act-${item.id}`}
              initial={{ opacity: 0, x: -8 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: -8 }}
              transition={{ ...spring, delay: Math.min(i, 8) * 0.02 }}
            >
              <ActivityItemRow item={item} isLast={i === displayItems.length - 1} />
            </motion.div>
          ))}
        </AnimatePresence>
      </LayoutGroup>
    </div>
  );
}
