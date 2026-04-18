import type { AffectedShipment } from "@/types/schemas";

export type RouteStatus = "good" | "watch" | "blocked";
export type RouteMode = "ocean" | "air" | "rail" | "truck";

export type AlternativeRoute = {
  id: string;
  label: string;                    // short human name, e.g. "Cape of Good Hope bypass"
  mode: RouteMode;
  waypoints: [number, number][];    // [lat, lng] polyline, origin → ... → destination
  extra_cost_usd: number;           // signed delta vs blocked primary
  time_delta_days: number;          // signed delta vs blocked primary
  confidence_pct: number;           // 0–100
  reason: string;                   // one-liner tradeoff
};

export type GlobeRoute = {
  id: string;
  origin: string;
  destination: string;
  from: [number, number]; // [lat, lng]
  to: [number, number];
  status: RouteStatus;
  mode: RouteMode;
  exposure: string;
  transit_days: number;
  carrier: string;
  recommendation: string;
  reason: string;
  alternatives?: AlternativeRoute[];
};

export const demoRoutes: GlobeRoute[] = [
  {
    id: "RTE-SZX-LAX",
    origin: "Shenzhen",
    destination: "Los Angeles",
    from: [22.5431, 114.0579],
    to: [33.7406, -118.2717],
    status: "good",
    mode: "ocean",
    exposure: "1280000",
    transit_days: 14,
    carrier: "COSCO",
    recommendation: "Keep ocean route active.",
    reason: "Carrier advisories are normal and destination capacity is available.",
  },
  {
    id: "RTE-BUS-SEA",
    origin: "Busan",
    destination: "Seattle",
    from: [35.1796, 129.0756],
    to: [47.6061, -122.3328],
    status: "watch",
    mode: "ocean",
    exposure: "940000",
    transit_days: 11,
    carrier: "HMM",
    recommendation: "Prepare alternate berth at Vancouver if dwell time rises above 48h.",
    reason: "Port labor noise is elevated, but current vessel schedules are still moving.",
  },
  {
    id: "RTE-SHA-RTM",
    origin: "Shanghai",
    destination: "Rotterdam",
    from: [31.2304, 121.4737],
    to: [51.9244, 4.4777],
    status: "blocked",
    mode: "ocean",
    exposure: "2260000",
    transit_days: 28,
    carrier: "Maersk",
    recommendation: "Reroute via Singapore and rail from Hamburg for priority SKUs.",
    reason: "Route crosses Red Sea advisory region — SLA breach risk is high.",
    alternatives: [
      {
        id: "ALT-SHA-RTM-COGH",
        label: "Cape of Good Hope bypass",
        mode: "ocean",
        waypoints: [
          [31.2304, 121.4737],  // Shanghai
          [1.3521, 103.8198],   // Singapore
          [-33.9249, 18.4241],  // Cape Town
          [51.9244, 4.4777],    // Rotterdam
        ],
        extra_cost_usd: 420_000,
        time_delta_days: 12,
        confidence_pct: 92,
        reason: "Bypasses Red Sea advisory; carriers already shifted.",
      },
      {
        id: "ALT-SHA-RTM-TSR",
        label: "Trans-Siberian rail via Hamburg",
        mode: "rail",
        waypoints: [
          [31.2304, 121.4737],  // Shanghai
          [43.1332, 131.9113],  // Vladivostok
          [55.7558, 37.6173],   // Moscow
          [53.5753, 10.0153],   // Hamburg
          [51.9244, 4.4777],    // Rotterdam
        ],
        extra_cost_usd: 180_000,
        time_delta_days: 7,
        confidence_pct: 74,
        reason: "Avoids maritime chokepoints; Kazakh permit backlog ±3d.",
      },
    ],
  },
  {
    id: "RTE-MAA-FRA",
    origin: "Chennai",
    destination: "Frankfurt",
    from: [13.0827, 80.2707],
    to: [50.1109, 8.6821],
    status: "good",
    mode: "air",
    exposure: "510000",
    transit_days: 2,
    carrier: "Lufthansa Cargo",
    recommendation: "Keep air freight allocation unchanged.",
    reason: "Weather and customs signals are within normal range.",
  },
  {
    id: "RTE-HKG-AMS",
    origin: "Hong Kong",
    destination: "Amsterdam",
    from: [22.3193, 114.1694],
    to: [52.3676, 4.9041],
    status: "watch",
    mode: "air",
    exposure: "760000",
    transit_days: 1,
    carrier: "Cathay Cargo",
    recommendation: "Hold two days of safety stock against customs delays.",
    reason: "Policy signal may affect electronics documentation checks.",
  },
  {
    id: "RTE-TPE-ORD",
    origin: "Taipei",
    destination: "Chicago",
    from: [25.033, 121.5654],
    to: [41.8781, -87.6298],
    status: "blocked",
    mode: "air",
    exposure: "1840000",
    transit_days: 1,
    carrier: "EVA Air Cargo",
    recommendation: "Activate backup ocean routing via Vancouver and rail.",
    reason: "Airspace congestion + customs hold on semiconductor components.",
    alternatives: [
      {
        id: "ALT-TPE-ORD-VANRAIL",
        label: "Ocean to Vancouver + rail",
        mode: "ocean",
        waypoints: [
          [25.033, 121.5654],   // Taipei
          [49.2827, -123.1207], // Vancouver
          [41.8781, -87.6298],  // Chicago
        ],
        extra_cost_usd: 120_000,
        time_delta_days: 18,
        confidence_pct: 88,
        reason: "Clears airspace + customs bottleneck; doubles transit.",
      },
      {
        id: "ALT-TPE-ORD-ANC",
        label: "Air via Anchorage",
        mode: "air",
        waypoints: [
          [25.033, 121.5654],   // Taipei
          [61.2181, -149.9003], // Anchorage
          [41.8781, -87.6298],  // Chicago
        ],
        extra_cost_usd: 320_000,
        time_delta_days: 0.5,
        confidence_pct: 71,
        reason: "Skirts congested Pacific corridors; keeps SLA window.",
      },
    ],
  },
  {
    id: "RTE-PVG-HBG",
    origin: "Shanghai",
    destination: "Hamburg",
    from: [31.1443, 121.8083],
    to: [53.5753, 10.0153],
    status: "watch",
    mode: "rail",
    exposure: "620000",
    transit_days: 18,
    carrier: "UTLC ERA",
    recommendation: "Monitor Trans-Siberian routing; prepare ocean fallback.",
    reason: "Transit permit delays in Kazakhstan adding 3–5 days.",
  },
  {
    id: "RTE-LAX-MEX",
    origin: "Los Angeles",
    destination: "Mexico City",
    from: [33.7406, -118.2717],
    to: [19.4326, -99.1332],
    status: "good",
    mode: "truck",
    exposure: "310000",
    transit_days: 3,
    carrier: "XPO Logistics",
    recommendation: "No action required.",
    reason: "Cross-border clearance times are within SLA.",
  },
];

const MODE_COLORS: Record<RouteMode, string> = {
  ocean: "rgba(99,179,237,",
  air: "rgba(167,139,250,",
  rail: "rgba(251,191,36,",
  truck: "rgba(110,231,183,",
};

export function arcColorForRoute(route: GlobeRoute): [string, string] {
  const base = MODE_COLORS[route.mode];
  // Start alpha raised from 0.04 → 0.30 so the origin half of the arc is visible
  // instead of fading to near-transparent. Ocean (blue) and truck (mint) were
  // particularly hard to read against the night-earth texture at the old levels.
  if (route.status === "blocked") return [`${base}0.14)`, "rgba(229,72,77,0.95)"];
  if (route.status === "watch") return [`${base}0.35)`, `${base}0.95)`];
  return [`${base}0.30)`, `${base}0.88)`];
}

export function routesFromShipments(shipments: AffectedShipment[]): GlobeRoute[] {
  const routes = shipments.flatMap((shipment): GlobeRoute[] => {
    if (
      shipment.origin_lat == null || shipment.origin_lng == null ||
      shipment.destination_lat == null || shipment.destination_lng == null
    ) return [];

    const status: RouteStatus =
      shipment.days_to_sla_breach != null && shipment.days_to_sla_breach < 2
        ? "blocked"
        : "watch";

    return [{
      id: shipment.shipment_id,
      origin: shipment.origin,
      destination: shipment.destination,
      from: [shipment.origin_lat, shipment.origin_lng],
      to: [shipment.destination_lat, shipment.destination_lng],
      status,
      mode: "ocean",
      exposure: shipment.exposure,
      transit_days: shipment.days_to_sla_breach ?? 14,
      carrier: "Unknown",
      recommendation:
        status === "blocked"
          ? "Approve reroute or expedite option for this shipment group."
          : "Keep route under watch and refresh ETA after next agent cycle.",
      reason:
        status === "blocked"
          ? "SLA breach window is inside two days."
          : "Shipment is affected but has remaining schedule buffer.",
    }];
  });

  return routes.length > 0 ? routes : demoRoutes;
}
