type WsDotProps = {
  status: "connecting" | "connected" | "disconnected";
  pulse?: boolean;
};

export function WsDot({ status, pulse = true }: WsDotProps) {
  const color =
    status === "connected"
      ? "var(--color-ok)"
      : status === "connecting"
        ? "var(--color-warn)"
        : "var(--color-critical)";

  return (
    <span
      aria-label={`WebSocket ${status}`}
      className={status === "connected" && pulse ? "pulse-ok" : ""}
      style={{
        width: 6,
        height: 6,
        borderRadius: 6,
        background: color,
        display: "inline-block",
        flexShrink: 0,
      }}
    />
  );
}
