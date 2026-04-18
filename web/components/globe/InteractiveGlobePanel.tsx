"use client";

import { useRef, useEffect, useState, useMemo } from "react";
import dynamic from "next/dynamic";
import type { ComponentType } from "react";
import * as THREE from "three";
import { AnimatePresence, motion } from "motion/react";
import type { AlternativeRoute, GlobeRoute, RouteMode } from "@/components/globe/routes";
import { arcColorForRoute } from "@/components/globe/routes";
import { formatCurrency } from "@/lib/format";

// Per-mode arc altitude. Rail/truck hug the surface; ocean rides low; air arches high.
// Values nudged up from {rail/truck: 0.005, ocean: 0.05} so the tube-segment chords
// don't dip below the globe mesh on long arcs (esp. Shanghai→Hamburg rail,
// Shanghai→Rotterdam ocean).
const MODE_ALTITUDE: Record<RouteMode, number> = {
  rail:  0.02,
  truck: 0.02,
  ocean: 0.14,
  air:   0.22,
};

// Path accessors — hoisted so their identities are stable across re-renders
// (mousemove causes frequent re-renders; inline fns would trip react-globe.gl
// into redrawing the paths and resetting the dash animation).
const pathPoints = (d: AlternativeRoute) => d.waypoints;
const pathPointLat = (p: [number, number]) => p[0];
const pathPointLng = (p: [number, number]) => p[1];
const pathPointAlt = () => 0.005;
const PATH_MODE_COLOR: Record<RouteMode, string> = {
  ocean: "rgba(99,179,237,0.85)",
  air:   "rgba(167,139,250,0.85)",
  rail:  "rgba(251,191,36,0.85)",
  truck: "rgba(110,231,183,0.85)",
};
const pathColor = (d: AlternativeRoute) => PATH_MODE_COLOR[d.mode];

// ─── Arc hit layer (invisible thick tubes for easier click/hover) ──
// Decouples hit-area from visible stroke: we keep `arcStroke` thin for looks
// and raycast against fat transparent tubes rendered here via customLayerData.
const GLOBE_RADIUS = 100; // three-globe default
const HIT_TUBE_RADIUS = 1.6; // ~1.6% of globe radius — generous click target
const HIT_TUBE_SEGMENTS = 48;

// Material is transparent-ish but still hit-testable. opacity: 0 can cause some
// three.js pipelines to skip raycasting, so we use a vanishingly small value.
const HIT_TUBE_MATERIAL = new THREE.MeshBasicMaterial({
  transparent: true,
  opacity: 0.001,
  depthWrite: false,
});

function latLngToUnitVec3(lat: number, lng: number): THREE.Vector3 {
  const phi = ((90 - lat) * Math.PI) / 180;
  const theta = ((lng + 180) * Math.PI) / 180;
  return new THREE.Vector3(
    -Math.sin(phi) * Math.cos(theta),
     Math.cos(phi),
     Math.sin(phi) * Math.sin(theta),
  );
}

function greatCircleArcPoints(
  from: [number, number],
  to: [number, number],
  peakAltitude: number,
  segments: number = HIT_TUBE_SEGMENTS,
): THREE.Vector3[] {
  const a = latLngToUnitVec3(from[0], from[1]);
  const b = latLngToUnitVec3(to[0], to[1]);
  const omega = a.angleTo(b);
  const sinOmega = Math.sin(omega);
  const out: THREE.Vector3[] = [];
  for (let i = 0; i <= segments; i++) {
    const t = i / segments;
    let p: THREE.Vector3;
    if (sinOmega < 1e-6) {
      p = a.clone().lerp(b, t).normalize();
    } else {
      const wa = Math.sin((1 - t) * omega) / sinOmega;
      const wb = Math.sin(t * omega) / sinOmega;
      p = a.clone().multiplyScalar(wa).add(b.clone().multiplyScalar(wb)).normalize();
    }
    // Parabolic altitude envelope peaking at t=0.5, matching three-globe's arc shape.
    // +0.006 baseline so ground-hugging tubes sit slightly above the globe mesh
    // and rays from the camera don't get eaten by the sphere surface first.
    const altFactor = 1 + peakAltitude * 4 * t * (1 - t) + 0.006;
    p.multiplyScalar(GLOBE_RADIUS * altFactor);
    out.push(p);
  }
  return out;
}

function makeArcHitMesh(route: GlobeRoute): THREE.Mesh {
  const points = greatCircleArcPoints(route.from, route.to, MODE_ALTITUDE[route.mode]);
  const curve = new THREE.CatmullRomCurve3(points);
  const geo = new THREE.TubeGeometry(curve, HIT_TUBE_SEGMENTS, HIT_TUBE_RADIUS, 8, false);
  return new THREE.Mesh(geo, HIT_TUBE_MATERIAL);
}

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
  const hasAlts = route.status === "blocked" && (route.alternatives?.length ?? 0) > 0;
  const width = hasAlts ? 320 : 210;
  const left = Math.min(pos.x + 16, window.innerWidth - width - 8);
  return (
    <div style={{
      position: "fixed", left, top: pos.y - 14,
      zIndex: 200,
      background: "var(--color-surface)",
      border: "1px solid var(--color-border-strong)",
      borderRadius: 5,
      padding: "8px 12px",
      pointerEvents: "none",
      width,
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

      {hasAlts && (
        <div style={{ marginTop: 8, paddingTop: 8, borderTop: "1px solid var(--color-border)" }}>
          <div style={{
            fontSize: 9, color: "var(--color-text-subtle)",
            textTransform: "uppercase", letterSpacing: "0.08em", marginBottom: 6,
          }}>
            {route.alternatives!.length} alternative{route.alternatives!.length === 1 ? "" : "s"}
          </div>
          {route.alternatives!.map((alt) => (
            <AltRow key={alt.id} alt={alt} />
          ))}
        </div>
      )}
    </div>
  );
}

function AltRow({ alt }: Readonly<{ alt: AlternativeRoute }>) {
  const costSign = alt.extra_cost_usd >= 0 ? "+" : "−";
  const timeSign = alt.time_delta_days >= 0 ? "+" : "−";
  return (
    <div style={{ marginBottom: 8 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 2 }}>
        <span style={{ width: 5, height: 5, borderRadius: 5, background: MODE_COLOR[alt.mode], flexShrink: 0 }} />
        <span style={{ fontSize: 11, fontWeight: 600, color: "var(--color-text)" }}>{alt.label}</span>
      </div>
      <div style={{ display: "flex", gap: 10, paddingLeft: 11, marginBottom: 2, fontFamily: "var(--font-mono)" }}>
        <span style={{ fontSize: 10, color: "var(--color-text-muted)" }} className="tnum">
          {costSign}{formatCurrency(Math.abs(alt.extra_cost_usd))}
        </span>
        <span style={{ fontSize: 10, color: "var(--color-text-muted)" }} className="tnum">
          {timeSign}{Math.abs(alt.time_delta_days)}d
        </span>
        <span style={{ fontSize: 10, color: "var(--color-ok)" }} className="tnum">
          {alt.confidence_pct}% conf
        </span>
      </div>
      <div style={{ paddingLeft: 11, fontSize: 10, color: "var(--color-text-subtle)", lineHeight: "14px" }}>
        {alt.reason}
      </div>
    </div>
  );
}

// ─── Selected arc panel ───────────────────────────────────────────
function RouteDetailPanel({ route, onClose }: Readonly<{ route: GlobeRoute; onClose: () => void }>) {
  const hasAlts = route.status === "blocked" && (route.alternatives?.length ?? 0) > 0;
  return (
    <motion.div
      initial={{ y: 60, opacity: 0 }}
      animate={{ y: 0, opacity: 1 }}
      exit={{ y: 60, opacity: 0 }}
      transition={{ type: "spring", stiffness: 260, damping: 26, mass: 0.9 }}
      style={{
        position: "absolute", bottom: 0, left: 0, right: 0,
        background: "linear-gradient(0deg, rgba(10,10,10,0.98) 0%, rgba(10,10,10,0.9) 100%)",
        borderTop: "1px solid var(--color-border)",
        padding: "14px 20px",
        display: "grid",
        gridTemplateColumns: "200px 100px 130px 1fr auto",
        gap: 24,
        alignItems: "center",
        backdropFilter: "blur(12px)",
      }}
    >
      <div>
        <div style={{ fontSize: 10, color: "var(--color-text-subtle)", textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: 4 }}>Route</div>
        <div style={{ fontSize: 13, fontWeight: 600 }}>{route.origin} → {route.destination}</div>
        <div style={{ marginTop: 3, display: "flex", alignItems: "center", gap: 5 }}>
          <span style={{ width: 5, height: 5, borderRadius: 5, background: MODE_COLOR[route.mode] }} />
          <span style={{ fontSize: 11, color: "var(--color-text-subtle)" }}>{MODE_LABEL[route.mode]}</span>
          <span style={{ fontSize: 11, color: "var(--color-text-subtle)", fontFamily: "var(--font-mono)" }}>· {route.carrier} · {route.transit_days}d</span>
        </div>
      </div>
      <div>
        <div style={{ fontSize: 10, color: "var(--color-text-subtle)", textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: 4 }}>Status</div>
        <div style={{ display: "flex", alignItems: "center", gap: 5 }}>
          <span style={{ width: 6, height: 6, borderRadius: 6, background: STATUS_COLOR[route.status] }} />
          <span style={{ fontSize: 13, fontWeight: 600, color: STATUS_COLOR[route.status], textTransform: "capitalize" }}>{route.status}</span>
        </div>
        <div style={{ fontSize: 11, color: "var(--color-text-subtle)", marginTop: 3, fontFamily: "var(--font-mono)" }}>{route.id}</div>
      </div>
      <div>
        <div style={{ fontSize: 10, color: "var(--color-text-subtle)", textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: 4 }}>Exposure</div>
        <div className="tnum" style={{ fontSize: 15, fontWeight: 700, letterSpacing: "-0.01em" }}>{formatCurrency(route.exposure)}</div>
        <div style={{ fontSize: 11, color: "var(--color-text-subtle)", marginTop: 3 }}>{route.transit_days}d transit</div>
      </div>
      <div>
        <div style={{ fontSize: 10, color: "var(--color-text-subtle)", textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: 6 }}>
          {hasAlts ? `${route.alternatives!.length} alternatives` : "Recommendation"}
        </div>
        {hasAlts ? (
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
            {route.alternatives!.map((alt) => (
              <PanelAltCard key={alt.id} alt={alt} />
            ))}
          </div>
        ) : (
          <div style={{ fontSize: 12, lineHeight: "17px", color: "var(--color-text-muted)" }}>{route.recommendation}</div>
        )}
      </div>
      <button type="button" onClick={onClose} style={{
        width: 26, height: 26, borderRadius: 4,
        border: "1px solid var(--color-border)",
        background: "transparent", color: "var(--color-text-muted)",
        display: "flex", alignItems: "center", justifyContent: "center",
        cursor: "pointer", fontSize: 12, flexShrink: 0,
      }}>✕</button>
    </motion.div>
  );
}

function PanelAltCard({ alt }: Readonly<{ alt: AlternativeRoute }>) {
  const costSign = alt.extra_cost_usd >= 0 ? "+" : "−";
  const timeSign = alt.time_delta_days >= 0 ? "+" : "−";
  return (
    <div style={{
      border: "1px solid var(--color-border)",
      borderRadius: 4,
      padding: "8px 10px",
      background: "rgba(255,255,255,0.02)",
    }}>
      <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 4 }}>
        <span style={{ width: 5, height: 5, borderRadius: 5, background: MODE_COLOR[alt.mode], flexShrink: 0 }} />
        <span style={{ fontSize: 11, fontWeight: 600, color: "var(--color-text)" }}>{alt.label}</span>
      </div>
      <div style={{ display: "flex", gap: 10, marginBottom: 4, fontFamily: "var(--font-mono)" }}>
        <span className="tnum" style={{ fontSize: 10, color: "var(--color-text-muted)" }}>
          {costSign}{formatCurrency(Math.abs(alt.extra_cost_usd))}
        </span>
        <span className="tnum" style={{ fontSize: 10, color: "var(--color-text-muted)" }}>
          {timeSign}{Math.abs(alt.time_delta_days)}d
        </span>
        <span className="tnum" style={{ fontSize: 10, color: "var(--color-ok)" }}>
          {alt.confidence_pct}% conf
        </span>
      </div>
      <div style={{ fontSize: 10, color: "var(--color-text-subtle)", lineHeight: "14px" }}>
        {alt.reason}
      </div>
    </div>
  );
}

function pointColor(d: CityPoint, hovered: CityPoint | null): string {
  if (d.isStorm) return "rgba(229,72,77,0.95)";
  if (d.city === hovered?.city) return "rgba(255,255,255,0.95)";
  return MODE_COLOR[d.mode];
}

// ─── Tooltip overlay (owns mousePos) ──────────────────────────────
// Kept separate so mouse-tracking doesn't re-render the GlobeGL-hosting parent.
function TooltipOverlay({
  hoveredArc, hoveredPoint, hasSelectedRoute, routes,
}: Readonly<{
  hoveredArc: GlobeRoute | null;
  hoveredPoint: CityPoint | null;
  hasSelectedRoute: boolean;
  routes: GlobeRoute[];
}>) {
  const [pos, setPos] = useState({ x: 0, y: 0 });
  const active = !!(hoveredArc || hoveredPoint);

  useEffect(() => {
    if (!active) return;
    const handler = (e: MouseEvent) => setPos({ x: e.clientX, y: e.clientY });
    window.addEventListener("mousemove", handler);
    return () => window.removeEventListener("mousemove", handler);
  }, [active]);

  const showCityTooltip = hoveredPoint && !hoveredArc;
  const showArcTooltip = hoveredArc && !hasSelectedRoute && !hoveredPoint;

  return (
    <>
      {showCityTooltip && (
        <CityTooltip point={hoveredPoint} routes={routes} pos={pos} />
      )}
      {showArcTooltip && (
        <ArcTooltip route={hoveredArc} pos={pos} />
      )}
    </>
  );
}

// ─── Main panel ───────────────────────────────────────────────────
export function InteractiveGlobePanel({ routes, stormCenter, disruptionTitle }: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const globeRef = useRef<any>(null);
  const [width, setWidth] = useState(800);
  const [selectedRoute, setSelectedRoute] = useState<GlobeRoute | null>(null);
  const [hoveredArc, setHoveredArc] = useState<GlobeRoute | null>(null);
  const [hoveredPoint, setHoveredPoint] = useState<CityPoint | null>(null);

  // Alternatives to show: hovered blocked route wins, else selected blocked route.
  // Memoized against mousemove-driven re-renders — a new array reference makes
  // react-globe.gl think the path data changed and retriggers its transition.
  const alternativePaths = useMemo<AlternativeRoute[]>(() => {
    const blocked = (r: GlobeRoute | null) =>
      r?.status === "blocked" && (r.alternatives?.length ?? 0) > 0 ? r : null;
    const source = blocked(hoveredArc) ?? blocked(selectedRoute);
    return source?.alternatives ?? [];
    // Deps are the IDs, not the objects — referential stability is the whole
    // point here. The alternatives array per route is immutable.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [hoveredArc?.id, selectedRoute?.id]);

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

  return (
    <div
      ref={containerRef}
      aria-label="Interactive supply chain globe"
      data-testid="supply-globe-panel"
      style={{ position: "relative", borderBottom: "1px solid var(--color-border)", background: "#0c0c0c", overflow: "hidden" }}
    >
      <GlobeGL
        ref={globeRef}
        width={width}
        height={globeHeight}
        backgroundColor="#0c0c0c00"
        globeImageUrl="//unpkg.com/three-globe/example/img/earth-night.jpg"
        bumpImageUrl="//unpkg.com/three-globe/example/img/earth-topology.png"
        atmosphereColor="rgba(130,110,80,0.25)"
        atmosphereAltitude={0.14}
        onGlobeReady={() => {
          if (globeRef.current?.pointOfView) {
            globeRef.current.pointOfView({ lat: 20, lng: 110, altitude: 1.8 }, 0);
          }
        }}

        // ── Arcs ──────────────────────────────────────────────────
        arcsData={routes}
        arcStartLat={(d: GlobeRoute) => d.from[0]}
        arcStartLng={(d: GlobeRoute) => d.from[1]}
        arcEndLat={(d: GlobeRoute) => d.to[0]}
        arcEndLng={(d: GlobeRoute) => d.to[1]}
        arcColor={(d: GlobeRoute) => arcColorForRoute(d)}
        arcStroke={(d: GlobeRoute) => {
          // Visual width only — the hit-area lives on a separate invisible
          // customLayerData tube (see makeArcHitMesh).
          if (d.id === selectedRoute?.id) return 1.4;
          if (d.id === hoveredArc?.id) return 1.0;
          if (d.status === "blocked") return 0.6;
          return 0.35;
        }}
        arcOpacity={1}
        arcDashLength={(d: GlobeRoute) => d.status === "blocked" ? 0.25 : 0.7}
        arcDashGap={(d: GlobeRoute) => d.status === "blocked" ? 0.08 : 0.4}
        arcDashAnimateTime={(d: GlobeRoute) => d.status === "blocked" ? 1400 : 2800}
        arcAltitude={(d: GlobeRoute) => MODE_ALTITUDE[d.mode]}
        // Keep arc hover/click handlers as a fallback — they still fire on
        // direct hits against the thin visible mesh, while the custom hit-
        // layer below widens the hit area everywhere else.
        onArcClick={(d: GlobeRoute) => setSelectedRoute((prev) => (prev?.id === d.id ? null : d))}
        onArcHover={(d: GlobeRoute | null) => setHoveredArc(d ?? null)}

        // ── Invisible hit layer (fat transparent tubes along each arc's great circle) ─
        customLayerData={routes}
        customThreeObject={(d: GlobeRoute) => makeArcHitMesh(d)}
        customThreeObjectUpdate={() => { /* static geometry */ }}
        onCustomLayerClick={(d: GlobeRoute) => setSelectedRoute((prev) => (prev?.id === d.id ? null : d))}
        onCustomLayerHover={(d: GlobeRoute | null) => setHoveredArc(d ?? null)}

        // ── Alternative paths (appear on hover/select of blocked routes) ─
        pathsData={alternativePaths}
        pathPoints={pathPoints}
        pathPointLat={pathPointLat}
        pathPointLng={pathPointLng}
        pathPointAlt={pathPointAlt}
        pathColor={pathColor}
        pathStroke={0.6}
        pathDashLength={0.35}
        pathDashGap={0.18}
        pathDashAnimateTime={2200}
        pathTransitionDuration={0}

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

      {/* Tooltip overlay — owns its own mousePos state so tracking the cursor
          doesn't re-render the parent (and thus doesn't thrash GlobeGL). */}
      <TooltipOverlay
        hoveredArc={hoveredArc}
        hoveredPoint={hoveredPoint}
        hasSelectedRoute={!!selectedRoute}
        routes={routes}
      />

      {/* Selected route panel */}
      <AnimatePresence>
        {selectedRoute && (
          <RouteDetailPanel
            key={selectedRoute.id}
            route={selectedRoute}
            onClose={() => setSelectedRoute(null)}
          />
        )}
      </AnimatePresence>
    </div>
  );
}
