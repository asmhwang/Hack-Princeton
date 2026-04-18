"use client";

import dynamic from "next/dynamic";
import type { AffectedShipment, Disruption } from "@/types/schemas";

const WorldMap = dynamic(() => import("@/components/map/WorldMap").then((mod) => mod.WorldMap), {
  ssr: false,
  loading: () => <div className="h-80 animate-pulse rounded bg-[var(--color-surface)]" />,
});

type WorldMapPanelProps = {
  disruption: Disruption | null;
  shipments: AffectedShipment[];
};

export function WorldMapPanel(props: WorldMapPanelProps) {
  return <WorldMap {...props} />;
}
