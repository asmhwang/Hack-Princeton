"use client";

import { useWarRoomStore } from "@/lib/store";
import { useActiveRoutes } from "@/hooks/useActiveRoutes";
import { useDisruptions, useExposureSummary } from "@/hooks/useDisruptions";
import { useSimulate } from "@/hooks/useSimulate";
import { DisruptionDetailView } from "@/components/disruption/DisruptionDetailView";
import { InteractiveGlobePanel } from "@/components/globe/InteractiveGlobePanel";
import { demoRoutes, routesFromActiveRoutes } from "@/components/globe/routes";
import { categoryTokens } from "@/lib/design-tokens";
import { formatCurrency, formatRelativeTime, eventTime } from "@/lib/format";

function StatusGrid() {
  const { data: summary } = useExposureSummary();
  const { data: disruptions = [] } = useDisruptions();

  const active = summary?.active_count ?? disruptions.length;
  const totalExp = summary?.total_exposure ?? "0";
  const blocked = disruptions.filter((d) => d.status === "active" && d.severity >= 4).length;

  const statusLabel = active > 0 ? "ESCALATED" : "NOMINAL";
  const statusColor = active > 0 ? "var(--color-critical)" : "var(--color-ok)";

  const cells = [
    { label: "Status", value: statusLabel, color: statusColor, mono: true },
    { label: "Active", value: String(active), color: active > 0 ? "var(--color-critical)" : "var(--color-ok)" },
    { label: "Exposure", value: formatCurrency(totalExp), mono: true },
    { label: "High sev", value: String(blocked), color: blocked > 0 ? "var(--color-critical)" : "var(--color-text)" },
    { label: "Agents", value: "3 / 3", color: "var(--color-ok)" },
  ];

  return (
    <div style={{
      display: "grid",
      gridTemplateColumns: "repeat(5, 1fr)",
      gap: 1,
      background: "var(--color-border)",
      border: "1px solid var(--color-border)",
      borderRadius: 5,
      overflow: "hidden",
      marginBottom: 24,
    }}>
      {cells.map(({ label, value, color, mono }) => (
        <div key={label} style={{ background: "var(--color-surface)", padding: "12px 16px" }}>
          <div style={{ fontSize: 10, color: "var(--color-text-subtle)", textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: 4 }}>
            {label}
          </div>
          <div
            className="tnum"
            style={{
              fontSize: 16,
              fontWeight: 700,
              color: color ?? "var(--color-text)",
              letterSpacing: "-0.01em",
              fontFamily: mono ? "var(--font-mono)" : undefined,
              whiteSpace: "nowrap",
              overflow: "hidden",
              textOverflow: "ellipsis",
            }}
          >
            {value}
          </div>
        </div>
      ))}
    </div>
  );
}

function RecentDisruptions() {
  const { data: disruptions = [], isLoading } = useDisruptions();
  const setSelectedDisruptionId = useWarRoomStore((s) => s.setSelectedDisruptionId);

  if (isLoading) {
    return (
      <div style={{ border: "1px solid var(--color-border)", borderRadius: 5, overflow: "hidden" }}>
        {[0, 1, 2].map((i) => (
          <div key={i} style={{ padding: "12px 16px", borderTop: i === 0 ? "none" : "1px solid var(--color-border)", display: "flex", gap: 12 }}>
            <div className="shimmer" style={{ width: 60, height: 14, borderRadius: 3 }} />
            <div className="shimmer" style={{ flex: 1, height: 14, borderRadius: 3 }} />
            <div className="shimmer" style={{ width: 80, height: 14, borderRadius: 3 }} />
          </div>
        ))}
      </div>
    );
  }

  if (disruptions.length === 0) {
    return (
      <div style={{
        border: "1px dashed var(--color-border-strong)",
        borderRadius: 5, padding: "20px 16px",
        textAlign: "center",
      }}>
        <div style={{ fontSize: 13, fontWeight: 500, marginBottom: 6 }}>No active disruptions</div>
        <div style={{ fontSize: 12, color: "var(--color-text-muted)" }}>
          Scout is monitoring 47 signals. Simulate an event to see the full workflow.
        </div>
      </div>
    );
  }

  const sorted = [...disruptions].sort((a, b) => Number(b.total_exposure) - Number(a.total_exposure)).slice(0, 6);

  return (
    <div style={{ border: "1px solid var(--color-border)", borderRadius: 5, overflow: "hidden", background: "var(--color-surface)" }}>
      <div style={{ padding: "10px 16px", borderBottom: "1px solid var(--color-border)", display: "flex", alignItems: "center", justifyContent: "space-between" }}>
        <h3 style={{ margin: 0, fontSize: 12, fontWeight: 500, textTransform: "uppercase", letterSpacing: "0.08em" }}>Active disruptions</h3>
        <span className="tnum" style={{ fontSize: 11, color: "var(--color-text-subtle)", fontFamily: "var(--font-mono)" }}>{disruptions.length}</span>
      </div>
      {sorted.map((d, i) => {
        const token = categoryTokens[d.category];
        return (
          <button
            key={d.id}
            type="button"
            onClick={() => setSelectedDisruptionId(d.id)}
            className="ship-row"
            style={{
              width: "100%",
              display: "grid",
              gridTemplateColumns: "88px minmax(0,1fr) 96px 100px 72px",
              gap: 12,
              padding: "11px 16px",
              alignItems: "center",
              borderTop: i === 0 ? "none" : "1px solid var(--color-border)",
              borderRight: "none",
              borderBottom: "none",
              borderLeft: "none",
              background: "transparent",
              cursor: "pointer",
              textAlign: "left",
              fontSize: 12,
            }}
          >
            <span style={{
              color: token.color, background: token.bg,
              padding: "2px 7px", borderRadius: 3,
              fontSize: 10, fontWeight: 500,
              textTransform: "uppercase", letterSpacing: "0.04em",
              display: "inline-block",
            }}>
              {token.label}
            </span>
            <span style={{ fontWeight: 500, color: "var(--color-text)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
              {d.title}
            </span>
            <span style={{ color: "var(--color-text-subtle)", fontSize: 11 }}>{d.region}</span>
            <span className="tnum" style={{ fontWeight: 600, textAlign: "right" }}>{formatCurrency(d.total_exposure)}</span>
            <span className="tnum" style={{ color: "var(--color-text-subtle)", fontSize: 11, fontFamily: "var(--font-mono)", textAlign: "right" }}>
              {formatRelativeTime(eventTime(d.detected_at ?? d.first_seen_at))}
            </span>
          </button>
        );
      })}
    </div>
  );
}

function SimulateCard() {
  const simulate = useSimulate();
  const scenarios = [
    { id: "typhoon_kaia", label: "Typhoon Kaia", desc: "Cat 3 · Shenzhen landfall · Yantian closure", cat: "weather" },
    { id: "busan_strike", label: "Busan strike", desc: "KPTU 72h stoppage · Asia-Pacific corridor", cat: "logistics" },
    { id: "cbam_tariff", label: "EU CBAM tariff", desc: "Q2 CBAM bracket shift · Class-B steel", cat: "policy" },
    { id: "luxshare_fire", label: "Luxshare fire", desc: "Kunshan plant · 7–10d production gap", cat: "news" },
    { id: "redsea_advisory", label: "Red Sea advisory", desc: "UKMTO Q2 extension · Cape routing", cat: "policy" },
  ];

  return (
    <div style={{ border: "1px solid var(--color-border)", borderRadius: 5, overflow: "hidden", background: "var(--color-surface)" }}>
      <div style={{ padding: "10px 16px", borderBottom: "1px solid var(--color-border)" }}>
        <h3 style={{ margin: 0, fontSize: 12, fontWeight: 500, textTransform: "uppercase", letterSpacing: "0.08em" }}>
          Simulate scenario
        </h3>
      </div>
      <div style={{ padding: "10px 10px", display: "flex", flexDirection: "column", gap: 6 }}>
        {scenarios.map((s) => {
          const token = categoryTokens[s.cat as keyof typeof categoryTokens] ?? categoryTokens.logistics;
          return (
            <button
              key={s.id}
              type="button"
              onClick={() => simulate.mutate(s.id)}
              disabled={simulate.isPending}
              style={{
                display: "flex",
                alignItems: "center",
                gap: 12,
                padding: "9px 12px",
                borderRadius: 4,
                border: "1px solid var(--color-border)",
                background: "var(--color-bg)",
                cursor: simulate.isPending ? "not-allowed" : "pointer",
                opacity: simulate.isPending ? 0.5 : 1,
                textAlign: "left",
              }}
              onMouseEnter={(e) => { if (!simulate.isPending) e.currentTarget.style.borderColor = "var(--color-border-strong)"; }}
              onMouseLeave={(e) => { e.currentTarget.style.borderColor = "var(--color-border)"; }}
            >
              <span style={{
                fontSize: 9, fontWeight: 500,
                color: token.color, background: token.bg,
                padding: "2px 5px", borderRadius: 2,
                textTransform: "uppercase", letterSpacing: "0.04em",
                flexShrink: 0,
              }}>
                {token.label}
              </span>
              <div style={{ minWidth: 0, flex: 1 }}>
                <div
                  style={{
                    fontSize: 12,
                    fontWeight: 500,
                    color: "var(--color-text)",
                    whiteSpace: "nowrap",
                    overflow: "hidden",
                    textOverflow: "ellipsis",
                  }}
                >
                  {s.label}
                </div>
                <div
                  style={{
                    fontSize: 11,
                    color: "var(--color-text-subtle)",
                    marginTop: 1,
                    display: "-webkit-box",
                    WebkitLineClamp: 2,
                    WebkitBoxOrient: "vertical",
                    overflow: "hidden",
                    lineHeight: "15px",
                  }}
                >
                  {s.desc}
                </div>
              </div>
              <span style={{
                marginLeft: "auto",
                width: 0, height: 0,
                borderTop: "4px solid transparent",
                borderBottom: "4px solid transparent",
                borderLeft: "6px solid var(--color-text-subtle)",
                flexShrink: 0,
              }} />
            </button>
          );
        })}
      </div>
    </div>
  );
}

export default function WarRoomPage() {
  const selectedDisruptionId = useWarRoomStore((s) => s.selectedDisruptionId);
  const { data: activeRoutes = [] } = useActiveRoutes();

  if (selectedDisruptionId) {
    return <DisruptionDetailView disruptionId={selectedDisruptionId} />;
  }

  // Prefer real routes; fall back to demoRoutes when the active list is empty
  // (cold start, or post-clear) so the globe never renders blank.
  const routes = activeRoutes.length > 0 ? routesFromActiveRoutes(activeRoutes) : demoRoutes;

  return (
    <div style={{ minHeight: "100%" }}>
      <InteractiveGlobePanel routes={routes} />
      <div style={{ padding: 24, display: "grid", gridTemplateColumns: "1fr 340px", gap: 20, alignItems: "start" }}>
        <div>
          <StatusGrid />
          <RecentDisruptions />
        </div>
        <SimulateCard />
      </div>
    </div>
  );
}
