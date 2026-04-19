"use client";

import { useState } from "react";
import { motion, AnimatePresence, LayoutGroup } from "motion/react";
import { useDisruptions } from "@/hooks/useDisruptions";
import { useDeleteDisruption } from "@/hooks/useDeleteDisruption";
import { useWarRoomStore } from "@/lib/store";
import { DisruptionCard } from "@/components/disruption/DisruptionCard";

const spring = { type: "spring" as const, stiffness: 260, damping: 26 };
const FILTERS = ["active", "monitoring", "resolved"] as const;
type Filter = (typeof FILTERS)[number];

function DisruptionListSkeleton() {
  return (
    <>
      {[0, 1, 2].map((i) => (
        <div
          key={i}
          style={{
            height: 110,
            marginBottom: 8,
            borderRadius: 5,
            border: "1px solid var(--color-border)",
            padding: 12,
            background: "var(--color-bg)",
            display: "flex",
            flexDirection: "column",
            justifyContent: "space-between",
          }}
        >
          <div style={{ display: "flex", justifyContent: "space-between" }}>
            <div className="shimmer" style={{ width: 56, height: 16, borderRadius: 3 }} />
            <div className="shimmer" style={{ width: 22, height: 12, borderRadius: 3 }} />
          </div>
          <div className="shimmer" style={{ width: "85%", height: 12, borderRadius: 3 }} />
          <div className="shimmer" style={{ width: "60%", height: 10, borderRadius: 3 }} />
          <div className="shimmer" style={{ width: 70, height: 14, borderRadius: 3 }} />
        </div>
      ))}
    </>
  );
}

export function LeftRail() {
  const [filter, setFilter] = useState<Filter>("active");
  const { data = [], isLoading } = useDisruptions(filter);
  const selectedDisruptionId = useWarRoomStore((s) => s.selectedDisruptionId);
  const setSelectedDisruptionId = useWarRoomStore((s) => s.setSelectedDisruptionId);
  const deleteDisruption = useDeleteDisruption();

  const sorted = [...data].sort((a, b) => {
    const ta = Date.parse(a.detected_at ?? a.first_seen_at ?? "") || 0;
    const tb = Date.parse(b.detected_at ?? b.first_seen_at ?? "") || 0;
    return tb - ta;
  });

  return (
    <aside
      style={{
        height: "100%",
        overflow: "hidden",
        display: "flex",
        flexDirection: "column",
        borderRight: "1px solid var(--color-border)",
        background: "var(--color-surface)",
      }}
    >
      {/* Header / filter tabs */}
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
        <div style={{ display: "flex", gap: 14, alignItems: "center" }}>
          {FILTERS.map((f) => (
            <button
              key={f}
              type="button"
              onClick={() => setFilter(f)}
              style={{
                background: "none",
                border: "none",
                padding: 0,
                fontSize: 12,
                textTransform: "capitalize",
                color: filter === f ? "var(--color-text)" : "var(--color-text-subtle)",
                fontWeight: filter === f ? 500 : 400,
                cursor: "pointer",
              }}
            >
              {f}
            </button>
          ))}
        </div>
        <span className="tnum" style={{ fontSize: 11, color: "var(--color-text-subtle)", fontFamily: "var(--font-mono)" }}>
          {sorted.length}
        </span>
      </div>

      {/* List */}
      <div style={{ flex: 1, overflow: "auto", padding: "10px 10px 20px" }}>
        {isLoading ? (
          <DisruptionListSkeleton />
        ) : (
          <LayoutGroup>
            <AnimatePresence initial={false}>
              {sorted.map((d, i) => (
                <motion.div
                  key={d.id}
                  layout
                  initial={{ opacity: 0, x: -8 }}
                  animate={{ opacity: 1, x: 0 }}
                  exit={{ opacity: 0, x: -8 }}
                  transition={{ ...spring, delay: i * 0.02 }}
                  style={{ marginBottom: 8 }}
                >
                  <DisruptionCard
                    disruption={d}
                    selected={selectedDisruptionId === d.id}
                    onSelect={() =>
                      setSelectedDisruptionId(selectedDisruptionId === d.id ? null : d.id)
                    }
                    onDelete={() => {
                      if (
                        typeof window !== "undefined" &&
                        !window.confirm(`Delete "${d.title}"? This cannot be undone.`)
                      ) {
                        return;
                      }
                      deleteDisruption.mutate(d.id);
                    }}
                  />
                </motion.div>
              ))}
            </AnimatePresence>
          </LayoutGroup>
        )}

        {!isLoading && sorted.length === 0 && (
          <div
            style={{
              marginTop: 4,
              padding: "10px 12px",
              borderRadius: 5,
              border: "1px dashed var(--color-border-strong)",
              color: "var(--color-text-subtle)",
              fontSize: 12,
            }}
          >
            No {filter} disruptions
          </div>
        )}

        <div
          style={{
            marginTop: 12,
            padding: "10px 12px",
            borderRadius: 5,
            border: "1px dashed var(--color-border-strong)",
            color: "var(--color-text-subtle)",
            fontSize: 12,
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
          }}
        >
          <span>Scanning 47 signals</span>
          <span style={{ fontFamily: "var(--font-mono)", fontSize: 10 }}>·····</span>
        </div>
      </div>

      {/* Footer */}
      <div
        style={{
          borderTop: "1px solid var(--color-border)",
          padding: "8px 14px",
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          fontSize: 11,
          color: "var(--color-text-subtle)",
          fontFamily: "var(--font-mono)",
        }}
      >
        <span>SCOUT · live</span>
        <span>↻ auto</span>
      </div>
    </aside>
  );
}
