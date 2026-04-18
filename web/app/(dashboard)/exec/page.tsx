"use client";

import { useDisruptions, useExposureSummary } from "@/hooks/useDisruptions";
import { categoryTokens } from "@/lib/design-tokens";
import { formatCurrency, eventTime, formatRelativeTime } from "@/lib/format";

function KpiCell({ label, value }: Readonly<{ label: string; value: string | number }>) {
  return (
    <div style={{ background: "var(--color-surface)", padding: "12px 16px" }}>
      <div style={{ fontSize: 10, color: "var(--color-text-subtle)", textTransform: "uppercase", letterSpacing: "0.06em" }}>
        {label}
      </div>
      <div className="tnum" style={{ marginTop: 4, fontSize: 18, fontWeight: 600, letterSpacing: "-0.01em" }}>
        {value}
      </div>
    </div>
  );
}

export default function ExecPage() {
  const { data: summary } = useExposureSummary();
  const { data: disruptions = [] } = useDisruptions();

  const active = summary?.active_count ?? disruptions.length;
  const totalExp = summary?.total_exposure ?? "0";
  const top = [...disruptions].sort((a, b) => Number(b.total_exposure) - Number(a.total_exposure)).slice(0, 5);

  let statusLabel = "NOMINAL";
  let statusColor = "var(--color-ok)";
  if (active > 2) { statusLabel = "ESCALATED"; statusColor = "var(--color-critical)"; }
  else if (active > 0) { statusLabel = "MONITORING"; statusColor = "var(--color-warn)"; }

  return (
    <div style={{ padding: 24, maxWidth: 1100 }}>
      <div style={{ marginBottom: 20 }}>
        <div style={{ fontSize: 10, color: "var(--color-text-subtle)", textTransform: "uppercase", letterSpacing: "0.08em", marginBottom: 4 }}>
          Executive summary
        </div>
        <h1 style={{ margin: 0, fontSize: 20, fontWeight: 600, letterSpacing: "-0.01em" }}>
          Supply chain posture — today
        </h1>
      </div>

      {/* Status banner */}
      <div
        style={{
          border: "1px solid var(--color-border)",
          borderRadius: 5,
          padding: "20px 24px",
          marginBottom: 20,
          background: `linear-gradient(135deg, ${statusColor}08 0%, var(--color-surface) 60%)`,
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          gap: 24,
        }}
      >
        <div>
          <div style={{ fontSize: 10, color: "var(--color-text-subtle)", textTransform: "uppercase", letterSpacing: "0.1em" }}>
            Overall status
          </div>
          <div style={{ marginTop: 6, display: "flex", alignItems: "center", gap: 12 }}>
            <span
              style={{
                width: 10,
                height: 10,
                borderRadius: 10,
                background: statusColor,
                boxShadow: `0 0 0 4px ${statusColor}20`,
              }}
            />
            <div style={{ fontSize: 28, fontWeight: 700, letterSpacing: "-0.02em", color: statusColor }}>
              {statusLabel}
            </div>
          </div>
          <p style={{ margin: "8px 0 0", fontSize: 13, color: "var(--color-text-muted)", maxWidth: 460 }}>
            {active} active disruption{active === 1 ? "" : "s"} · no approvals pending beyond 2h threshold.
          </p>
        </div>
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(3, minmax(130px, 1fr))",
            gap: 1,
            background: "var(--color-border)",
            border: "1px solid var(--color-border)",
            borderRadius: 5,
            overflow: "hidden",
          }}
        >
          <KpiCell label="Active" value={active} />
          <KpiCell label="At risk" value={formatCurrency(totalExp)} />
          <KpiCell label="Pending" value="0" />
        </div>
      </div>

      {/* Top disruptions */}
      <section
        style={{
          border: "1px solid var(--color-border)",
          borderRadius: 5,
          background: "var(--color-surface)",
          overflow: "hidden",
        }}
      >
        <div style={{ padding: "12px 16px", borderBottom: "1px solid var(--color-border)" }}>
          <h2 style={{ margin: 0, fontSize: 12, fontWeight: 500, textTransform: "uppercase", letterSpacing: "0.08em" }}>
            Top active disruptions
          </h2>
        </div>
        {top.length === 0 ? (
          <div style={{ padding: "16px", fontSize: 13, color: "var(--color-text-muted)" }}>
            No active disruptions from the API.
          </div>
        ) : (
          <div>
            {top.map((d, i) => {
              const token = categoryTokens[d.category];
              return (
                <div
                  key={d.id}
                  style={{
                    display: "grid",
                    gridTemplateColumns: "14px 1fr 140px 120px 100px",
                    gap: 16,
                    padding: "14px 16px",
                    alignItems: "center",
                    borderTop: i === 0 ? "none" : "1px solid var(--color-border)",
                    fontSize: 13,
                  }}
                >
                  <span
                    style={{
                      width: 8,
                      height: 8,
                      borderRadius: 8,
                      background: token.color,
                      display: "inline-block",
                      flexShrink: 0,
                    }}
                  />
                  <div>
                    <div style={{ fontWeight: 500 }}>{d.title}</div>
                    <div style={{ marginTop: 2, fontSize: 11, color: "var(--color-text-subtle)" }}>
                      {token.label} · {d.region}
                    </div>
                  </div>
                  <div className="tnum" style={{ textAlign: "right", fontWeight: 600 }}>
                    {formatCurrency(d.total_exposure)}
                  </div>
                  <div className="tnum" style={{ textAlign: "right", color: "var(--color-text-muted)", fontSize: 12 }}>
                    {d.affected_shipments_count} shipments
                  </div>
                  <div
                    className="tnum"
                    style={{
                      textAlign: "right",
                      color: "var(--color-text-subtle)",
                      fontSize: 11,
                      fontFamily: "var(--font-mono)",
                    }}
                  >
                    {formatRelativeTime(eventTime(d.detected_at ?? d.first_seen_at))}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </section>
    </div>
  );
}
