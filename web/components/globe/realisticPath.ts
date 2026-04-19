// Per-mode path geometry for the globe.
//
// Ocean lanes run through searoute-ts — a precomputed maritime network that
// follows real shipping lanes (Suez, Panama, etc.) so arcs stay on water and
// bend around continents instead of cutting across them.
//
// Rail/truck lanes use a sampled great-circle at surface altitude. The user
// accepted the caveat that these won't hug roads; they just need to look
// plausible on land. For the hackathon demo the curated rail/truck lanes
// (Shanghai-Hamburg, LA-Mexico City) stay over land naturally.
//
// Air routes keep the existing arcsData rendering upstream — they're not
// produced here.

import { seaRoute } from "searoute-ts";
import type { GlobeRoute } from "./routes";

export type LatLng = [number, number]; // [lat, lng]

const GREAT_CIRCLE_SEGMENTS = 64;

// searoute-ts logs `nearestLineIndex` on every call — a leftover debug print
// in the published lib. Filter those out once on first use so they don't
// spam the browser console (or the Next build output during SSG).
let _consoleSilenced = false;
function silenceSearouteLogs(): void {
  if (_consoleSilenced) return;
  _consoleSilenced = true;
  const originalLog = console.log;
  console.log = (...args: unknown[]) => {
    if (args.length === 1 && typeof args[0] === "number") return;
    originalLog.apply(console, args);
  };
}

function toRadians(deg: number): number {
  return (deg * Math.PI) / 180;
}

function toDegrees(rad: number): number {
  return (rad * 180) / Math.PI;
}

// Great-circle slerp between two lat/lng points. Returns `segments+1` points
// including both endpoints. Degenerates gracefully when the two points
// coincide.
function greatCirclePoints(
  from: LatLng,
  to: LatLng,
  segments: number = GREAT_CIRCLE_SEGMENTS,
): LatLng[] {
  const phi1 = toRadians(from[0]);
  const lam1 = toRadians(from[1]);
  const phi2 = toRadians(to[0]);
  const lam2 = toRadians(to[1]);

  const cosPhi1 = Math.cos(phi1);
  const cosPhi2 = Math.cos(phi2);
  const sinPhi1 = Math.sin(phi1);
  const sinPhi2 = Math.sin(phi2);

  const x1 = cosPhi1 * Math.cos(lam1);
  const y1 = cosPhi1 * Math.sin(lam1);
  const z1 = sinPhi1;
  const x2 = cosPhi2 * Math.cos(lam2);
  const y2 = cosPhi2 * Math.sin(lam2);
  const z2 = sinPhi2;

  const dot = Math.max(-1, Math.min(1, x1 * x2 + y1 * y2 + z1 * z2));
  const omega = Math.acos(dot);
  const sinOmega = Math.sin(omega);

  const out: LatLng[] = [];
  for (let i = 0; i <= segments; i++) {
    const t = i / segments;
    let x: number, y: number, z: number;
    if (sinOmega < 1e-9) {
      x = x1;
      y = y1;
      z = z1;
    } else {
      const a = Math.sin((1 - t) * omega) / sinOmega;
      const b = Math.sin(t * omega) / sinOmega;
      x = a * x1 + b * x2;
      y = a * y1 + b * y2;
      z = a * z1 + b * z2;
    }
    const lat = toDegrees(Math.atan2(z, Math.sqrt(x * x + y * y)));
    const lng = toDegrees(Math.atan2(y, x));
    out.push([lat, lng]);
  }
  return out;
}

type GeoJsonPoint = {
  type: "Feature";
  properties: Record<string, never>;
  geometry: { type: "Point"; coordinates: [number, number] };
};

function toGeoJsonPoint(latLng: LatLng): GeoJsonPoint {
  return {
    type: "Feature",
    properties: {},
    geometry: { type: "Point", coordinates: [latLng[1], latLng[0]] },
  };
}

// Compute an ocean path via the searoute maritime network. Returns null if
// the library throws (e.g. coordinates too far inland / not reachable); the
// caller should fall back to great-circle in that case.
function oceanPath(from: LatLng, to: LatLng): LatLng[] | null {
  silenceSearouteLogs();
  try {
    const origin = toGeoJsonPoint(from);
    const destination = toGeoJsonPoint(to);
    const result = seaRoute(origin, destination);
    const coords = result?.geometry?.coordinates;
    if (!Array.isArray(coords) || coords.length < 2) return null;
    return coords.map(([lng, lat]) => [lat, lng] as LatLng);
  } catch {
    return null;
  }
}

// Path cache: keyed by route id + mode + endpoints. Ocean routing in
// particular is expensive (Dijkstra over ~tens of thousands of edges), so
// caching is essential — the globe re-renders many times per minute.
const pathCache = new Map<string, LatLng[]>();

function cacheKey(route: GlobeRoute): string {
  return `${route.mode}:${route.from[0]},${route.from[1]}:${route.to[0]},${route.to[1]}`;
}

// Compute the surface path for a non-air route. Ocean routes follow real
// shipping lanes; rail/truck use a sampled great-circle.
export function surfacePathFor(route: GlobeRoute): LatLng[] {
  const key = cacheKey(route);
  const cached = pathCache.get(key);
  if (cached) return cached;

  let path: LatLng[];
  if (route.mode === "ocean") {
    path = oceanPath(route.from, route.to) ?? greatCirclePoints(route.from, route.to);
  } else {
    // rail | truck — great-circle at surface altitude.
    path = greatCirclePoints(route.from, route.to, 48);
  }

  pathCache.set(key, path);
  return path;
}

export { greatCirclePoints };
