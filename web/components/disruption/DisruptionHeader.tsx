"use client";

import type { Disruption, ImpactReport } from "@/types/schemas";
import { categoryTokens } from "@/lib/design-tokens";
import { eventTime, formatCurrency, formatRelativeTime } from "@/lib/format";
import { useClock } from "@/hooks/useClock";

function severityColor(s: number): string {
  if (s >= 4) return "var(--color-critical)";
  if (s >= 3) return "var(--color-warn)";
  return "var(--color-ok)";
}

function StatCell({
  label,
  value,
  accent,
  upper,
}: Readonly<{ label: string; value: string | number; accent?: string; upper?: boolean }>) {
  return (
    <div style={{ background: "var(--color-surface)", padding: "10px 14px" }}>
      <div
        style={{
          fontSize: 10,
          color: "var(--color-text-subtle)",
          textTransform: "uppercase",
          letterSpacing: "0.06em",
        }}
      >
        {label}
      </div>
      <div
        className="tnum"
        style={{
          marginTop: 4,
          fontSize: 17,
          fontWeight: 600,
          color: accent ?? "var(--color-text)",
          textTransform: upper ? "capitalize" : "none",
          display: "flex",
          alignItems: "center",
          gap: 6,
        }}
      >
        {accent && !upper && (
          <span style={{ width: 7, height: 7, borderRadius: 7, background: accent }} />
        )}
        {value}
      </div>
    </div>
  );
}

type DisruptionHeaderProps = Readonly<{
  disruption: Disruption;
  impact: ImpactReport | null;
}>;

export function DisruptionHeader({ disruption, impact }: DisruptionHeaderProps) {
  useClock();
  const token = categoryTokens[disruption.category];
  const detectedAt = eventTime(disruption.detected_at ?? disruption.first_seen_at);
  const exposure = impact?.total_exposure ?? disruption.total_exposure;
  // Prefer the impact report's actual affected_shipments list. The
  // single-disruption endpoint doesn't populate affected_shipments_count
  // (that only comes through the list JOIN), so relying on the disruption
  // record alone shows "0" on the detail view.
  const shipmentCount = impact?.affected_shipments?.length ?? disruption.affected_shipments_count;
  let statusColor = "var(--color-ok)";
  if (disruption.status === "active") statusColor = "var(--color-critical)";

  return (
    <section
      style={{
        borderBottom: "1px solid var(--color-border)",
        padding: "20px 24px",
        background: "var(--color-bg)",
      }}
    >
      <div style={{ display: "flex", justifyContent: "space-between", gap: 32, alignItems: "flex-start" }}>
        <div style={{ minWidth: 0, flex: 1 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 8, fontSize: 11 }}>
            <span
              style={{
                color: token.color,
                background: token.bg,
                padding: "2px 7px",
                borderRadius: 3,
                fontWeight: 500,
                textTransform: "uppercase",
                letterSpacing: "0.05em",
              }}
            >
              {token.label}
            </span>
            <span style={{ color: "var(--color-text-subtle)", fontFamily: "var(--font-mono)" }}>
              DIS-{disruption.id.replace("dis_", "").toUpperCase()}
            </span>
            <span style={{ color: "var(--color-text-subtle)" }}>·</span>
            <span style={{ color: "var(--color-text-muted)" }}>{disruption.region ?? "Unmapped"}</span>
            <span style={{ color: "var(--color-text-subtle)" }}>·</span>
            <span style={{ color: "var(--color-text-muted)" }}>
              Detected {formatRelativeTime(detectedAt)}
            </span>
          </div>
          <h1
            style={{
              margin: 0,
              fontSize: 22,
              fontWeight: 600,
              lineHeight: "28px",
              letterSpacing: "-0.015em",
              color: "var(--color-text)",
              maxWidth: 780,
            }}
          >
            {disruption.title}
          </h1>
          {disruption.summary && (
            <p
              style={{
                margin: "10px 0 0",
                maxWidth: 780,
                fontSize: 13,
                lineHeight: "20px",
                color: "var(--color-text-muted)",
              }}
            >
              {disruption.summary}
            </p>
          )}
        </div>

        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(2, minmax(100px, 1fr))",
            gap: 1,
            minWidth: 280,
            border: "1px solid var(--color-border)",
            borderRadius: 5,
            overflow: "hidden",
            background: "var(--color-border)",
          }}
        >
          <StatCell label="Severity" value={`${disruption.severity}/5`} accent={severityColor(disruption.severity)} />
          <StatCell label="Exposure" value={formatCurrency(exposure)} />
          <StatCell label="Shipments" value={shipmentCount} />
          <StatCell label="Status" value={disruption.status} accent={statusColor} upper />
        </div>
      </div>
    </section>
  );
}
