import Link from "next/link";
import { LiveClock, LiveMetricLine } from "@/components/landing/LiveIndicators";

export const metadata = {
  title: "suppl.ai — Supply chain war room",
  description:
    "An autonomous three-agent swarm watches global supply signals, scores exposure, and drafts mitigations for one-click approval.",
};

const BORDER = "1px solid var(--color-border)";
const BORDER_STRONG = "1px solid var(--color-border-strong)";
const KICKER: React.CSSProperties = {
  fontSize: 10,
  fontWeight: 500,
  color: "var(--color-text-subtle)",
  textTransform: "uppercase",
  letterSpacing: "0.14em",
  fontFamily: "var(--font-mono)",
};
const SECTION_LABEL: React.CSSProperties = {
  fontSize: 11,
  fontWeight: 500,
  color: "var(--color-text-subtle)",
  textTransform: "uppercase",
  letterSpacing: "0.12em",
  fontFamily: "var(--font-mono)",
};

type StatusCell = { label: string; value: string; color?: string; mono?: boolean; pulse?: boolean };

const heroStatus: StatusCell[] = [
  { label: "Status", value: "MONITORING", color: "var(--color-warn)", mono: true, pulse: true },
  { label: "Active disruptions", value: "3", color: "var(--color-critical)" },
  { label: "Exposure at risk", value: "$48.2M", mono: true },
  { label: "High severity", value: "1", color: "var(--color-critical)" },
  { label: "Monitoring", value: "2", color: "var(--color-warn)" },
  { label: "Agents", value: "3 / 3", color: "var(--color-ok)" },
];

const agents = [
  {
    kicker: "SCOUT",
    kickerColor: "var(--color-cat-news)",
    title: "Scout",
    body: "Five parallel sources, each on its own cadence. Classifies, dedupes by region + keyword hash, fuses related low-severity events into a single disruption.",
    lines: [
      ["NEWS", "60s"],
      ["WEATHER", "5m"],
      ["POLICY", "15m"],
      ["LOGISTICS", "10m"],
      ["MACRO", "30m"],
    ],
  },
  {
    kicker: "ANALYST",
    kickerColor: "var(--color-cat-logistics)",
    title: "Analyst",
    body: "Runs a Gemini function-calling loop across seven parameterized read-only tools. Every call returns rows plus the synthesized SQL — stored on the impact report as a reasoning trace.",
    lines: [
      ["TOOLS", "7 parameterized"],
      ["MUTATIONS", "zero"],
      ["TRACE", "stored"],
      ["FALLBACK", "rules-based"],
      ["MODEL", "gemini-2.5-flash"],
    ],
  },
  {
    kicker: "STRATEGIST",
    kickerColor: "var(--color-cat-macro)",
    title: "Strategist",
    body: "Drafts mitigations through OpenClaw: reroute shipments, alternate suppliers, customer drafts. Nothing sent — draft_communications.sent_at stays NULL.",
    lines: [
      ["OPENCLAW", "exclusive"],
      ["SMTP IMPORTS", "zero"],
      ["AUDIT LOG", "append-only"],
      ["STATE SNAPSHOT", "JSONB"],
      ["APPROVAL", "one-click"],
    ],
  },
];

type SignalRow = {
  tag: string;
  color: string;
  bg: string;
  title: string;
  region: string;
  time: string;
  severity: string;
};

const signalRows: SignalRow[] = [
  {
    tag: "Weather",
    color: "var(--color-cat-weather)",
    bg: "rgba(156, 163, 175, 0.10)",
    title: "Typhoon Kaia intensifies to Category 4 near Vietnam",
    region: "HCM Port · South China Sea",
    time: "6m",
    severity: "S4",
  },
  {
    tag: "Policy",
    color: "var(--color-cat-policy)",
    bg: "rgba(184, 163, 143, 0.10)",
    title: "Red Sea shipping advisory extended through Q2",
    region: "Bab-el-Mandeb",
    time: "24m",
    severity: "S3",
  },
  {
    tag: "Logistics",
    color: "var(--color-cat-logistics)",
    bg: "rgba(194, 164, 109, 0.10)",
    title: "ILWU votes to authorize strike at LA / Long Beach",
    region: "Port of Los Angeles",
    time: "1h",
    severity: "S3",
  },
  {
    tag: "News",
    color: "var(--color-cat-news)",
    bg: "rgba(143, 174, 130, 0.10)",
    title: "Foxconn Zhengzhou reports Q2 staffing shortfall",
    region: "Zhengzhou",
    time: "2h",
    severity: "S2",
  },
  {
    tag: "Macro",
    color: "var(--color-cat-macro)",
    bg: "rgba(189, 141, 107, 0.10)",
    title: "PBOC cuts 7-day reverse repo 10bps",
    region: "China",
    time: "4h",
    severity: "S1",
  },
];

const workflow = [
  { step: "01", label: "Signal detected", sub: "Scout · LISTEN/NOTIFY" },
  { step: "02", label: "Impact assessed", sub: "Analyst · tool loop" },
  { step: "03", label: "Mitigation drafted", sub: "Strategist · OpenClaw" },
  { step: "04", label: "Human approved", sub: "Operator · one click" },
];

const principles = [
  {
    index: "01",
    title: "Postgres is the bus.",
    body: "Agents communicate only via LISTEN/NOTIFY on five channels. No RPC, no queues, no drift — the schema is the contract.",
  },
  {
    index: "02",
    title: "No free-form SQL. Ever.",
    body: "The Analyst picks from seven parameterized read-only tools — no mutation path exists in the LLM surface. Any synthesized SQL string still passes through a token-level validator before execution. Defense in depth; twenty-two tests.",
  },
  {
    index: "03",
    title: "Mutations flow through OpenClaw.",
    body: "Approvals flip shipment status, write state snapshots to JSONB, and log provenance. The Eragon rubric demands it — and audit demands it louder.",
  },
  {
    index: "04",
    title: "No chatbots. No spinners.",
    body: "Skeleton screens, tabular numerals, decisions you can close in one click. The surface shouldn't move faster than the data underneath it.",
  },
];

function HeroStatusGrid() {
  return (
    <div
      style={{
        display: "grid",
        gridTemplateColumns: "repeat(2, 1fr)",
        gap: 1,
        background: "var(--color-border)",
        border: BORDER,
        borderRadius: 5,
        overflow: "hidden",
      }}
    >
      {heroStatus.map(({ label, value, color, mono, pulse }) => (
        <div
          key={label}
          style={{
            background: "var(--color-surface)",
            padding: "16px 18px",
            display: "flex",
            flexDirection: "column",
            gap: 6,
          }}
        >
          <div
            style={{
              fontSize: 10,
              color: "var(--color-text-subtle)",
              textTransform: "uppercase",
              letterSpacing: "0.08em",
              display: "flex",
              alignItems: "center",
              gap: 8,
            }}
          >
            {pulse ? (
              <span
                className="pulse-ok"
                style={{
                  width: 6,
                  height: 6,
                  borderRadius: 6,
                  background: color ?? "var(--color-ok)",
                  display: "inline-block",
                }}
              />
            ) : null}
            {label}
          </div>
          <div
            className="tnum"
            style={{
              fontSize: 18,
              fontWeight: 600,
              color: color ?? "var(--color-text)",
              letterSpacing: "-0.01em",
              fontFamily: mono ? "var(--font-mono)" : undefined,
            }}
          >
            {value}
          </div>
        </div>
      ))}
    </div>
  );
}

function Nav() {
  return (
    <header
      style={{
        height: 56,
        borderBottom: BORDER,
        position: "sticky",
        top: 0,
        zIndex: 10,
        background: "var(--color-bg)",
      }}
    >
      <div
        style={{
          maxWidth: 1240,
          margin: "0 auto",
          height: "100%",
          padding: "0 24px",
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
          <span style={{ fontSize: 15, fontWeight: 600, letterSpacing: "-0.01em" }}>suppl.ai</span>
          <span style={{ ...KICKER, fontSize: 10 }}>HackPrinceton · Spring &rsquo;26</span>
        </div>
        <nav style={{ display: "flex", alignItems: "center", gap: 20, fontSize: 13 }}>
          <a
            href="#agents"
            style={{ color: "var(--color-text-muted)", textDecoration: "none" }}
          >
            Agents
          </a>
          <a
            href="#signals"
            style={{ color: "var(--color-text-muted)", textDecoration: "none" }}
          >
            Signals
          </a>
          <a
            href="#workflow"
            style={{ color: "var(--color-text-muted)", textDecoration: "none" }}
          >
            Workflow
          </a>
          <Link
            href="/"
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: 6,
              height: 30,
              padding: "0 12px",
              borderRadius: 4,
              border: BORDER_STRONG,
              background: "var(--color-surface-raised)",
              color: "var(--color-text)",
              fontSize: 13,
              fontWeight: 500,
              textDecoration: "none",
            }}
          >
            Open war room
            <span aria-hidden style={{ fontFamily: "var(--font-mono)", fontSize: 12 }}>→</span>
          </Link>
        </nav>
      </div>
    </header>
  );
}

function Hero() {
  return (
    <section style={{ borderBottom: BORDER }}>
      <div
        style={{
          maxWidth: 1240,
          margin: "0 auto",
          padding: "64px 24px 56px",
          display: "grid",
          gridTemplateColumns: "minmax(0, 1.2fr) minmax(0, 1fr)",
          gap: 48,
          alignItems: "start",
        }}
      >
        <div>
          <div style={{ ...KICKER, display: "flex", alignItems: "center", gap: 10, marginBottom: 20 }}>
            <span
              style={{
                width: 6,
                height: 6,
                borderRadius: 6,
                background: "var(--color-info)",
                display: "inline-block",
              }}
            />
            Supply chain · War room
          </div>
          <h1
            style={{
              fontSize: 52,
              lineHeight: 1.05,
              fontWeight: 600,
              letterSpacing: "-0.025em",
              margin: 0,
              color: "var(--color-text)",
              maxWidth: 640,
            }}
          >
            See the shock before it hits your P&amp;L.
          </h1>
          <p
            style={{
              marginTop: 20,
              fontSize: 16,
              lineHeight: 1.6,
              color: "var(--color-text-muted)",
              maxWidth: 560,
            }}
          >
            An autonomous three-agent swarm watches global supply signals, scores exposure against your live
            warehouse, and drafts mitigations for one-click human approval. Not a chatbot &mdash; an operator war
            room.
          </p>
          <div style={{ marginTop: 28, display: "flex", alignItems: "center", gap: 10 }}>
            <Link
              href="/"
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: 8,
                height: 36,
                padding: "0 16px",
                borderRadius: 4,
                border: "1px solid var(--color-info)",
                background: "var(--color-info)",
                color: "#1a1408",
                fontSize: 13,
                fontWeight: 600,
                textDecoration: "none",
              }}
            >
              Open war room
              <span aria-hidden style={{ fontFamily: "var(--font-mono)", fontSize: 12 }}>→</span>
            </Link>
            <a
              href="#workflow"
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: 8,
                height: 36,
                padding: "0 14px",
                borderRadius: 4,
                border: BORDER_STRONG,
                background: "var(--color-surface-raised)",
                color: "var(--color-text)",
                fontSize: 13,
                fontWeight: 500,
                textDecoration: "none",
              }}
            >
              How it works
            </a>
          </div>
          <div
            style={{
              marginTop: 40,
              display: "grid",
              gridTemplateColumns: "repeat(3, auto)",
              gap: 28,
              paddingTop: 20,
              borderTop: BORDER,
              maxWidth: 560,
            }}
          >
            <Meta label="Agents" value="3" sub="Scout · Analyst · Strategist" />
            <Meta label="Signal channels" value="5" sub="pg LISTEN/NOTIFY" />
            <Meta label="Avg decision" value="< 60s" sub="signal to approval" />
          </div>
        </div>
        <div style={{ position: "sticky", top: 80 }}>
          <div style={{ ...SECTION_LABEL, marginBottom: 10, display: "flex", justifyContent: "space-between" }}>
            <span>Live state · demo</span>
            <LiveClock />
          </div>
          <HeroStatusGrid />
          <LiveMetricLine />
        </div>
      </div>
    </section>
  );
}

function Meta({ label, value, sub }: { label: string; value: string; sub: string }) {
  return (
    <div>
      <div style={{ fontSize: 10, color: "var(--color-text-subtle)", textTransform: "uppercase", letterSpacing: "0.08em" }}>
        {label}
      </div>
      <div
        className="tnum"
        style={{
          fontSize: 20,
          fontWeight: 600,
          marginTop: 4,
          letterSpacing: "-0.01em",
          fontFamily: "var(--font-mono)",
        }}
      >
        {value}
      </div>
      <div style={{ fontSize: 11, color: "var(--color-text-muted)", marginTop: 2 }}>{sub}</div>
    </div>
  );
}

function Agents() {
  return (
    <section id="agents" style={{ borderBottom: BORDER }}>
      <div style={{ maxWidth: 1240, margin: "0 auto", padding: "64px 24px" }}>
        <SectionHead
          kicker="01 · The swarm"
          title="Three agents. One bus. No chatter."
          sub="Each agent runs on its own Dedalus VM and speaks only through Postgres. The schema is the contract; reasoning traces are the receipt."
        />
        <div
          style={{
            marginTop: 36,
            display: "grid",
            gridTemplateColumns: "repeat(3, 1fr)",
            gap: 1,
            background: "var(--color-border)",
            border: BORDER,
            borderRadius: 5,
            overflow: "hidden",
          }}
        >
          {agents.map((a) => (
            <div key={a.kicker} style={{ background: "var(--color-surface)", padding: "24px 22px", display: "flex", flexDirection: "column", gap: 14 }}>
              <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                <span style={{ ...KICKER, color: a.kickerColor, letterSpacing: "0.18em" }}>{a.kicker}</span>
                <span style={{ fontFamily: "var(--font-mono)", fontSize: 11, color: "var(--color-text-subtle)" }}>
                  VM · running
                </span>
              </div>
              <h3
                style={{
                  margin: 0,
                  fontSize: 22,
                  fontWeight: 600,
                  letterSpacing: "-0.01em",
                }}
              >
                {a.title}
              </h3>
              <p style={{ margin: 0, fontSize: 13, lineHeight: 1.6, color: "var(--color-text-muted)" }}>
                {a.body}
              </p>
              <div style={{ marginTop: "auto", paddingTop: 14, borderTop: BORDER, display: "flex", flexDirection: "column", gap: 5 }}>
                {a.lines.map(([k, v]) => (
                  <div
                    key={k}
                    style={{
                      display: "flex",
                      justifyContent: "space-between",
                      fontFamily: "var(--font-mono)",
                      fontSize: 11,
                      color: "var(--color-text-subtle)",
                      letterSpacing: "0.02em",
                    }}
                  >
                    <span>{k}</span>
                    <span className="tnum" style={{ color: "var(--color-text-muted)" }}>{v}</span>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

function Signals() {
  return (
    <section id="signals" style={{ borderBottom: BORDER }}>
      <div style={{ maxWidth: 1240, margin: "0 auto", padding: "64px 24px" }}>
        <SectionHead
          kicker="02 · Signal feed"
          title="Five categories. 72-hour dedupe window. Fusion before escalation."
          sub="Low-severity signals related by region and keyword merge into higher-severity disruptions before the Analyst ever sees them."
        />
        <div
          style={{
            marginTop: 36,
            border: BORDER,
            borderRadius: 5,
            overflow: "hidden",
            background: "var(--color-surface)",
          }}
        >
          <div
            style={{
              padding: "10px 16px",
              borderBottom: BORDER,
              display: "grid",
              gridTemplateColumns: "120px 1fr 180px 60px 60px",
              gap: 16,
              ...SECTION_LABEL,
              fontSize: 10,
            }}
          >
            <span>Category</span>
            <span>Signal</span>
            <span>Region</span>
            <span style={{ textAlign: "right" }}>Sev</span>
            <span style={{ textAlign: "right" }}>T</span>
          </div>
          {signalRows.map((row, i) => (
            <div
              key={row.title}
              className="ship-row"
              style={{
                display: "grid",
                gridTemplateColumns: "120px 1fr 180px 60px 60px",
                gap: 16,
                padding: "13px 16px",
                alignItems: "center",
                borderTop: i === 0 ? "none" : BORDER,
                fontSize: 13,
              }}
            >
              <span>
                <span
                  style={{
                    color: row.color,
                    background: row.bg,
                    padding: "3px 8px",
                    borderRadius: 3,
                    fontSize: 10,
                    fontWeight: 500,
                    textTransform: "uppercase",
                    letterSpacing: "0.06em",
                  }}
                >
                  {row.tag}
                </span>
              </span>
              <span style={{ color: "var(--color-text)", fontWeight: 500, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                {row.title}
              </span>
              <span style={{ color: "var(--color-text-subtle)", fontSize: 12 }}>{row.region}</span>
              <span
                className="tnum"
                style={{
                  textAlign: "right",
                  fontFamily: "var(--font-mono)",
                  color: row.severity === "S4" ? "var(--color-critical)" : row.severity === "S3" ? "var(--color-warn)" : "var(--color-text-muted)",
                }}
              >
                {row.severity}
              </span>
              <span
                className="tnum"
                style={{
                  textAlign: "right",
                  fontFamily: "var(--font-mono)",
                  color: "var(--color-text-subtle)",
                  fontSize: 12,
                }}
              >
                {row.time}
              </span>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

function Workflow() {
  return (
    <section id="workflow" style={{ borderBottom: BORDER }}>
      <div style={{ maxWidth: 1240, margin: "0 auto", padding: "64px 24px" }}>
        <SectionHead
          kicker="03 · The loop"
          title="Signal to approval in under a minute."
          sub="Every transition is a pg NOTIFY. Every mutation is audited. Nothing moves without a human at the last step."
        />
        <div
          style={{
            marginTop: 36,
            display: "grid",
            gridTemplateColumns: "repeat(4, 1fr)",
            gap: 1,
            background: "var(--color-border)",
            border: BORDER,
            borderRadius: 5,
            overflow: "hidden",
          }}
        >
          {workflow.map((w, i) => (
            <div
              key={w.step}
              style={{
                background: "var(--color-surface)",
                padding: "22px 20px",
                display: "flex",
                flexDirection: "column",
                gap: 10,
                position: "relative",
              }}
            >
              <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                <span
                  style={{
                    fontFamily: "var(--font-mono)",
                    fontSize: 11,
                    color: "var(--color-text-subtle)",
                    letterSpacing: "0.08em",
                  }}
                >
                  {w.step}
                </span>
                {i < workflow.length - 1 ? (
                  <span
                    aria-hidden
                    style={{
                      fontFamily: "var(--font-mono)",
                      fontSize: 13,
                      color: "var(--color-text-subtle)",
                    }}
                  >
                    →
                  </span>
                ) : (
                  <span
                    aria-hidden
                    style={{
                      width: 6,
                      height: 6,
                      borderRadius: 6,
                      background: "var(--color-ok)",
                      display: "inline-block",
                    }}
                    className="pulse-ok"
                  />
                )}
              </div>
              <div
                style={{
                  fontSize: 16,
                  fontWeight: 600,
                  letterSpacing: "-0.005em",
                }}
              >
                {w.label}
              </div>
              <div style={{ fontSize: 12, color: "var(--color-text-muted)", fontFamily: "var(--font-mono)" }}>
                {w.sub}
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

function Principles() {
  return (
    <section style={{ borderBottom: BORDER }}>
      <div style={{ maxWidth: 1240, margin: "0 auto", padding: "64px 24px" }}>
        <SectionHead
          kicker="04 · Discipline"
          title="Four rules the codebase actually enforces."
          sub="Quality gates in CI. No chatty retries, no hand-wavy prompts, no SMTP imports hiding in a sub-dep."
        />
        <div
          style={{
            marginTop: 36,
            display: "grid",
            gridTemplateColumns: "repeat(2, 1fr)",
            gap: 1,
            background: "var(--color-border)",
            border: BORDER,
            borderRadius: 5,
            overflow: "hidden",
          }}
        >
          {principles.map((p) => (
            <div
              key={p.index}
              style={{
                background: "var(--color-surface)",
                padding: "26px 24px",
                display: "flex",
                gap: 18,
                alignItems: "flex-start",
              }}
            >
              <span
                style={{
                  fontFamily: "var(--font-mono)",
                  fontSize: 11,
                  color: "var(--color-info)",
                  letterSpacing: "0.1em",
                  paddingTop: 2,
                }}
              >
                {p.index}
              </span>
              <div>
                <div style={{ fontSize: 15, fontWeight: 600, letterSpacing: "-0.005em" }}>{p.title}</div>
                <p style={{ margin: "6px 0 0", fontSize: 13, lineHeight: 1.6, color: "var(--color-text-muted)" }}>
                  {p.body}
                </p>
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

function Closing() {
  return (
    <section>
      <div
        style={{
          maxWidth: 1240,
          margin: "0 auto",
          padding: "80px 24px",
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          gap: 24,
          flexWrap: "wrap",
        }}
      >
        <div>
          <div style={{ ...KICKER, marginBottom: 10 }}>Ready when you are</div>
          <h2
            style={{
              margin: 0,
              fontSize: 36,
              fontWeight: 600,
              letterSpacing: "-0.02em",
              lineHeight: 1.1,
            }}
          >
            Open the war room.
          </h2>
          <p style={{ marginTop: 10, fontSize: 14, color: "var(--color-text-muted)" }}>
            Five pre-scripted scenarios. Full loop in under 60 seconds.
          </p>
        </div>
        <Link
          href="/"
          style={{
            display: "inline-flex",
            alignItems: "center",
            gap: 8,
            height: 40,
            padding: "0 20px",
            borderRadius: 4,
            border: "1px solid var(--color-info)",
            background: "var(--color-info)",
            color: "#1a1408",
            fontSize: 14,
            fontWeight: 600,
            textDecoration: "none",
          }}
        >
          Enter suppl.ai
          <span aria-hidden style={{ fontFamily: "var(--font-mono)", fontSize: 13 }}>→</span>
        </Link>
      </div>
    </section>
  );
}

function Footer() {
  return (
    <footer style={{ borderTop: BORDER }}>
      <div
        style={{
          maxWidth: 1240,
          margin: "0 auto",
          padding: "20px 24px",
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          gap: 16,
          flexWrap: "wrap",
          fontFamily: "var(--font-mono)",
          fontSize: 11,
          color: "var(--color-text-subtle)",
          letterSpacing: "0.04em",
        }}
      >
        <span>suppl.ai · HackPrinceton Spring &rsquo;26</span>
        <span>Inter · JetBrains Mono · Postgres · Dedalus · Gemini · OpenClaw</span>
        <span>v0.1 · build 2026.04.18</span>
      </div>
    </footer>
  );
}

function SectionHead({ kicker, title, sub }: { kicker: string; title: string; sub: string }) {
  return (
    <div style={{ maxWidth: 720 }}>
      <div style={{ ...SECTION_LABEL, marginBottom: 14 }}>{kicker}</div>
      <h2
        style={{
          margin: 0,
          fontSize: 30,
          fontWeight: 600,
          letterSpacing: "-0.02em",
          lineHeight: 1.15,
          color: "var(--color-text)",
        }}
      >
        {title}
      </h2>
      <p style={{ marginTop: 12, fontSize: 14, lineHeight: 1.6, color: "var(--color-text-muted)" }}>
        {sub}
      </p>
    </div>
  );
}

export default function LandingPage() {
  return (
    <>
      <Nav />
      <Hero />
      <Agents />
      <Signals />
      <Workflow />
      <Principles />
      <Closing />
      <Footer />
    </>
  );
}
