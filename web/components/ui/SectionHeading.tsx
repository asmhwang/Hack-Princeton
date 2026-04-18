type SectionHeadingProps = Readonly<{
  title: string;
  count?: number | null;
  meta?: string;
}>;

export function SectionHeading({ title, count, meta }: SectionHeadingProps) {
  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        marginBottom: 10,
      }}
    >
      <div style={{ display: "flex", alignItems: "baseline", gap: 8 }}>
        <h3
          style={{
            margin: 0,
            fontSize: 12,
            fontWeight: 500,
            textTransform: "uppercase",
            letterSpacing: "0.08em",
            color: "var(--color-text)",
          }}
        >
          {title}
        </h3>
        {count !== null && count !== undefined && (
          <span
            className="tnum"
            style={{ fontSize: 11, color: "var(--color-text-subtle)", fontFamily: "var(--font-mono)" }}
          >
            {count}
          </span>
        )}
      </div>
      {meta && <span style={{ fontSize: 11, color: "var(--color-text-subtle)" }}>{meta}</span>}
    </div>
  );
}
