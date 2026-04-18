type SqlPreviewProps = Readonly<{ sql: string; meta?: string }>;

function highlightSql(sql: string): string {
  const escape = (s: string) =>
    s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  let out = escape(sql);
  const keywords = [
    "SELECT", "FROM", "LEFT JOIN", "INNER JOIN", "JOIN", "ON",
    "WHERE", "AND", "OR", "IN", "ORDER BY", "GROUP BY", "AS",
    "DESC", "ASC", "INTERVAL", "BETWEEN", "LIMIT",
  ];
  for (const k of keywords) {
    out = out.replace(
      new RegExp(`\\b${k}\\b`, "g"),
      `<span style="color:var(--color-info);font-weight:500">${k}</span>`,
    );
  }
  out = out.replace(/'[^']*'/g, (m) => `<span style="color:var(--color-ok)">${m}</span>`);
  out = out.replace(
    /\b(CURRENT_DATE|CURRENT_TIMESTAMP|DATE_DIFF|ST_INTERSECTS)\b/g,
    `<span style="color:var(--color-cat-news)">$1</span>`,
  );
  out = out.replace(/@\w+/g, (m) => `<span style="color:var(--color-warn)">${m}</span>`);
  return out;
}

export function SqlPreview({ sql, meta = "impact.sql · 412ms" }: SqlPreviewProps) {
  return (
    <div
      style={{
        border: "1px solid var(--color-border)",
        borderRadius: 5,
        background: "var(--color-bg)",
        overflow: "hidden",
      }}
    >
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          padding: "6px 12px",
          borderBottom: "1px solid var(--color-border)",
          background: "var(--color-surface)",
          fontFamily: "var(--font-mono)",
          fontSize: 10,
          color: "var(--color-text-subtle)",
          textTransform: "uppercase",
          letterSpacing: "0.06em",
        }}
      >
        <span>{meta}</span>
      </div>
      <pre
        style={{
          margin: 0,
          padding: 14,
          maxHeight: 200,
          overflow: "auto",
          fontFamily: "var(--font-mono)",
          fontSize: 11.5,
          lineHeight: "18px",
          color: "var(--color-text-muted)",
        }}
      >
        {/* SQL is from our trusted backend — highlight is regex-based on escaped HTML */}
        <code dangerouslySetInnerHTML={{ __html: highlightSql(sql) }} />
      </pre>
    </div>
  );
}
