"use client";

import { motion, AnimatePresence } from "motion/react";
import type { ImpactReport, MitigationOption } from "@/types/schemas";
import { SqlPreview } from "@/components/ui/SqlPreview";

const spring = { type: "spring" as const, stiffness: 260, damping: 26 };
const easeOut = { duration: 0.2, ease: "easeOut" as const };

function Section({ title, meta, children }: Readonly<{ title: string; meta?: string; children: React.ReactNode }>) {
  return (
    <section style={{ marginBottom: 22 }}>
      <div style={{ display: "flex", alignItems: "baseline", justifyContent: "space-between", marginBottom: 10 }}>
        <h3 style={{
          margin: 0, fontSize: 11, fontWeight: 500, textTransform: "uppercase",
          letterSpacing: "0.08em", color: "var(--color-text)",
        }}>
          {title}
        </h3>
        {meta && (
          <span style={{ fontSize: 10, color: "var(--color-text-subtle)", fontFamily: "var(--font-mono)" }}>
            {meta}
          </span>
        )}
      </div>
      {children}
    </section>
  );
}

function CounterfactualCell({ label, value, color }: Readonly<{ label: string; value: string; color: string }>) {
  return (
    <div style={{ padding: "8px 10px", border: "1px solid var(--color-border)", borderRadius: 4, background: "var(--color-bg)" }}>
      <div style={{ fontSize: 10, color: "var(--color-text-subtle)", textTransform: "uppercase", letterSpacing: "0.06em" }}>
        {label}
      </div>
      <div className="tnum" style={{ marginTop: 3, fontSize: 13, fontWeight: 600, color }}>{value}</div>
    </div>
  );
}

const TRIGGER_SIGNALS = [
  { label: "JMA · typhoon bulletin", color: "var(--color-cat-weather)" },
  { label: "ProteusAIS · vessel divergence", color: "var(--color-cat-logistics)" },
  { label: "HK Marine · T8 signal", color: "var(--color-cat-news)" },
  { label: "ECMWF · cone forecast", color: "var(--color-cat-weather)" },
];

type ExplainabilityDrawerProps = Readonly<{
  open: boolean;
  option: MitigationOption | null;
  impact: ImpactReport | null;
  onClose: () => void;
}>;

export function ExplainabilityDrawer({ open, option, impact, onClose }: ExplainabilityDrawerProps) {
  const sql = impact?.sql_executed ?? impact?.generated_sql;
  const reasoningTrace = impact?.reasoning_trace;

  type Step = { label: string; value: string };
  type ToolCall = {
    tool_name?: string;
    row_count?: number;
    args?: Record<string, unknown>;
    synthesized_sql?: string;
  };

  const summarizeArgs = (args: Record<string, unknown> | undefined): string => {
    if (!args) return "";
    const parts: string[] = [];
    for (const [k, v] of Object.entries(args)) {
      if (typeof v === "number") parts.push(`${k}=${v}`);
      else if (typeof v === "string") parts.push(`${k}="${v.length > 40 ? v.slice(0, 37) + "..." : v}"`);
      else if (Array.isArray(v)) parts.push(`${k}=[${v.length} items]`);
    }
    return parts.join(", ");
  };

  const buildSteps = (): Step[] => {
    if (!reasoningTrace || typeof reasoningTrace !== "object") return [];
    if (Array.isArray((reasoningTrace as { steps?: unknown }).steps)) {
      return (reasoningTrace as { steps: Step[] }).steps;
    }
    const out: Step[] = [];
    const trace = reasoningTrace as Record<string, unknown>;

    // tool_calls: explode each into its own readable step.
    const calls = trace.tool_calls;
    if (Array.isArray(calls)) {
      for (const raw of calls) {
        const call = raw as ToolCall;
        const name = call.tool_name ?? "tool";
        const rows = typeof call.row_count === "number" ? ` · ${call.row_count} rows` : "";
        const argSummary = summarizeArgs(call.args);
        out.push({
          label: `${name}${rows}`,
          value: argSummary || "(no args)",
        });
      }
    }

    // Other keys: render scalars/strings inline; skip the raw tool_calls dump.
    for (const [k, v] of Object.entries(trace)) {
      if (k === "tool_calls") continue;
      if (v == null) continue;
      if (typeof v === "string" || typeof v === "number" || typeof v === "boolean") {
        out.push({ label: k.replace(/_/g, " "), value: String(v) });
      }
    }
    return out;
  };

  const steps = buildSteps();

  return (
    <AnimatePresence>
      {open && option && (
        <>
          <motion.div
            key="drawer-scrim"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={easeOut}
            onClick={onClose}
            style={{ position: "fixed", inset: 0, zIndex: 40, background: "rgba(0,0,0,0.4)" }}
          />
          <motion.aside
            key="drawer"
            initial={{ x: "100%" }}
            animate={{ x: 0 }}
            exit={{ x: "100%" }}
            transition={spring}
            style={{
              position: "fixed", top: 0, right: 0, bottom: 0, zIndex: 45,
              width: "100%", maxWidth: 580,
              background: "var(--color-surface)",
              borderLeft: "1px solid var(--color-border-strong)",
              display: "flex", flexDirection: "column",
              boxShadow: "-20px 0 60px rgba(0,0,0,0.4)",
            }}
          >
            {/* Header */}
            <div style={{
              height: 52, minHeight: 52,
              display: "flex", alignItems: "center", justifyContent: "space-between",
              borderBottom: "1px solid var(--color-border)", padding: "0 18px",
            }}>
              <div>
                <div style={{ fontSize: 10, color: "var(--color-text-subtle)", textTransform: "uppercase", letterSpacing: "0.08em" }}>
                  Evidence · {option.id.slice(0, 8)}
                </div>
                <h2 style={{ margin: "2px 0 0", fontSize: 14, fontWeight: 600 }}>
                  {option.title ?? option.option_type.replace(/_/g, " ")}
                </h2>
              </div>
              <button
                type="button"
                onClick={onClose}
                style={{
                  width: 28, height: 28, borderRadius: 4,
                  border: "1px solid var(--color-border)",
                  background: "transparent", color: "var(--color-text-muted)",
                  display: "flex", alignItems: "center", justifyContent: "center",
                  cursor: "pointer", fontSize: 13,
                }}
              >
                ✕
              </button>
            </div>

            {/* Content */}
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ duration: 0.2, delay: 0.06 }}
              style={{ flex: 1, overflow: "auto", padding: 20 }}
            >
              <Section title="Trigger signals">
                <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
                  {TRIGGER_SIGNALS.map((sig) => (
                    <span
                      key={sig.label}
                      style={{
                        display: "inline-flex", alignItems: "center", gap: 5,
                        fontSize: 11, padding: "3px 8px", borderRadius: 3,
                        border: "1px solid var(--color-border)",
                        fontFamily: "var(--font-mono)", color: "var(--color-text-muted)",
                      }}
                    >
                      <span style={{ width: 5, height: 5, borderRadius: 5, background: sig.color }} />
                      {sig.label}
                    </span>
                  ))}
                </div>
              </Section>

              <Section title="Rationale">
                <p style={{ margin: 0, fontSize: 13, lineHeight: "20px", color: "var(--color-text-muted)" }}>
                  {option.rationale ?? option.description}
                </p>
              </Section>

              {sql && (
                <Section title="Impact query" meta="Analyst · SQL">
                  <SqlPreview sql={sql} />
                </Section>
              )}

              {steps.length > 0 && (
                <Section title="Reasoning trace" meta={`Strategist · ${steps.length} steps`}>
                  <ol style={{ margin: 0, padding: 0, listStyle: "none", display: "flex", flexDirection: "column", gap: 10 }}>
                    {steps.map((step, i) => (
                      <li
                        key={step.label}
                        style={{
                          display: "grid", gridTemplateColumns: "28px 1fr",
                          padding: "10px 12px",
                          border: "1px solid var(--color-border)", borderRadius: 4,
                          background: "var(--color-bg)",
                        }}
                      >
                        <div style={{ fontFamily: "var(--font-mono)", fontSize: 11, color: "var(--color-info)", fontWeight: 500 }}>
                          {String(i + 1).padStart(2, "0")}
                        </div>
                        <div>
                          <div style={{ fontSize: 12, fontWeight: 500, color: "var(--color-text)", marginBottom: 3 }}>
                            {step.label}
                          </div>
                          <pre
                            style={{
                              margin: 0,
                              fontSize: 12,
                              lineHeight: "18px",
                              color: "var(--color-text-muted)",
                              fontFamily: step.value.startsWith("{") || step.value.startsWith("[")
                                ? "var(--font-mono)"
                                : "inherit",
                              whiteSpace: "pre-wrap",
                              wordBreak: "break-word",
                            }}
                          >
                            {step.value}
                          </pre>
                        </div>
                      </li>
                    ))}
                  </ol>
                </Section>
              )}

              <Section title="Counterfactuals" meta="If this option is not taken">
                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8 }}>
                  <CounterfactualCell label="Expected exposure" value="+$843K" color="var(--color-critical)" />
                  <CounterfactualCell label="SLA breaches" value="6 / 14" color="var(--color-warn)" />
                  <CounterfactualCell label="Customer calls" value="~3 escalations" color="var(--color-text-muted)" />
                  <CounterfactualCell label="Recovery window" value="9 → 14 days" color="var(--color-text-muted)" />
                </div>
              </Section>
            </motion.div>
          </motion.aside>
        </>
      )}
    </AnimatePresence>
  );
}
