"use client";

import { useState } from "react";
import { ExposureBars } from "@/components/charts/ExposureBars";
import { useAnalytics } from "@/hooks/useDisruptions";

const RANGES = ["24h", "7d", "30d", "QTD"] as const;

function toCsv(rows: { label: string; exposure: string; count?: number }[]) {
  return ["label,exposure,count", ...rows.map((r) => `${r.label},${r.exposure},${r.count ?? 0}`)].join("\n");
}

export default function AnalyticsPage() {
  const [range, setRange] = useState("7d");
  const { data } = useAnalytics();
  const analytics = data ?? { by_customer: [], by_sku: [], by_quarter: [] };

  function exportCsv() {
    const rows = [...analytics.by_customer, ...analytics.by_sku, ...analytics.by_quarter];
    const blob = new Blob([toCsv(rows)], { type: "text/csv;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url; a.download = "suppl-ai-exposure.csv"; a.click();
    URL.revokeObjectURL(url);
  }

  return (
    <div style={{ padding: 24, maxWidth: 1200 }}>
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          borderBottom: "1px solid var(--color-border)",
          paddingBottom: 16,
          marginBottom: 20,
        }}
      >
        <div>
          <div style={{ fontSize: 10, color: "var(--color-text-subtle)", textTransform: "uppercase", letterSpacing: "0.08em", marginBottom: 4 }}>
            Analytics
          </div>
          <h1 style={{ margin: 0, fontSize: 20, fontWeight: 600, letterSpacing: "-0.01em" }}>
            Exposure attribution
          </h1>
        </div>
        <div style={{ display: "flex", gap: 8 }}>
          {/* Range tabs */}
          <div
            style={{
              display: "flex",
              border: "1px solid var(--color-border)",
              borderRadius: 4,
              overflow: "hidden",
            }}
          >
            {RANGES.map((r) => (
              <button
                key={r}
                type="button"
                onClick={() => setRange(r)}
                style={{
                  height: 30,
                  padding: "0 10px",
                  border: "none",
                  background: range === r ? "var(--color-surface-raised)" : "transparent",
                  color: range === r ? "var(--color-text)" : "var(--color-text-muted)",
                  fontSize: 11,
                  fontFamily: "var(--font-mono)",
                  cursor: "pointer",
                }}
              >
                {r}
              </button>
            ))}
          </div>
          <button
            type="button"
            onClick={exportCsv}
            style={{
              height: 30,
              padding: "0 12px",
              borderRadius: 4,
              border: "1px solid var(--color-border-strong)",
              background: "var(--color-surface-raised)",
              color: "var(--color-text)",
              fontSize: 12,
              cursor: "pointer",
            }}
          >
            Export CSV
          </button>
        </div>
      </div>

      <div style={{ display: "grid", gap: 20 }}>
        <ExposureBars title="By customer" data={analytics.by_customer} />
        <ExposureBars title="By SKU" data={analytics.by_sku} />
        <ExposureBars title="By quarter" data={analytics.by_quarter} />
      </div>
    </div>
  );
}
