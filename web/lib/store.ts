"use client";

import { create } from "zustand";
import type { ActivityItem, WsEvent } from "@/types/schemas";

type ConnectionStatus = "connecting" | "connected" | "disconnected";

type WarRoomState = {
  selectedDisruptionId: string | null;
  drawerOpen: boolean;
  activityFeed: ActivityItem[];
  simulateInFlight: boolean;
  connectionStatus: ConnectionStatus;
  lastEvent: WsEvent | null;
  setSelectedDisruptionId: (id: string | null) => void;
  setDrawerOpen: (open: boolean) => void;
  setSimulateInFlight: (inFlight: boolean) => void;
  setConnectionStatus: (status: ConnectionStatus) => void;
  pushActivity: (item: ActivityItem) => void;
  receiveWsEvent: (event: WsEvent) => void;
};

function activityFromEvent(event: WsEvent): ActivityItem {
  const timestamp = new Date().toISOString();

  switch (event.channel) {
    case "new_signal":
      return {
        id: `activity-${event.channel}-${event.payload.id}`,
        agent: "Scout",
        message: `Captured ${event.payload.source_category} signal ${event.payload.id.slice(0, 8)}`,
        created_at: timestamp,
        severity: "info",
      };
    case "new_disruption":
      return {
        id: `activity-${event.channel}-${event.payload.id}`,
        agent: "Scout",
        message: `Promoted disruption ${event.payload.id.slice(0, 8)} at severity ${event.payload.severity}`,
        created_at: timestamp,
        severity: event.payload.severity >= 4 ? "critical" : "warning",
      };
    case "new_impact":
      return {
        id: `activity-${event.channel}-${event.payload.id}`,
        agent: "Analyst",
        message: `Published impact report ${event.payload.id.slice(0, 8)}`,
        created_at: timestamp,
        severity: "warning",
      };
    case "new_mitigation":
      return {
        id: `activity-${event.channel}-${event.payload.id}`,
        agent: "Strategist",
        message: `Drafted mitigation ${event.payload.id.slice(0, 8)}`,
        created_at: timestamp,
        severity: "info",
      };
    case "new_approval":
      return {
        id: `activity-${event.channel}-${event.payload.id}`,
        agent: "System",
        message: `Approved mitigation ${event.payload.mitigation_id.slice(0, 8)}`,
        created_at: timestamp,
        severity: "success",
      };
  }
}

export const useWarRoomStore = create<WarRoomState>((set) => ({
  selectedDisruptionId: null,
  drawerOpen: false,
  activityFeed: [],
  simulateInFlight: false,
  connectionStatus: "disconnected",
  lastEvent: null,
  setSelectedDisruptionId: (id) => set({ selectedDisruptionId: id }),
  setDrawerOpen: (open) => set({ drawerOpen: open }),
  setSimulateInFlight: (inFlight) => set({ simulateInFlight: inFlight }),
  setConnectionStatus: (status) => set({ connectionStatus: status }),
  pushActivity: (item) =>
    set((state) => ({
      activityFeed: [item, ...state.activityFeed].slice(0, 50),
    })),
  receiveWsEvent: (event) =>
    set((state) => ({
      lastEvent: event,
      activityFeed: [activityFromEvent(event), ...state.activityFeed].slice(0, 50),
    })),
}));
