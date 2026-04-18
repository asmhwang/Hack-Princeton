"use client";

import { useState } from "react";
import { motion, AnimatePresence, LayoutGroup } from "motion/react";
import type { ImpactReport, MitigationOption } from "@/types/schemas";
import { useApprove } from "@/hooks/useApprove";
import { useWarRoomStore } from "@/lib/store";
import { ApprovalModal } from "@/components/mitigation/ApprovalModal";
import { ExplainabilityDrawer } from "@/components/mitigation/ExplainabilityDrawer";
import { MitigationCard } from "@/components/mitigation/MitigationCard";

const spring = { type: "spring" as const, stiffness: 260, damping: 26 };

type MitigationCardStackProps = Readonly<{
  disruptionId: string | null;
  impact: ImpactReport | null;
  options: MitigationOption[];
}>;

export function MitigationCardStack({ disruptionId, impact, options }: MitigationCardStackProps) {
  const approve = useApprove(disruptionId);
  const pushActivity = useWarRoomStore((s) => s.pushActivity);
  const [approvalOption, setApprovalOption] = useState<MitigationOption | null>(null);
  const [explainOption, setExplainOption] = useState<MitigationOption | null>(null);
  const [approvedIds, setApprovedIds] = useState<Set<string>>(new Set());

  if (options.length === 0) {
    return (
      <section
        style={{
          borderRadius: 5,
          border: "1px dashed var(--color-border-strong)",
          padding: 16,
        }}
      >
        <p style={{ margin: 0, fontSize: 13, fontWeight: 500 }}>No mitigation options yet</p>
        <p style={{ margin: "8px 0 0", fontSize: 13, color: "var(--color-text-muted)" }}>
          Strategist output will appear after the impact report is ready.
        </p>
      </section>
    );
  }

  return (
    <>
      <LayoutGroup>
        <section style={{ display: "flex", flexDirection: "column", gap: 12 }}>
          <AnimatePresence initial={false}>
            {options.map((option, i) => (
              <motion.div
                key={option.id}
                layout
                initial={{ opacity: 0, y: 6 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: 6 }}
                transition={{ ...spring, delay: i * 0.03 }}
              >
                <MitigationCard
                  option={option}
                  index={i}
                  approved={approvedIds.has(option.id) || option.status === "approved"}
                  onApprove={() => setApprovalOption(option)}
                  onExplain={() => setExplainOption(option)}
                />
              </motion.div>
            ))}
          </AnimatePresence>
        </section>
      </LayoutGroup>

      <ApprovalModal
        option={approvalOption}
        open={Boolean(approvalOption)}
        pending={approve.isPending}
        onClose={() => setApprovalOption(null)}
        onConfirm={() => {
          if (approvalOption) {
            const pendingOption = approvalOption;
            approve.mutate(pendingOption.id, {
              onSuccess: () => {
                setApprovedIds((prev) => new Set([...prev, pendingOption.id]));
                pushActivity({
                  id: `approval-morph-${pendingOption.id}`,
                  agent: "System",
                  message: `Approved ${pendingOption.title ?? pendingOption.option_type.replaceAll("_", " ")}`,
                  severity: "success",
                  created_at: new Date().toISOString(),
                });
                setApprovalOption(null);
              },
            });
          }
        }}
      />

      <ExplainabilityDrawer
        open={Boolean(explainOption)}
        option={explainOption}
        impact={impact}
        onClose={() => setExplainOption(null)}
      />
    </>
  );
}
