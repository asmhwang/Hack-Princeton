"use client";

import { useEffect } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { useWarRoomStore } from "@/lib/store";
import { queryKeys } from "@/lib/query-keys";
import { wsEventSchema, type WsEvent } from "@/types/schemas";

const WS_BASE_URL =
  process.env.NEXT_PUBLIC_WS_URL ??
  `${process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000"}`.replace(/^http/, "ws");

type EventHandler = (event: WsEvent) => void;

export class WarRoomSocket {
  private socket: WebSocket | null = null;
  private reconnectAttempt = 0;
  private closedByClient = false;

  constructor(
    private readonly onEvent: EventHandler,
    private readonly onStatus: (status: "connecting" | "connected" | "disconnected") => void,
  ) {}

  connect() {
    if (this.socket?.readyState === WebSocket.OPEN || this.socket?.readyState === WebSocket.CONNECTING) {
      return;
    }

    this.closedByClient = false;
    this.onStatus("connecting");
    this.socket = new WebSocket(`${WS_BASE_URL}/ws/updates`);

    this.socket.onopen = () => {
      this.reconnectAttempt = 0;
      this.onStatus("connected");
    };

    this.socket.onmessage = (message) => {
      const parsed = wsEventSchema.safeParse(JSON.parse(message.data));
      if (parsed.success) {
        this.onEvent(parsed.data);
      }
    };

    this.socket.onclose = () => {
      this.onStatus("disconnected");
      if (!this.closedByClient) {
        this.scheduleReconnect();
      }
    };

    this.socket.onerror = () => {
      this.socket?.close();
    };
  }

  close() {
    this.closedByClient = true;
    this.socket?.close();
    this.socket = null;
  }

  private scheduleReconnect() {
    const delay = Math.min(20_000, 500 * 2 ** this.reconnectAttempt);
    this.reconnectAttempt += 1;
    window.setTimeout(() => this.connect(), delay);
  }
}

export function useLiveUpdates() {
  const queryClient = useQueryClient();

  useEffect(() => {
    const socket = new WarRoomSocket(
      (event) => {
        useWarRoomStore.getState().receiveWsEvent(event);
        if (event.channel === "new_disruption") {
          void queryClient.invalidateQueries({ queryKey: queryKeys.disruptions() });
        }
        if (event.channel === "new_signal") {
          void queryClient.invalidateQueries({ queryKey: queryKeys.signals });
        }
        if (event.channel === "new_impact" || event.channel === "new_mitigation") {
          void queryClient.invalidateQueries();
        }
        if (event.channel === "new_approval") {
          void queryClient.invalidateQueries({ queryKey: queryKeys.exposure });
          void queryClient.invalidateQueries({ queryKey: queryKeys.activity });
        }
      },
      (status) => useWarRoomStore.getState().setConnectionStatus(status),
    );

    socket.connect();
    return () => socket.close();
  }, [queryClient]);
}
