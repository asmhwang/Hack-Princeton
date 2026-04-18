"use client";

import { AffectedShipmentsTable } from "@/components/disruption/AffectedShipmentsTable";
import { DisruptionHeader } from "@/components/disruption/DisruptionHeader";
import { MitigationCardStack } from "@/components/mitigation/MitigationCardStack";
import { InteractiveGlobePanel } from "@/components/globe/InteractiveGlobePanel";
import { routesFromShipments } from "@/components/globe/routes";
import { SectionHeading } from "@/components/ui/SectionHeading";
import { SqlPreview } from "@/components/ui/SqlPreview";
import { useDisruption, useImpact, useMitigations } from "@/hooks/useDisruptions";

function DisruptionDetailSkeleton() {
  return (
    <div>
      <div
        style={{
          borderBottom: "1px solid var(--color-border)",
          padding: "20px 24px",
          display: "flex",
          justifyContent: "space-between",
          gap: 32,
        }}
      >
        <div style={{ flex: 1 }}>
          <div className="shimmer" style={{ width: 160, height: 16, borderRadius: 3 }} />
          <div className="shimmer" style={{ width: "70%", height: 24, borderRadius: 3, marginTop: 10 }} />
          <div className="shimmer" style={{ width: "90%", height: 14, borderRadius: 3, marginTop: 10 }} />
          <div className="shimmer" style={{ width: "80%", height: 14, borderRadius: 3, marginTop: 6 }} />
        </div>
        <div
          style={{
            width: 280,
            display: "grid",
            gridTemplateColumns: "1fr 1fr",
            gap: 1,
            background: "var(--color-border)",
            border: "1px solid var(--color-border)",
            borderRadius: 5,
            overflow: "hidden",
          }}
        >
          {[0, 1, 2, 3].map((i) => (
            <div key={i} style={{ background: "var(--color-surface)", padding: 12 }}>
              <div className="shimmer" style={{ width: 50, height: 10, borderRadius: 3 }} />
              <div className="shimmer" style={{ width: 70, height: 18, borderRadius: 3, marginTop: 8 }} />
            </div>
          ))}
        </div>
      </div>
      <div className="shimmer" style={{ height: 360, borderBottom: "1px solid var(--color-border)" }} />
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "minmax(0,1fr) 380px",
          gap: 20,
          padding: 24,
        }}
      >
        <div>
          <div style={{ border: "1px solid var(--color-border)", borderRadius: 5, overflow: "hidden" }}>
            <div className="shimmer" style={{ height: 40 }} />
            {[0, 1, 2, 3, 4].map((i) => (
              <div
                key={i}
                style={{
                  padding: "10px 12px",
                  borderTop: "1px solid var(--color-border)",
                  display: "flex",
                  gap: 12,
                }}
              >
                <div className="shimmer" style={{ width: 80, height: 12, borderRadius: 3 }} />
                <div className="shimmer" style={{ width: 70, height: 12, borderRadius: 3 }} />
                <div className="shimmer" style={{ width: 120, height: 12, borderRadius: 3 }} />
                <div className="shimmer" style={{ flex: 1, height: 12, borderRadius: 3 }} />
                <div className="shimmer" style={{ width: 60, height: 12, borderRadius: 3 }} />
              </div>
            ))}
          </div>
        </div>
        <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
          {[0, 1, 2].map((i) => (
            <div
              key={i}
              style={{
                border: "1px solid var(--color-border)",
                borderRadius: 5,
                padding: 16,
                height: 180,
                display: "flex",
                flexDirection: "column",
                gap: 10,
              }}
            >
              <div className="shimmer" style={{ width: "70%", height: 14, borderRadius: 3 }} />
              <div className="shimmer" style={{ width: "90%", height: 10, borderRadius: 3 }} />
              <div className="shimmer" style={{ width: "80%", height: 10, borderRadius: 3 }} />
              <div style={{ display: "flex", gap: 12, marginTop: "auto" }}>
                <div className="shimmer" style={{ flex: 1, height: 30, borderRadius: 3 }} />
                <div className="shimmer" style={{ flex: 1, height: 30, borderRadius: 3 }} />
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

type DisruptionDetailViewProps = Readonly<{ disruptionId: string }>;

export function DisruptionDetailView({ disruptionId }: DisruptionDetailViewProps) {
  const disruption = useDisruption(disruptionId);
  const impact = useImpact(disruptionId);
  const mitigations = useMitigations(disruptionId);

  if (disruption.isLoading || impact.isLoading || mitigations.isLoading) {
    return <DisruptionDetailSkeleton />;
  }

  if (!disruption.data) {
    return (
      <section style={{ padding: 24 }}>
        <div
          style={{
            border: "1px dashed var(--color-border-strong)",
            borderRadius: 5,
            padding: 16,
          }}
        >
          <p style={{ margin: 0, fontSize: 13, fontWeight: 500 }}>Disruption not available</p>
          <p style={{ margin: "8px 0 0", fontSize: 13, color: "var(--color-text-muted)" }}>
            The selected disruption could not be loaded from the API.
          </p>
        </div>
      </section>
    );
  }

  const shipments = impact.data?.affected_shipments ?? [];
  const routes = routesFromShipments(shipments);
  const sql = impact.data?.sql_executed ?? impact.data?.generated_sql;
  const stormCenter =
    disruption.data.category === "weather" &&
    disruption.data.lat !== null &&
    disruption.data.lat !== undefined &&
    disruption.data.lng !== null &&
    disruption.data.lng !== undefined
      ? { lat: disruption.data.lat, lng: disruption.data.lng }
      : null;

  return (
    <div style={{ minHeight: "100%" }}>
      <DisruptionHeader disruption={disruption.data} impact={impact.data ?? null} />
      <InteractiveGlobePanel
        routes={routes}
        stormCenter={stormCenter}
        disruptionTitle={disruption.data.title}
      />
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "minmax(0,1fr) 380px",
          gap: 20,
          padding: 24,
        }}
      >
        <div>
          <SectionHeading title="Affected shipments" count={shipments.length} />
          <AffectedShipmentsTable shipments={shipments} />
          {sql && (
            <>
              <div style={{ height: 24 }} />
              <SectionHeading title="Impact query" meta="Analyst" />
              <SqlPreview sql={sql} />
            </>
          )}
        </div>
        <div>
          <SectionHeading title="Mitigation options" count={mitigations.data?.length ?? 0} />
          <MitigationCardStack
            disruptionId={disruptionId}
            impact={impact.data ?? null}
            options={mitigations.data ?? []}
          />
        </div>
      </div>
    </div>
  );
}
