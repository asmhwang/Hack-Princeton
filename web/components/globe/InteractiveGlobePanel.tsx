"use client";

import { useRef, useEffect, useState, useMemo } from "react";
import dynamic from "next/dynamic";
import type { ComponentType } from "react";
import type { GlobeRoute, RouteMode } from "@/components/globe/routes";
import { arcColorForRoute } from "@/components/globe/routes";
import { formatCurrency } from "@/lib/format";

// eslint-disable-next-line @typescript-eslint/no-explicit-any
type GlobeComponent = ComponentType<Record<string, any>>;

const GlobeGL = dynamic(
  () => import("react-globe.gl").then((m) => m.default as GlobeComponent),
  {
    ssr: false,
    loading: () => (
      <div style={{
        height: 460, background: "#0c0c0c",
        display: "flex", alignItems: "center", justifyContent: "center",
        color: "#444", fontSize: 11, fontFamily: "monospace", letterSpacing: "0.1em",
      }}>
        LOADING GLOBE…
      </div>
    ),
  },
) as GlobeComponent;

const MODE_LABEL: Record<RouteMode, string> = {
  ocean: "Ocean freight",
  air: "Air freight",
  rail: "Rail (intermodal)",
  truck: "Road / truck",
};

const MODE_COLOR: Record<RouteMode, string> = {
  ocean: "rgba(99,179,237,0.9)",
  air:   "rgba(167,139,250,0.9)",
  rail:  "rgba(251,191,36,0.9)",
  truck: "rgba(110,231,183,0.9)",
};

const STATUS_COLOR: Record<GlobeRoute["status"], string> = {
  blocked: "var(--color-critical)",
  watch:   "var(--color-warn)",
  good:    "var(--color-ok)",
};

type CityPoint = {
  lat: number;
  lng: number;
  city: string;
  mode: RouteMode;
  status: GlobeRoute["status"];
  isStorm?: boolean;
};

type Props = Readonly<{
  routes: GlobeRoute[];
  stormCenter?: { lat: number; lng: number } | null;
  disruptionTitle?: string;
}>;

// ─── City tooltip ─────────────────────────────────────────────────
function CityTooltip({
  point, routes, pos,
}: Readonly<{
  point: CityPoint;
  routes: GlobeRoute[];
  pos: { x: number; y: number };
}>) {
  const nodeRoutes = routes.filter(
    (r) =>
      (Math.abs(r.from[0] - point.lat) < 0.5 && Math.abs(r.from[1] - point.lng) < 0.5) ||
      (Math.abs(r.to[0] - point.lat) < 0.5 && Math.abs(r.to[1] - point.lng) < 0.5),
  );
  const totalExposure = nodeRoutes.reduce((s, r) => s + Number(r.exposure), 0);

  // Keep tooltip in viewport
  const left = Math.min(pos.x + 16, window.innerWidth - 280);
  const top = pos.y - 20;

  return (
    <div
      style={{
        position: "fixed",
        left,
        top,
        zIndex: 200,
        background: "var(--color-surface)",
        border: "1px solid var(--color-border-strong)",
        borderRadius: 6,
        width: 260,
        boxShadow: "0 12px 40px rgba(0,0,0,0.7)",
        pointerEvents: "none",
        overflow: "hidden",
      }}
    >
      {/* Header */}
      <div style={{
        padding: "10px 14px",
        borderBottom: "1px solid var(--color-border)",
        background: "var(--color-surface-raised)",
      }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <span style={{
            width: 8, height: 8, borderRadius: 8,
            background: point.isStorm ? "var(--color-critical)" : MODE_COLOR[point.mode],
            boxShadow: `0 0 0 3px ${point.isStorm ? "rgba(229,72,77,0.2)" : "rgba(99,179,237,0.2)"}`,
          }} />
          <span style={{ fontSize: 14, fontWeight: 700, letterSpacing: "-0.01em" }}>
            {point.city}
          </span>
        </div>
        {nodeRoutes.length > 0 && (
          <div style={{ marginTop: 4, fontSize: 11, color: "var(--color-text-subtle)" }}>
            {nodeRoutes.length} route{nodeRoutes.length === 1 ? "" : "s"} · {formatCurrency(totalExposure)} exposure
          </div>
        )}
      </div>

      {/* Route list */}
      {nodeRoutes.length > 0 && (
        <div style={{ padding: "8px 0" }}>
          {nodeRoutes.map((r) => (
            <div
              key={r.id}
              style={{
                display: "grid",
                gridTemplateColumns: "1fr auto",
                gap: 8,
                padding: "6px 14px",
                alignItems: "center",
              }}
            >
              <div>
                <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 2 }}>
                  <span style={{ width: 5, height: 5, borderRadius: 5, background: MODE_COLOR[r.mode], flexShrink: 0 }} />
                  <span style={{ fontSize: 11, color: "var(--color-text)", fontWeight: 500 }}>
                    {r.origin} → {r.destination}
                  </span>
                </div>
                <div style={{ fontSize: 10, color: "var(--color-text-subtle)", fontFamily: "var(--font-mono)", paddingLeft: 11 }}>
                  {MODE_LABEL[r.mode]} · {r.carrier} · {r.transit_days}d
                </div>
              </div>
              <div style={{ textAlign: "right" }}>
                <div className="tnum" style={{ fontSize: 11, fontWeight: 600 }}>
                  {formatCurrency(r.exposure)}
                </div>
                <div style={{ fontSize: 10, color: STATUS_COLOR[r.status], textTransform: "capitalize", fontWeight: 500 }}>
                  {r.status}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ─── Arc hover tooltip ────────────────────────────────────────────
function ArcTooltip({
  route, pos,
}: Readonly<{ route: GlobeRoute; pos: { x: number; y: number } }>) {
  const left = Math.min(pos.x + 16, window.innerWidth - 220);
  return (
    <div style={{
      position: "fixed", left, top: pos.y - 14,
      zIndex: 200,
      background: "var(--color-surface)",
      border: "1px solid var(--color-border-strong)",
      borderRadius: 5,
      padding: "8px 12px",
      pointerEvents: "none",
      width: 210,
      boxShadow: "0 8px 24px rgba(0,0,0,0.6)",
    }}>
      <div style={{ fontSize: 12, fontWeight: 600, marginBottom: 4 }}>
        {route.origin} → {route.destination}
      </div>
      <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 3 }}>
        <span style={{ width: 5, height: 5, borderRadius: 5, background: MODE_COLOR[route.mode] }} />
        <span style={{ fontSize: 11, color: "var(--color-text-muted)" }}>{MODE_LABEL[route.mode]}</span>
      </div>
      <div style={{ fontSize: 11, color: "var(--color-text-subtle)", fontFamily: "var(--font-mono)", marginBottom: 3 }}>
        {route.carrier} · {route.transit_days}d transit
      </div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginTop: 6, paddingTop: 6, borderTop: "1px solid var(--color-border)" }}>
        <span style={{ fontSize: 10, color: STATUS_COLOR[route.status], fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.04em" }}>
          {route.status}
        </span>
        <span className="tnum" style={{ fontSize: 12, fontWeight: 600 }}>{formatCurrency(route.exposure)}</span>
      </div>
    </div>
  );
}

// ─── Selected arc panel ───────────────────────────────────────────
function RouteDetailPanel({ route, onClose }: Readonly<{ route: GlobeRoute; onClose: () => void }>) {
  return (
    <div style={{
      position: "absolute", bottom: 0, left: 0, right: 0,
      background: "linear-gradient(0deg, rgba(10,10,10,0.98) 0%, rgba(10,10,10,0.9) 100%)",
      borderTop: "1px solid var(--color-border)",
      padding: "14px 20px",
      display: "grid",
      gridTemplateColumns: "200px 100px 130px 1fr auto",
      gap: 24,
      alignItems: "center",
      backdropFilter: "blur(12px)",
    }}>
      <div>
        <div style={{ fontSize: 10, color: "var(--color-text-subtle)", textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: 4 }}>Route</div>
        <div style={{ fontSize: 13, fontWeight: 600 }}>{route.origin} → {route.destination}</div>
        <div style={{ marginTop: 3, display: "flex", alignItems: "center", gap: 5 }}>
          <span style={{ width: 5, height: 5, borderRadius: 5, background: MODE_COLOR[route.mode] }} />
          <span style={{ fontSize: 11, color: "var(--color-text-subtle)" }}>{MODE_LABEL[route.mode]}</span>
          <span style={{ fontSize: 11, color: "var(--color-text-subtle)", fontFamily: "var(--font-mono)" }}>· {route.id}</span>
        </div>
      </div>
      <div>
        <div style={{ fontSize: 10, color: "var(--color-text-subtle)", textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: 4 }}>Status</div>
        <div style={{ display: "flex", alignItems: "center", gap: 5 }}>
          <span style={{ width: 6, height: 6, borderRadius: 6, background: STATUS_COLOR[route.status] }} />
          <span style={{ fontSize: 13, fontWeight: 600, color: STATUS_COLOR[route.status], textTransform: "capitalize" }}>{route.status}</span>
        </div>
        <div style={{ fontSize: 11, color: "var(--color-text-subtle)", marginTop: 3 }}>{route.carrier}</div>
      </div>
      <div>
        <div style={{ fontSize: 10, color: "var(--color-text-subtle)", textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: 4 }}>Exposure</div>
        <div className="tnum" style={{ fontSize: 15, fontWeight: 700, letterSpacing: "-0.01em" }}>{formatCurrency(route.exposure)}</div>
        <div style={{ fontSize: 11, color: "var(--color-text-subtle)", marginTop: 3 }}>{route.transit_days}d transit</div>
      </div>
      <div>
        <div style={{ fontSize: 10, color: "var(--color-text-subtle)", textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: 4 }}>Recommendation</div>
        <div style={{ fontSize: 12, lineHeight: "17px", color: "var(--color-text-muted)" }}>{route.recommendation}</div>
      </div>
      <button type="button" onClick={onClose} style={{
        width: 26, height: 26, borderRadius: 4,
        border: "1px solid var(--color-border)",
        background: "transparent", color: "var(--color-text-muted)",
        display: "flex", alignItems: "center", justifyContent: "center",
        cursor: "pointer", fontSize: 12, flexShrink: 0,
      }}>✕</button>
    </div>
  );
}

function pointColor(d: CityPoint, hovered: CityPoint | null): string {
  if (d.isStorm) return "rgba(229,72,77,0.95)";
  if (d.city === hovered?.city) return "rgba(255,255,255,0.95)";
  return MODE_COLOR[d.mode];
}

// ─── Main panel ───────────────────────────────────────────────────
export function InteractiveGlobePanel({ routes, stormCenter, disruptionTitle }: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [width, setWidth] = useState(800);
  const [selectedRoute, setSelectedRoute] = useState<GlobeRoute | null>(null);
  const [hoveredArc, setHoveredArc] = useState<GlobeRoute | null>(null);
  const [hoveredPoint, setHoveredPoint] = useState<CityPoint | null>(null);
  const [mousePos, setMousePos] = useState({ x: 0, y: 0 });

  useEffect(() => {
    if (!containerRef.current) return;
    const ro = new ResizeObserver((entries) => {
      const w = entries[0]?.contentRect.width;
      if (w) setWidth(w);
    });
    ro.observe(containerRef.current);
    setWidth(containerRef.current.offsetWidth);
    return () => ro.disconnect();
  }, []);

  // Deduplicated city points, picking the worst status for each city
  const points: CityPoint[] = useMemo(() => {
    function worstStatus(a: GlobeRoute["status"], b: GlobeRoute["status"]): GlobeRoute["status"] {
      if (a === "blocked" || b === "blocked") return "blocked";
      if (a === "watch" || b === "watch") return "watch";
      return "good";
    }
    const map = new Map<string, CityPoint>();
    for (const r of routes) {
      const fromKey = `${r.from[0].toFixed(2)},${r.from[1].toFixed(2)}`;
      const toKey = `${r.to[0].toFixed(2)},${r.to[1].toFixed(2)}`;
      const existing = map.get(fromKey);
      map.set(fromKey, {
        lat: r.from[0], lng: r.from[1], city: r.origin,
        mode: r.mode,
        status: existing ? worstStatus(existing.status, r.status) : r.status,
      });
      const existing2 = map.get(toKey);
      map.set(toKey, {
        lat: r.to[0], lng: r.to[1], city: r.destination,
        mode: r.mode,
        status: existing2 ? worstStatus(existing2.status, r.status) : r.status,
      });
    }
    return [...map.values()];
  }, [routes]);

  const allPoints: CityPoint[] = stormCenter
    ? [...points, { lat: stormCenter.lat, lng: stormCenter.lng, city: "Storm center", mode: "ocean", status: "blocked", isStorm: true }]
    : points;

  const stormRings = stormCenter ? [{ lat: stormCenter.lat, lng: stormCenter.lng }] : [];
  const globeHeight = selectedRoute ? 520 : 460;
  const showCityTooltip = hoveredPoint && !hoveredArc;

  return (
    <div
      ref={containerRef}
      aria-label="Interactive supply chain globe"
      data-testid="supply-globe-panel"
      style={{ position: "relative", borderBottom: "1px solid var(--color-border)", background: "#0c0c0c", overflow: "hidden" }}
      onMouseMove={(e) => setMousePos({ x: e.clientX, y: e.clientY })}
    >
      <GlobeGL
        width={width}
        height={globeHeight}
        backgroundColor="#0c0c0c00"
        globeImageUrl="//unpkg.com/three-globe/example/img/earth-night.jpg"
        bumpImageUrl="//unpkg.com/three-globe/example/img/earth-topology.png"
        atmosphereColor="rgba(130,110,80,0.25)"
        atmosphereAltitude={0.14}

        // ── Arcs ──────────────────────────────────────────────────
        arcsData={routes}
        arcStartLat={(d: GlobeRoute) => d.from[0]}
        arcStartLng={(d: GlobeRoute) => d.from[1]}
        arcEndLat={(d: GlobeRoute) => d.to[0]}
        arcEndLng={(d: GlobeRoute) => d.to[1]}
        arcColor={(d: GlobeRoute) => arcColorForRoute(d)}
        arcStroke={(d: GlobeRoute) => {
          if (d.id === selectedRoute?.id) return 1.4;
          if (d.id === hoveredArc?.id) return 1.0;
          if (d.status === "blocked") return 0.6;
          return 0.35;
        }}
        arcOpacity={1}
        arcDashLength={(d: GlobeRoute) => d.status === "blocked" ? 0.25 : 0.7}
        arcDashGap={(d: GlobeRoute) => d.status === "blocked" ? 0.08 : 0.4}
        arcDashAnimateTime={(d: GlobeRoute) => d.status === "blocked" ? 1400 : 2800}
        arcAltitudeAutoScale={0.3}
        onArcClick={(d: GlobeRoute) => setSelectedRoute((prev) => (prev?.id === d.id ? null : d))}
        onArcHover={(d: GlobeRoute | null) => setHoveredArc(d ?? null)}

        // ── City dots ─────────────────────────────────────────────
        pointsData={allPoints}
        pointLat={(d: CityPoint) => d.lat}
        pointLng={(d: CityPoint) => d.lng}
        pointColor={(d: CityPoint) => pointColor(d, hoveredPoint)}
        pointRadius={(d: CityPoint) => {
          if (d.isStorm) return 0.55;
          if (d.city === hoveredPoint?.city) return 0.5;
          return 0.28;
        }}
        pointAltitude={0.01}
        onPointHover={(d: CityPoint | null) => setHoveredPoint(d ?? null)}

        // ── Storm rings ───────────────────────────────────────────
        ringsData={stormRings}
        ringLat="lat"
        ringLng="lng"
        ringColor={() => ["rgba(229,72,77,0.7)", "rgba(229,72,77,0)"]}
        ringMaxRadius={5}
        ringPropagationSpeed={1.8}
        ringRepeatPeriod={750}

        enablePointerInteraction
      />

      {/* Title overlay */}
      <div style={{
        position: "absolute", top: 16, left: 20, right: 20,
        display: "flex", justifyContent: "space-between", alignItems: "flex-start",
        pointerEvents: "none",
      }}>
        <div>
          <div style={{ fontSize: 10, color: "#555", letterSpacing: "0.1em", textTransform: "uppercase", marginBottom: 4 }}>
            Global lane map
          </div>
          <div style={{ fontSize: 13, color: "#888" }}>
            {disruptionTitle ?? "Monitoring all active lanes"}
          </div>
        </div>

        {/* Two-row legend */}
        <div style={{ display: "flex", flexDirection: "column", gap: 6, alignItems: "flex-end" }}>
          <div style={{ display: "flex", gap: 14 }}>
            {(["blocked", "watch", "good"] as const).map((s) => (
              <div key={s} style={{ display: "flex", alignItems: "center", gap: 5, fontSize: 11, color: "#666" }}>
                <span style={{ width: 7, height: 7, borderRadius: 7, background: s === "blocked" ? "var(--color-critical)" : s === "watch" ? "var(--color-warn)" : "var(--color-ok)" }} />
                <span style={{ textTransform: "capitalize" }}>{s}</span>
              </div>
            ))}
          </div>
          <div style={{ display: "flex", gap: 12 }}>
            {(["ocean", "air", "rail", "truck"] as RouteMode[]).map((m) => (
              <div key={m} style={{ display: "flex", alignItems: "center", gap: 5, fontSize: 10, color: "#555" }}>
                <span style={{ width: 5, height: 5, borderRadius: 5, background: MODE_COLOR[m] }} />
                <span style={{ textTransform: "capitalize" }}>{m}</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Bottom hint */}
      {!selectedRoute && (
        <div style={{
          position: "absolute", bottom: 14, right: 20,
          fontSize: 10, color: "#444", fontFamily: "var(--font-mono)",
          pointerEvents: "none", letterSpacing: "0.06em",
        }}>
          DRAG · SCROLL · CLICK ARC · {routes.length} LANES
        </div>
      )}

      {/* City node tooltip */}
      {showCityTooltip && (
        <CityTooltip point={hoveredPoint} routes={routes} pos={mousePos} />
      )}

      {/* Arc hover tooltip */}
      {hoveredArc && !selectedRoute && !hoveredPoint && (
        <ArcTooltip route={hoveredArc} pos={mousePos} />
      )}

      {/* Selected route panel */}
      {selectedRoute && (
        <RouteDetailPanel route={selectedRoute} onClose={() => setSelectedRoute(null)} />
      )}
    </div>
  );
}
