"use client";

import { useState, useMemo } from "react";
import type { AffectedShipment } from "@/types/schemas";
import { formatCurrency } from "@/lib/format";

type SortKey = "shipment_id" | "sku" | "customer_name" | "exposure" | "days_to_sla_breach";
type SortDir = "asc" | "desc";

function SortHeader({
  col,
  label,
  align = "left",
  sortBy,
  dir,
  onSort,
}: Readonly<{
  col: SortKey;
  label: string;
  align?: "left" | "right";
  sortBy: SortKey;
  dir: SortDir;
  onSort: (col: SortKey) => void;
}>) {
  const active = sortBy === col;
  return (
    <th
      onClick={() => onSort(col)}
      style={{
        padding: "8px 12px",
        textAlign: align,
        fontSize: 10,
        fontWeight: 500,
        color: active ? "var(--color-text)" : "var(--color-text-subtle)",
        textTransform: "uppercase",
        letterSpacing: "0.06em",
        borderBottom: "1px solid var(--color-border)",
        cursor: "pointer",
        userSelect: "none",
        background: "var(--color-surface)",
        position: "sticky",
        top: 0,
        whiteSpace: "nowrap",
      }}
    >
      {label}
      {active && <span style={{ marginLeft: 4, fontSize: 9 }}>{dir === "asc" ? "▲" : "▼"}</span>}
    </th>
  );
}

type AffectedShipmentsTableProps = Readonly<{ shipments: AffectedShipment[] }>;

export function AffectedShipmentsTable({ shipments }: AffectedShipmentsTableProps) {
  const [sortBy, setSortBy] = useState<SortKey>("exposure");
  const [dir, setDir] = useState<SortDir>("desc");
  const [q, setQ] = useState("");

  const sorted = useMemo(() => {
    const filtered = q
      ? shipments.filter((s) => {
          const needle = q.toLowerCase();
          return (
            s.shipment_id.toLowerCase().includes(needle) ||
            (s.customer_name ?? "").toLowerCase().includes(needle) ||
            (s.sku ?? "").toLowerCase().includes(needle)
          );
        })
      : shipments;
    return [...filtered].sort((a, b) => {
      const av = a[sortBy] ?? "";
      const bv = b[sortBy] ?? "";
      const cmp =
        typeof av === "number" && typeof bv === "number"
          ? av - bv
          : String(av).localeCompare(String(bv));
      return dir === "asc" ? cmp : -cmp;
    });
  }, [shipments, sortBy, dir, q]);

  const toggleSort = (col: SortKey) => {
    if (sortBy === col) setDir(dir === "asc" ? "desc" : "asc");
    else { setSortBy(col); setDir("desc"); }
  };

  function exportCsv() {
    const header = ["Shipment", "SKU", "Customer", "Origin", "Destination", "Exposure", "SLA (days)", "Status"];
    const rows = sorted.map((s) => [
      s.shipment_id, s.sku, s.customer_name, s.origin, s.destination,
      s.exposure, s.days_to_sla_breach ?? "", s.status,
    ]);
    const csv = [header, ...rows].map((r) => r.join(",")).join("\n");
    const url = URL.createObjectURL(new Blob([csv], { type: "text/csv" }));
    const a = document.createElement("a");
    a.href = url; a.download = "shipments.csv"; a.click();
    URL.revokeObjectURL(url);
  }

  if (shipments.length === 0) {
    return (
      <div
        style={{
          borderRadius: 5,
          border: "1px dashed var(--color-border-strong)",
          padding: 16,
        }}
      >
        <p style={{ margin: 0, fontSize: 13, fontWeight: 500 }}>No affected shipments yet</p>
        <p style={{ margin: "8px 0 0", fontSize: 13, lineHeight: "20px", color: "var(--color-text-muted)" }}>
          Analyst output will populate this table after an impact report is generated.
        </p>
      </div>
    );
  }

  const sharedThStyle = {
    padding: "8px 12px",
    textAlign: "left" as const,
    fontSize: 10,
    fontWeight: 500,
    color: "var(--color-text-subtle)",
    textTransform: "uppercase" as const,
    letterSpacing: "0.06em",
    borderBottom: "1px solid var(--color-border)",
    background: "var(--color-surface)",
    position: "sticky" as const,
    top: 0,
  };

  return (
    <div
      style={{
        borderRadius: 5,
        border: "1px solid var(--color-border)",
        overflow: "hidden",
        background: "var(--color-bg)",
      }}
    >
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          gap: 8,
          padding: "10px 12px",
          borderBottom: "1px solid var(--color-border)",
          background: "var(--color-surface)",
          flexWrap: "wrap",
        }}
      >
        <span
          className="tnum"
          style={{
            fontSize: 11,
            color: "var(--color-text-subtle)",
            fontFamily: "var(--font-mono)",
            whiteSpace: "nowrap",
          }}
        >
          {sorted.length} of {shipments.length}
        </span>
        <div style={{ display: "flex", gap: 8, flex: 1, justifyContent: "flex-end", minWidth: 0 }}>
          <input
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="Filter…"
            style={{
              height: 26,
              padding: "0 8px",
              border: "1px solid var(--color-border)",
              background: "var(--color-bg)",
              color: "var(--color-text)",
              fontSize: 12,
              borderRadius: 3,
              width: 120,
              minWidth: 0,
              outline: "none",
              fontFamily: "var(--font-mono)",
            }}
          />
          <button
            type="button"
            onClick={exportCsv}
            style={{
              height: 26,
              padding: "0 10px",
              borderRadius: 3,
              border: "1px solid var(--color-border)",
              background: "transparent",
              color: "var(--color-text-muted)",
              fontSize: 11,
              cursor: "pointer",
              whiteSpace: "nowrap",
            }}
          >
            CSV
          </button>
        </div>
      </div>

      <div style={{ overflow: "auto", maxHeight: 360 }}>
        <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12, tableLayout: "fixed" }}>
          <thead>
            <tr>
              <SortHeader col="shipment_id" label="Shipment" sortBy={sortBy} dir={dir} onSort={toggleSort} />
              <SortHeader col="sku" label="SKU" sortBy={sortBy} dir={dir} onSort={toggleSort} />
              <SortHeader col="customer_name" label="Customer" sortBy={sortBy} dir={dir} onSort={toggleSort} />
              <th style={sharedThStyle}>Route</th>
              <SortHeader col="exposure" label="Exposure" align="right" sortBy={sortBy} dir={dir} onSort={toggleSort} />
              <SortHeader col="days_to_sla_breach" label="SLA" align="right" sortBy={sortBy} dir={dir} onSort={toggleSort} />
              <th style={sharedThStyle}>Status</th>
            </tr>
          </thead>
          <tbody>
            {sorted.map((s, idx) => {
              const urgent =
                s.days_to_sla_breach !== null && s.days_to_sla_breach !== undefined && s.days_to_sla_breach < 2;
              return (
                <tr
                  key={s.shipment_id}
                  className="ship-row"
                  style={{
                    borderBottom: idx === sorted.length - 1 ? "none" : "1px solid var(--color-border)",
                  }}
                >
                  <td
                    style={{
                      padding: "9px 12px",
                      fontFamily: "var(--font-mono)",
                      fontSize: 11,
                      color: "var(--color-text)",
                      whiteSpace: "nowrap",
                    }}
                  >
                    {s.shipment_id}
                  </td>
                  <td
                    title={s.sku ?? undefined}
                    style={{
                      padding: "9px 12px",
                      fontFamily: "var(--font-mono)",
                      fontSize: 11,
                      color: "var(--color-text-muted)",
                      whiteSpace: "nowrap",
                      overflow: "hidden",
                      textOverflow: "ellipsis",
                      maxWidth: 120,
                    }}
                  >
                    {s.sku}
                  </td>
                  <td
                    title={s.customer_name ?? undefined}
                    style={{
                      padding: "9px 12px",
                      whiteSpace: "nowrap",
                      overflow: "hidden",
                      textOverflow: "ellipsis",
                      maxWidth: 140,
                    }}
                  >
                    {s.customer_name}
                  </td>
                  <td
                    title={`${s.origin} → ${s.destination}`}
                    style={{
                      padding: "9px 12px",
                      color: "var(--color-text-muted)",
                      fontFamily: "var(--font-mono)",
                      fontSize: 11,
                      whiteSpace: "nowrap",
                      overflow: "hidden",
                      textOverflow: "ellipsis",
                      maxWidth: 180,
                    }}
                  >
                    {s.origin} → {s.destination}
                  </td>
                  <td className="tnum" style={{ padding: "9px 12px", textAlign: "right", fontWeight: 500 }}>
                    {formatCurrency(s.exposure)}
                  </td>
                  <td className="tnum" style={{ padding: "9px 12px", textAlign: "right" }}>
                    <span
                      style={{
                        display: "inline-flex",
                        alignItems: "center",
                        gap: 4,
                        color: urgent ? "var(--color-critical)" : "var(--color-text-muted)",
                        fontWeight: urgent ? 600 : 400,
                      }}
                    >
                      {urgent && <span style={{ fontSize: 10 }}>●</span>}
                      {s.days_to_sla_breach !== null && s.days_to_sla_breach !== undefined
                        ? `${s.days_to_sla_breach}d`
                        : "—"}
                    </span>
                  </td>
                  <td style={{ padding: "9px 12px" }}>
                    <span
                      style={{
                        fontSize: 10,
                        padding: "2px 6px",
                        borderRadius: 3,
                        border: "1px solid var(--color-border)",
                        color: "var(--color-text-muted)",
                        textTransform: "uppercase",
                        letterSpacing: "0.04em",
                        fontFamily: "var(--font-mono)",
                      }}
                    >
                      {(s.status ?? "unknown").replace(/_/g, " ")}
                    </span>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
