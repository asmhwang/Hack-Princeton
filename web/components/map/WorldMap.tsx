"use client";

import { CircleMarker, MapContainer, Polyline, TileLayer, Tooltip } from "react-leaflet";
import type { AffectedShipment, Disruption } from "@/types/schemas";
import { categoryTokens } from "@/lib/design-tokens";

type WorldMapProps = {
  disruption: Disruption | null;
  shipments: AffectedShipment[];
};

function shipmentLines(shipments: AffectedShipment[]) {
  return shipments.flatMap((shipment) => {
    if (
      shipment.origin_lat === undefined ||
      shipment.origin_lat === null ||
      shipment.origin_lng === undefined ||
      shipment.origin_lng === null ||
      shipment.destination_lat === undefined ||
      shipment.destination_lat === null ||
      shipment.destination_lng === undefined ||
      shipment.destination_lng === null
    ) {
      return [];
    }

    return [
      {
        id: shipment.shipment_id,
        from: [shipment.origin_lat, shipment.origin_lng] as [number, number],
        to: [shipment.destination_lat, shipment.destination_lng] as [number, number],
      },
    ];
  });
}

export function WorldMap({ disruption, shipments }: WorldMapProps) {
  const center: [number, number] =
    disruption?.lat !== undefined && disruption.lat !== null && disruption.lng !== undefined && disruption.lng !== null
      ? [disruption.lat, disruption.lng]
      : [22, 103];
  const token = disruption ? categoryTokens[disruption.category] : null;
  const lines = shipmentLines(shipments);

  return (
    <div className="h-80 overflow-hidden rounded border border-[var(--color-border)]">
      <MapContainer center={center} zoom={disruption?.lat ? 4 : 2} scrollWheelZoom={false} className="h-full">
        <TileLayer
          attribution="&copy; OpenStreetMap"
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />
        {disruption ? (
          <CircleMarker
            center={center}
            radius={9}
            pathOptions={{
              color: token?.color ?? "#c2a46d",
              fillColor: token?.color ?? "#c2a46d",
              fillOpacity: 0.5,
              weight: 1,
            }}
          >
            <Tooltip>{disruption.title}</Tooltip>
          </CircleMarker>
        ) : null}
        {lines.map((line) => (
          <Polyline
            key={line.id}
            positions={[line.from, line.to]}
            pathOptions={{ color: "#8a8a8a", weight: 1, opacity: 0.7 }}
          />
        ))}
      </MapContainer>
    </div>
  );
}
