"use client";

import { motion } from "motion/react";
import type { AnalyticsPoint } from "@/types/schemas";
import { formatCurrency } from "@/lib/format";

const spring = { type: "spring" as const, stiffness: 260, damping: 26 };

type ExposureBarsProps = Readonly<{
  title: string;
  data: AnalyticsPoint[];
}>;

export function ExposureBars({ title, data }: ExposureBarsProps) {
  if (data.length === 0) {
    return (
      <section
        style={{
          border: "1px solid var(--color-border)",
          borderRadius: 5,
          background: "var(--color-surface)",
          overflow: "hidden",
        }}
      >
        <div style={{ padding: "12px 16px", borderBottom: "1px solid var(--color-border)" }}>
          <h3 style={{ margin: 0, fontSize: 13, fontWeight: 600 }}>{title}</h3>
        </div>
        <div style={{ padding: "14px 16px", fontSize: 12, color: "var(--color-text-muted)" }}>
          No data available yet.
        </div>
      </section>
    );
  }

  const sorted = [...data].sort((a, b) => Number(b.exposure) - Number(a.exposure));
  const max = Math.max(...sorted.map((d) => Number(d.exposure)));
  const total = sorted.reduce((s, d) => s + Number(d.exposure), 0);

  return (
    <section
      style={{
        border: "1px solid var(--color-border)",
        borderRadius: 5,
        background: "var(--color-surface)",
        overflow: "hidden",
      }}
    >
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          padding: "12px 16px",
          borderBottom: "1px solid var(--color-border)",
        }}
      >
        <div style={{ display: "flex", alignItems: "baseline", gap: 10 }}>
          <h3 style={{ margin: 0, fontSize: 13, fontWeight: 600 }}>{title}</h3>
          <span className="tnum" style={{ fontSize: 11, color: "var(--color-text-subtle)", fontFamily: "var(--font-mono)" }}>
            Σ {formatCurrency(total)} · n={data.length}
          </span>
        </div>
        <span
          style={{
            fontSize: 10,
            color: "var(--color-text-subtle)",
            fontFamily: "var(--font-mono)",
            textTransform: "uppercase",
            letterSpacing: "0.06em",
          }}
        >
          sorted by exposure
        </span>
      </div>

      <div style={{ padding: "14px 16px", display: "flex", flexDirection: "column", gap: 8 }}>
        {sorted.map((row, i) => (
          <div
            key={row.label}
            style={{
              display: "grid",
              gridTemplateColumns: "180px 1fr 110px 50px",
              gap: 14,
              alignItems: "center",
              fontSize: 12,
            }}
          >
            <div
              style={{
                color: "var(--color-text)",
                overflow: "hidden",
                textOverflow: "ellipsis",
                whiteSpace: "nowrap",
              }}
            >
              {row.label}
            </div>
            <div
              style={{
                position: "relative",
                height: 18,
                background: "var(--color-bg)",
                borderRadius: 2,
                overflow: "hidden",
              }}
            >
              <motion.div
                initial={{ width: 0 }}
                animate={{ width: `${(Number(row.exposure) / max) * 100}%` }}
                transition={{ ...spring, delay: i * 0.04 }}
                style={{
                  height: "100%",
                  background: "linear-gradient(90deg, var(--color-info) 0%, rgba(194,164,109,0.5) 100%)",
                }}
              />
            </div>
            <div className="tnum" style={{ textAlign: "right", fontWeight: 500 }}>
              {formatCurrency(row.exposure)}
            </div>
            <div
              className="tnum"
              style={{
                textAlign: "right",
                color: "var(--color-text-subtle)",
                fontFamily: "var(--font-mono)",
                fontSize: 11,
              }}
            >
              {row.count}
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}
