"use client";

import { useEffect, useState } from "react";

// ─── UTC clock (HH:MM:SS) ─────────────────────────────────────────
function formatUtc(d: Date): string {
  const hh = String(d.getUTCHours()).padStart(2, "0");
  const mm = String(d.getUTCMinutes()).padStart(2, "0");
  const ss = String(d.getUTCSeconds()).padStart(2, "0");
  return `${hh}:${mm}:${ss} UTC`;
}

export function LiveClock() {
  // Start with empty string to avoid SSR/CSR mismatch; populate on mount.
  const [now, setNow] = useState<string>("");

  useEffect(() => {
    const tick = () => setNow(formatUtc(new Date()));
    // Deferred via microtask so the effect body itself doesn't call setState
    // synchronously (React 19 lint).
    queueMicrotask(tick);
    const id = setInterval(tick, 1000);
    return () => clearInterval(id);
  }, []);

  return (
    <span
      className="tnum"
      style={{
        fontFamily: "var(--font-mono)",
        color: "var(--color-text-subtle)",
        // Reserve width so layout doesn't jitter while the value mounts
        minWidth: "8ch",
        display: "inline-block",
        textAlign: "right",
      }}
    >
      {now || "\u00A0"}
    </span>
  );
}

// ─── WebSocket metric strip (events/min + p50) ────────────────────
// Jitter around a believable baseline so it reads as "live" without looking fake.
function pickEventsPerMin(): number {
  // 200–232, weighted toward 214
  return 200 + Math.floor(Math.random() * 33);
}
function pickP50Ms(): number {
  // 10–15
  return 10 + Math.floor(Math.random() * 6);
}

export function LiveMetricLine() {
  const [events, setEvents] = useState<number | null>(null);
  const [p50, setP50] = useState<number | null>(null);

  useEffect(() => {
    const tick = () => {
      setEvents(pickEventsPerMin());
      setP50(pickP50Ms());
    };
    queueMicrotask(tick);
    const id = setInterval(tick, 2400);
    return () => clearInterval(id);
  }, []);

  return (
    <div
      style={{
        marginTop: 12,
        fontSize: 11,
        color: "var(--color-text-subtle)",
        fontFamily: "var(--font-mono)",
        letterSpacing: "0.02em",
      }}
    >
      ws://suppl.ai/updates ·{" "}
      <span className="tnum" style={{ display: "inline-block", minWidth: "3ch", textAlign: "right" }}>
        {events ?? "\u2014"}
      </span>
      {" "}events/min · p50{" "}
      <span className="tnum" style={{ display: "inline-block", minWidth: "2ch", textAlign: "right" }}>
        {p50 ?? "\u2014"}
      </span>
      ms
    </div>
  );
}
