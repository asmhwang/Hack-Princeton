"use client";

import { motion } from "motion/react";
import type { Disruption } from "@/types/schemas";
import { categoryTokens } from "@/lib/design-tokens";
import { formatCurrency, formatRelativeTime, eventTime } from "@/lib/format";
import { useClock } from "@/hooks/useClock";

const spring = { type: "spring" as const, stiffness: 260, damping: 26 };

function severityColor(s: number): string {
  if (s >= 4) return "var(--color-critical)";
  if (s >= 3) return "var(--color-warn)";
  return "var(--color-ok)";
}

type DisruptionCardProps = Readonly<{
  disruption: Disruption;
  selected: boolean;
  onSelect: () => void;
  onDelete?: () => void;
}>;

export function DisruptionCard({ disruption, selected, onSelect, onDelete }: DisruptionCardProps) {
  useClock();
  const token = categoryTokens[disruption.category];
  const sev = severityColor(disruption.severity);
  const detectedAt = eventTime(disruption.detected_at ?? disruption.first_seen_at);

  return (
    <button
      type="button"
      onClick={onSelect}
      style={{
        display: "block",
        width: "100%",
        textAlign: "left",
        borderRadius: 5,
        border: `1px solid ${selected ? "var(--color-info)" : "var(--color-border)"}`,
        background: selected ? "rgba(194,164,109,0.06)" : "var(--color-bg)",
        padding: 12,
        cursor: "pointer",
        transition: "all 0.12s ease-out",
        position: "relative",
      }}
      onMouseEnter={(e) => {
        if (!selected) e.currentTarget.style.borderColor = "var(--color-border-strong)";
      }}
      onMouseLeave={(e) => {
        if (!selected) e.currentTarget.style.borderColor = "var(--color-border)";
      }}
    >
      {selected && (
        <motion.span
          layoutId="disruption-selected-indicator"
          style={{
            position: "absolute",
            left: -1,
            top: 10,
            bottom: 10,
            width: 2,
            background: "var(--color-info)",
            borderRadius: 2,
          }}
          transition={spring}
        />
      )}

      {onDelete && (
        <span
          role="button"
          tabIndex={0}
          aria-label="Delete disruption"
          onClick={(e) => {
            e.stopPropagation();
            onDelete();
          }}
          onKeyDown={(e) => {
            if (e.key === "Enter" || e.key === " ") {
              e.preventDefault();
              e.stopPropagation();
              onDelete();
            }
          }}
          className="disruption-card-delete"
          style={{
            position: "absolute",
            top: 6,
            right: 6,
            width: 18,
            height: 18,
            display: "inline-flex",
            alignItems: "center",
            justifyContent: "center",
            borderRadius: 3,
            color: "var(--color-text-subtle)",
            fontSize: 12,
            lineHeight: 1,
            cursor: "pointer",
            opacity: 0.45,
            transition: "opacity 0.12s ease-out, background 0.12s ease-out, color 0.12s ease-out",
          }}
          onMouseEnter={(e) => {
            e.currentTarget.style.background = "var(--color-critical)";
            e.currentTarget.style.color = "var(--color-text)";
            e.currentTarget.style.opacity = "1";
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.background = "transparent";
            e.currentTarget.style.color = "var(--color-text-subtle)";
            e.currentTarget.style.opacity = "0.45";
          }}
        >
          ×
        </span>
      )}

      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 10, gap: 8 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
          <span
            style={{
              fontSize: 10,
              fontWeight: 500,
              color: token.color,
              background: token.bg,
              padding: "2px 6px",
              borderRadius: 3,
              textTransform: "uppercase",
              letterSpacing: "0.04em",
            }}
          >
            {token.label}
          </span>
          <span
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: 4,
              fontSize: 10,
              color: "var(--color-text-subtle)",
              fontFamily: "var(--font-mono)",
            }}
          >
            <span style={{ width: 5, height: 5, borderRadius: 5, background: sev, display: "inline-block" }} />
            S{disruption.severity}
          </span>
        </div>
        <span className="tnum" style={{ fontSize: 10, color: "var(--color-text-subtle)", fontFamily: "var(--font-mono)" }}>
          {formatRelativeTime(detectedAt)}
        </span>
      </div>

      <p
        className="line-clamp-2"
        style={{ margin: 0, fontSize: 13, fontWeight: 500, lineHeight: "18px", color: "var(--color-text)" }}
      >
        {disruption.title}
      </p>

      <div style={{ marginTop: 10, display: "flex", alignItems: "baseline", justifyContent: "space-between", gap: 8 }}>
        <span
          style={{
            fontSize: 11,
            color: "var(--color-text-subtle)",
            overflow: "hidden",
            textOverflow: "ellipsis",
            whiteSpace: "nowrap",
          }}
        >
          {disruption.region ?? "Unmapped region"}
        </span>
        <span className="tnum" style={{ fontSize: 15, fontWeight: 600, color: "var(--color-text)", letterSpacing: "-0.01em" }}>
          {formatCurrency(disruption.total_exposure)}
        </span>
      </div>
    </button>
  );
}
