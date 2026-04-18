"use client";

import { motion } from "motion/react";
import type { MitigationOption } from "@/types/schemas";
import { formatCurrency, formatPercent } from "@/lib/format";

const spring = { type: "spring" as const, stiffness: 260, damping: 26 };

function confidenceColor(c: number): string {
  if (c >= 0.8) return "var(--color-ok)";
  if (c >= 0.6) return "var(--color-info)";
  return "var(--color-warn)";
}

function Metric({
  label, value, sign, signColor, valueColor, bar, barColor,
}: Readonly<{
  label: string; value: string; sign?: string; signColor?: string;
  valueColor?: string; bar?: number; barColor?: string;
}>) {
  return (
    <div>
      <dt style={{ fontSize: 10, color: "var(--color-text-subtle)", textTransform: "uppercase", letterSpacing: "0.06em", fontWeight: 500 }}>
        {label}
      </dt>
      <dd className="tnum" style={{ margin: "4px 0 0", fontSize: 15, fontWeight: 600, color: valueColor ?? "var(--color-text)", letterSpacing: "-0.01em" }}>
        {sign && <span style={{ color: signColor ?? "inherit", marginRight: 1 }}>{sign}</span>}
        {value}
      </dd>
      {bar !== undefined && (
        <div style={{ marginTop: 6, height: 2, background: "var(--color-border)", borderRadius: 1, overflow: "hidden" }}>
          <div style={{ width: `${bar * 100}%`, height: "100%", background: barColor }} />
        </div>
      )}
    </div>
  );
}

type MitigationCardProps = Readonly<{
  option: MitigationOption;
  index: number;
  approved: boolean;
  onApprove: () => void;
  onExplain: () => void;
}>;

export function MitigationCard({ option, index, approved, onApprove, onExplain }: MitigationCardProps) {
  const cost = option.incremental_cost ?? option.delta_cost ?? "0";
  const days = option.days_saved ?? option.delta_days ?? 0;
  const confColor = confidenceColor(option.confidence);
  const isTop = index === 0;

  return (
    <motion.article
      layout
      style={{
        borderRadius: 5,
        border: isTop ? "1px solid rgba(194,164,109,0.3)" : "1px solid var(--color-border)",
        background: isTop
          ? "linear-gradient(180deg, rgba(194,164,109,0.03) 0%, var(--color-bg) 60%)"
          : "var(--color-bg)",
        padding: 16,
        position: "relative",
      }}
    >
      {isTop && (
        <div style={{
          position: "absolute", top: -1, left: 12,
          fontSize: 9, fontWeight: 500,
          background: "var(--color-info)", color: "#0f0f0f",
          padding: "2px 6px", borderRadius: "0 0 3px 3px",
          textTransform: "uppercase", letterSpacing: "0.05em",
          fontFamily: "var(--font-mono)",
        }}>
          Recommended
        </div>
      )}

      <div style={{ display: "flex", justifyContent: "space-between", gap: 12, alignItems: "flex-start" }}>
        <div style={{ minWidth: 0, flex: 1 }}>
          <div style={{ marginBottom: 6 }}>
            <span style={{
              fontSize: 10, fontFamily: "var(--font-mono)",
              color: "var(--color-text-subtle)", textTransform: "uppercase", letterSpacing: "0.05em",
            }}>
              {option.option_type.replaceAll("_", "·")}
            </span>
          </div>
          <p style={{ margin: 0, fontSize: 14, fontWeight: 600, lineHeight: "20px", letterSpacing: "-0.005em" }}>
            {option.title ?? option.option_type.replaceAll("_", " ")}
          </p>
          <p style={{ margin: "6px 0 0", fontSize: 12, lineHeight: "18px", color: "var(--color-text-muted)" }}>
            {option.description}
          </p>
        </div>
      </div>

      <dl style={{
        margin: "14px 0 0",
        display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 8,
        padding: "10px 0",
        borderTop: "1px solid var(--color-border)",
        borderBottom: "1px solid var(--color-border)",
      }}>
        <Metric
          label="Δ Cost"
          value={formatCurrency(cost)}
          sign={Number(cost) > 0 ? "+" : undefined}
          signColor={Number(cost) > 0 ? "var(--color-warn)" : "var(--color-ok)"}
        />
        <Metric
          label="Δ Days"
          value={days >= 0 ? `-${days}` : `+${-days}`}
          valueColor={days > 0 ? "var(--color-ok)" : "var(--color-warn)"}
        />
        <Metric
          label="Confidence"
          value={formatPercent(option.confidence)}
          valueColor={confColor}
          bar={option.confidence}
          barColor={confColor}
        />
      </dl>

      <div style={{ marginTop: 12, display: "flex", alignItems: "center", justifyContent: "space-between", gap: 10 }}>
        <button
          type="button"
          onClick={onExplain}
          style={{
            background: "none", border: "none", padding: 0,
            fontSize: 12, color: "var(--color-text-muted)",
            display: "inline-flex", alignItems: "center", gap: 4, cursor: "pointer",
          }}
          onMouseEnter={(e) => { e.currentTarget.style.color = "var(--color-text)"; e.currentTarget.style.textDecoration = "underline"; }}
          onMouseLeave={(e) => { e.currentTarget.style.color = "var(--color-text-muted)"; e.currentTarget.style.textDecoration = "none"; }}
        >
          <span style={{ color: "var(--color-text-subtle)" }}>▸</span> Why this recommendation?
        </button>
        <motion.button
          type="button"
          layoutId={`mitigation-approve-${option.id}`}
          onClick={onApprove}
          disabled={approved}
          transition={spring}
          style={{
            height: 30, padding: "0 12px", borderRadius: 4,
            border: approved ? "1px solid rgba(70,167,88,0.4)" : "1px solid var(--color-info)",
            background: approved ? "rgba(70,167,88,0.08)" : "rgba(194,164,109,0.1)",
            color: approved ? "var(--color-ok)" : "var(--color-info)",
            fontSize: 12, fontWeight: 500,
            display: "inline-flex", alignItems: "center", gap: 6,
            cursor: approved ? "default" : "pointer",
          }}
        >
          {approved ? (
            <>
              <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
                <path d="M2 6L5 9L10 3" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
              Approved
            </>
          ) : (
            <>Approve &amp; prepare</>
          )}
        </motion.button>
      </div>
    </motion.article>
  );
}
