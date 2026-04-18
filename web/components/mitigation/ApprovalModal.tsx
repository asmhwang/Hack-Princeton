"use client";

import { motion, AnimatePresence } from "motion/react";
import type { MitigationOption } from "@/types/schemas";
import { formatCurrency, formatPercent } from "@/lib/format";

const spring = { type: "spring" as const, stiffness: 260, damping: 26 };
const easeOut = { duration: 0.2, ease: "easeOut" as const };

function KvCell({ label, value }: Readonly<{ label: string; value: string }>) {
  return (
    <div style={{ background: "var(--color-surface)", padding: "12px 16px" }}>
      <div style={{ fontSize: 10, color: "var(--color-text-subtle)", textTransform: "uppercase", letterSpacing: "0.06em" }}>
        {label}
      </div>
      <div className="tnum" style={{ marginTop: 4, fontSize: 15, fontWeight: 600, letterSpacing: "-0.01em" }}>
        {value}
      </div>
    </div>
  );
}

function DraftRow({ label, meta }: Readonly<{ label: string; meta: string }>) {
  return (
    <div style={{
      display: "flex", alignItems: "center", gap: 10,
      padding: "8px 10px", borderRadius: 4,
      border: "1px solid var(--color-border)",
      background: "var(--color-bg)",
    }}>
      <div style={{
        width: 22, height: 22, borderRadius: 3,
        display: "flex", alignItems: "center", justifyContent: "center",
        background: "var(--color-surface-raised)",
        fontSize: 11, color: "var(--color-text-muted)", flexShrink: 0,
      }}>
        ✉
      </div>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ fontSize: 12, color: "var(--color-text)" }}>{label}</div>
        <div style={{ fontSize: 10, color: "var(--color-text-subtle)", fontFamily: "var(--font-mono)" }}>{meta}</div>
      </div>
      <span style={{ fontSize: 11, color: "var(--color-text-muted)" }}>Draft</span>
    </div>
  );
}

type ApprovalModalProps = Readonly<{
  option: MitigationOption | null;
  open: boolean;
  pending: boolean;
  onClose: () => void;
  onConfirm: () => void;
}>;

export function ApprovalModal({ option, open, pending, onClose, onConfirm }: ApprovalModalProps) {
  const cost = option ? (option.incremental_cost ?? option.delta_cost ?? "0") : "0";
  const days = option ? (option.days_saved ?? option.delta_days ?? 0) : 0;

  return (
    <AnimatePresence>
      {open && option && (
        <motion.div
          key="backdrop"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={easeOut}
          onClick={() => { if (!pending) onClose(); }}
          style={{
            position: "fixed", inset: 0, zIndex: 50,
            background: "rgba(0,0,0,0.6)",
            backdropFilter: "blur(2px)",
            display: "flex", alignItems: "center", justifyContent: "center", padding: 20,
          }}
        >
          <motion.div
            key="panel"
            initial={{ opacity: 0, scale: 0.96, y: 6 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.96, y: 6 }}
            transition={spring}
            onClick={(e) => e.stopPropagation()}
            style={{
              width: "100%", maxWidth: 520,
              background: "var(--color-surface)",
              border: "1px solid var(--color-border-strong)",
              borderRadius: 6, overflow: "hidden",
              boxShadow: "0 20px 60px rgba(0,0,0,0.6)",
            }}
          >
            {/* Header */}
            <div style={{ padding: "18px 20px", borderBottom: "1px solid var(--color-border)" }}>
              <div style={{
                display: "inline-block",
                fontSize: 10, fontFamily: "var(--font-mono)",
                color: "var(--color-info)", background: "rgba(194,164,109,0.1)",
                padding: "2px 6px", borderRadius: 3,
                textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: 10,
              }}>
                {option.option_type.replace(/_/g, " ")}
              </div>
              <h2 style={{ margin: 0, fontSize: 17, fontWeight: 600, letterSpacing: "-0.01em" }}>
                {option.title ?? option.option_type.replace(/_/g, " ")}
              </h2>
              <p style={{ margin: "8px 0 0", fontSize: 13, lineHeight: "20px", color: "var(--color-text-muted)" }}>
                This records approval, flips eligible shipments to rerouting, and saves draft communications.{" "}
                <strong style={{ color: "var(--color-text)", fontWeight: 500 }}>No emails are sent.</strong>
              </p>
            </div>

            {/* KV grid */}
            <div style={{
              display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 1,
              background: "var(--color-border)",
              borderBottom: "1px solid var(--color-border)",
            }}>
              <KvCell label="Incremental cost" value={formatCurrency(cost)} />
              <KvCell label="Days recovered" value={days >= 0 ? `${days}d` : `+${-days}d`} />
              <KvCell label="Confidence" value={formatPercent(option.confidence)} />
            </div>

            {/* Prepared drafts */}
            <div style={{ padding: "16px 20px", borderBottom: "1px solid var(--color-border)" }}>
              <h3 style={{
                margin: 0, fontSize: 11, fontWeight: 500, textTransform: "uppercase",
                letterSpacing: "0.08em", color: "var(--color-text-subtle)",
              }}>
                Prepared drafts{" "}
                <span style={{ color: "var(--color-text-subtle)", textTransform: "none", letterSpacing: 0 }}>
                  — never sent
                </span>
              </h3>
              <div style={{ marginTop: 10, display: "flex", flexDirection: "column", gap: 6 }}>
                <DraftRow label="Supplier notification" meta="Carrier ops · Draft" />
                <DraftRow label="Customer update" meta="Affected recipients · Draft" />
                <DraftRow label="Internal escalation" meta="#ops-critical · Draft" />
              </div>
            </div>

            {/* DB changes */}
            <div style={{ padding: "14px 20px", borderBottom: "1px solid var(--color-border)" }}>
              <h3 style={{
                margin: 0, fontSize: 11, fontWeight: 500, textTransform: "uppercase",
                letterSpacing: "0.08em", color: "var(--color-text-subtle)",
              }}>
                Database changes
              </h3>
              <ul style={{ margin: "10px 0 0", padding: 0, listStyle: "none", fontSize: 12, lineHeight: "20px", color: "var(--color-text-muted)", display: "flex", flexDirection: "column", gap: 3 }}>
                <li>
                  <span style={{ fontFamily: "var(--font-mono)", color: "var(--color-info)" }}>UPDATE</span>
                  {" "}affected shipments →{" "}
                  <span style={{ color: "var(--color-warn)", fontFamily: "var(--font-mono)" }}>rerouting</span>
                </li>
                <li>
                  <span style={{ fontFamily: "var(--font-mono)", color: "var(--color-info)" }}>INSERT</span>
                  {" "}approval entry{" "}
                  <span style={{ fontFamily: "var(--font-mono)", color: "var(--color-text-subtle)" }}>(ts: now)</span>
                </li>
                <li>
                  <span style={{ fontFamily: "var(--font-mono)", color: "var(--color-info)" }}>INSERT</span>
                  {" "}3 draft_communications
                </li>
              </ul>
            </div>

            {/* Actions */}
            <div style={{ display: "flex", justifyContent: "flex-end", gap: 8, padding: "14px 20px" }}>
              <button
                type="button"
                onClick={onClose}
                disabled={pending}
                style={{
                  height: 32, padding: "0 14px", borderRadius: 4,
                  border: "1px solid var(--color-border-strong)",
                  background: "transparent", color: "var(--color-text)",
                  fontSize: 12, fontWeight: 500, cursor: "pointer",
                }}
              >
                Cancel
              </button>
              <motion.button
                type="button"
                layoutId={`act-approval-morph-${option.id}`}
                transition={spring}
                onClick={onConfirm}
                disabled={pending}
                style={{
                  height: 32, padding: "0 14px", borderRadius: 4,
                  border: "1px solid var(--color-info)",
                  background: pending ? "var(--color-surface-raised)" : "var(--color-info)",
                  color: pending ? "var(--color-text-muted)" : "#0f0f0f",
                  fontSize: 12, fontWeight: 600,
                  display: "inline-flex", alignItems: "center", gap: 6,
                  cursor: pending ? "not-allowed" : "pointer",
                }}
              >
                {pending ? "Approving…" : "Approve & prepare"}
              </motion.button>
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
