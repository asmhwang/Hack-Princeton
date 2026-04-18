"use client";

import { motion } from "motion/react";

const EASE_OUT: [number, number, number, number] = [0.23, 1, 0.32, 1];

/* Arrow accent — a slightly-vibrant violet that reads clearly against the
   dark bg and matches the reference image's purple connector look. */
const ARROW = "#A78BFA";
const ARROW_DIM = "#A78BFA40";

type Tool = { name: string; color: string };
type Box = {
  id: string;
  label: string;
  cx: number;
  cy: number;
  w: number;
  h: number;
  tools: Tool[];
};

/* All coordinates live in a single 1400 × 820 viewBox so positions are
   deterministic and the whole diagram scales uniformly on resize. */

const HUB: { cx: number; cy: number; w: number; h: number } = {
  cx: 700,
  cy: 420,
  w: 260,
  h: 90,
};

const BOXES: Box[] = [
  {
    id: "agents",
    label: "Agents",
    cx: 230,
    cy: 110,
    w: 220,
    h: 160,
    tools: [
      { name: "Scout",       color: "#A3BE8C" },
      { name: "Analyst",     color: "#EBCB8B" },
      { name: "Strategist",  color: "#B48EAD" },
    ],
  },
  {
    id: "llm",
    label: "LLM",
    cx: 700,
    cy: 110,
    w: 220,
    h: 160,
    tools: [
      { name: "Gemini Flash", color: "#8AB4F8" },
      { name: "Gemini Pro",   color: "#8AB4F8" },
      { name: "OpenClaw",     color: "#FFB454" },
    ],
  },
  {
    id: "sources",
    label: "Sources",
    cx: 1170,
    cy: 110,
    w: 220,
    h: 160,
    tools: [
      { name: "Tavily",     color: "#6B9BD2" },
      { name: "Open-Meteo", color: "#A3BE8C" },
    ],
  },
  {
    id: "backend",
    label: "Backend",
    cx: 180,
    cy: 700,
    w: 220,
    h: 160,
    tools: [
      { name: "Python 3.12",  color: "#4B8BBE" },
      { name: "FastAPI",      color: "#009688" },
      { name: "Pydantic v2",  color: "#E92063" },
      { name: "SQLAlchemy",   color: "#C44536" },
    ],
  },
  {
    id: "database",
    label: "Database",
    cx: 530,
    cy: 700,
    w: 220,
    h: 160,
    tools: [
      { name: "Postgres 16",     color: "#4A8FD4" },
      { name: "LISTEN / NOTIFY", color: "#5E81AC" },
      { name: "asyncpg",         color: "#4A8FD4" },
      { name: "Alembic",         color: "#7C9885" },
    ],
  },
  {
    id: "frontend",
    label: "Frontend",
    cx: 870,
    cy: 700,
    w: 220,
    h: 160,
    tools: [
      { name: "Next.js 15", color: "#E8EAED" },
      { name: "React 19",   color: "#61DAFB" },
      { name: "Tailwind v4", color: "#38BDF8" },
      { name: "Motion",     color: "#E8EAED" },
    ],
  },
  {
    id: "platform",
    label: "Platform",
    cx: 1220,
    cy: 700,
    w: 220,
    h: 160,
    tools: [
      { name: "Dedalus",        color: "#B48EAD" },
      { name: "Vercel",         color: "#E8EAED" },
      { name: "GitHub Actions", color: "#8B9098" },
      { name: "systemd",        color: "#8B9098" },
    ],
  },
];

/* Compute each connector: start on hub edge, end on box edge (inset 6px so
   the arrowhead sits cleanly OUTSIDE the box outline). Start points are
   spread along the hub's top/bottom edge so the fan of arrows looks
   balanced, not stacked. */

type Connector = {
  id: string;
  x1: number;
  y1: number;
  x2: number;
  y2: number;
  delay: number;
};

function buildConnectors(): Connector[] {
  const hubTopY = HUB.cy - HUB.h / 2; // 375
  const hubBottomY = HUB.cy + HUB.h / 2; // 465

  // Spread hub anchors along top/bottom edges.
  const topAnchors = [
    HUB.cx - 80, // Agents
    HUB.cx,      // LLM
    HUB.cx + 80, // Sources
  ];
  const bottomAnchors = [
    HUB.cx - 90, // Backend
    HUB.cx - 30, // Database
    HUB.cx + 30, // Frontend
    HUB.cx + 90, // Platform
  ];

  const topIds = ["agents", "llm", "sources"];
  const bottomIds = ["backend", "database", "frontend", "platform"];

  const lookup = Object.fromEntries(BOXES.map((b) => [b.id, b]));
  const result: Connector[] = [];

  topIds.forEach((id, i) => {
    const box = lookup[id];
    const boxBottomY = box.cy + box.h / 2; // 190
    result.push({
      id: `hub-${id}`,
      x1: topAnchors[i],
      y1: hubTopY,
      x2: box.cx,
      y2: boxBottomY + 6,
      delay: i * 0.18,
    });
  });

  bottomIds.forEach((id, i) => {
    const box = lookup[id];
    const boxTopY = box.cy - box.h / 2; // 620
    result.push({
      id: `hub-${id}`,
      x1: bottomAnchors[i],
      y1: hubBottomY,
      x2: box.cx,
      y2: boxTopY - 6,
      delay: 0.1 + i * 0.18,
    });
  });

  return result;
}

const CONNECTORS = buildConnectors();

/* ── Renderers ───────────────────────────────────────────────────────────── */

function ArrowConnector({ c }: { c: Connector }) {
  const dx = c.x2 - c.x1;
  const dy = c.y2 - c.y1;
  const angle = (Math.atan2(dy, dx) * 180) / Math.PI;
  // Arrowhead tip positioned at (x2, y2), pointing along the line.
  return (
    <g>
      {/* Static dashed base — gives the "dashed arrow" look from the reference */}
      <line
        x1={c.x1}
        y1={c.y1}
        x2={c.x2}
        y2={c.y2}
        stroke={ARROW_DIM}
        strokeWidth={1.5}
        strokeDasharray="4 4"
        fill="none"
      />
      {/* Bright traveling pulse — CSS animation on stroke-dashoffset.
          pathLength=100 normalizes so all connectors can share one
          keyframe regardless of actual pixel length. */}
      <line
        x1={c.x1}
        y1={c.y1}
        x2={c.x2}
        y2={c.y2}
        stroke={ARROW}
        strokeWidth={2}
        strokeLinecap="round"
        fill="none"
        pathLength={100}
        className="stack-arrow-pulse"
        style={{
          animationDelay: `${c.delay}s`,
          filter: `drop-shadow(0 0 4px ${ARROW}aa)`,
        }}
      />
      {/* Arrowhead */}
      <polygon
        points="0,-5 10,0 0,5"
        fill={ARROW}
        transform={`translate(${c.x2}, ${c.y2}) rotate(${angle})`}
      />
    </g>
  );
}

function BoxNode({ box }: { box: Box }) {
  const x = box.cx - box.w / 2;
  const y = box.cy - box.h / 2;
  const titleY = y + 26;
  const dividerY = y + 40;
  const firstToolY = y + 66;
  const toolStep = 28;
  return (
    <motion.g
      initial={{ opacity: 0, y: 4 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3, ease: EASE_OUT }}
    >
      <rect
        x={x}
        y={y}
        width={box.w}
        height={box.h}
        rx={14}
        ry={14}
        fill="var(--color-surface)"
        stroke={ARROW}
        strokeOpacity={0.45}
        strokeWidth={1.2}
      />
      {/* subtle inner-top wash */}
      <rect
        x={x + 1}
        y={y + 1}
        width={box.w - 2}
        height={40}
        rx={13}
        ry={13}
        fill={`${ARROW}12`}
      />
      <text
        x={box.cx}
        y={titleY}
        textAnchor="middle"
        fontSize={12}
        fontFamily="var(--font-sans)"
        fontWeight={500}
        fill="var(--color-text)"
        style={{ letterSpacing: "0.04em" }}
      >
        {box.label}
      </text>
      <line
        x1={x + 16}
        x2={x + box.w - 16}
        y1={dividerY}
        y2={dividerY}
        stroke="var(--color-border-strong)"
        strokeWidth={1}
      />
      {box.tools.map((t, i) => {
        const ty = firstToolY + i * toolStep;
        return (
          <g key={t.name}>
            <circle
              cx={x + 24}
              cy={ty}
              r={5}
              fill={t.color}
              style={{ filter: `drop-shadow(0 0 6px ${t.color}aa)` }}
            />
            <text
              x={x + 38}
              y={ty + 4}
              fontSize={13}
              fontFamily="var(--font-sans)"
              fontWeight={500}
              fill="var(--color-text)"
            >
              {t.name}
            </text>
          </g>
        );
      })}
    </motion.g>
  );
}

function HubNode() {
  const x = HUB.cx - HUB.w / 2;
  const y = HUB.cy - HUB.h / 2;
  return (
    <motion.g
      initial={{ opacity: 0, scale: 0.96 }}
      animate={{ opacity: 1, scale: 1 }}
      transition={{ duration: 0.32, ease: EASE_OUT }}
      style={{ transformOrigin: `${HUB.cx}px ${HUB.cy}px` }}
    >
      {/* outer halo */}
      <rect
        x={x - 8}
        y={y - 8}
        width={HUB.w + 16}
        height={HUB.h + 16}
        rx={18}
        ry={18}
        fill="none"
        stroke={ARROW}
        strokeOpacity={0.15}
        strokeWidth={1}
      />
      <rect
        x={x}
        y={y}
        width={HUB.w}
        height={HUB.h}
        rx={14}
        ry={14}
        fill="var(--color-surface-raised)"
        stroke={ARROW}
        strokeOpacity={0.65}
        strokeWidth={1.5}
        style={{ filter: `drop-shadow(0 0 14px ${ARROW}44)` }}
      />
      <text
        x={HUB.cx}
        y={HUB.cy - 4}
        textAnchor="middle"
        fontSize={22}
        fontFamily="var(--font-sans)"
        fontWeight={600}
        fill="var(--color-text)"
      >
        suppl
        <tspan fill={ARROW}>.</tspan>
        ai
      </text>
      <text
        x={HUB.cx}
        y={HUB.cy + 18}
        textAnchor="middle"
        fontSize={10}
        fontFamily="var(--font-mono)"
        fill="var(--color-text-subtle)"
        style={{ letterSpacing: "0.18em" }}
      >
        TECH STACK
      </text>
    </motion.g>
  );
}

/* ── Page ─────────────────────────────────────────────────────────────────── */

export default function StackPage() {
  return (
    <main className="flex h-screen w-screen flex-col overflow-hidden bg-[var(--color-bg)] text-[var(--color-text)]">
      <style>{`
        @keyframes stack-arrow-pulse-kf {
          from { stroke-dashoffset: 0; }
          to   { stroke-dashoffset: -100; }
        }
        .stack-arrow-pulse {
          stroke-dasharray: 6 94;
          animation: stack-arrow-pulse-kf 2.4s linear infinite;
        }
        @media (prefers-reduced-motion: reduce) {
          .stack-arrow-pulse { animation: none; stroke-dasharray: 0; opacity: 0; }
        }
      `}</style>

      <motion.header
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ duration: 0.3, ease: EASE_OUT }}
        className="flex h-12 flex-none items-baseline justify-between border-b border-[var(--color-border)] px-6"
      >
        <div className="flex items-baseline gap-3">
          <span className="font-mono text-[10px] uppercase tracking-[0.22em] text-[var(--color-text-subtle)]">
            Tech stack
          </span>
          <h1 className="text-[16px] font-medium tracking-tight">
            suppl<span className="text-[var(--color-info)]">.</span>ai
          </h1>
        </div>
        <div className="flex items-baseline gap-6 font-mono text-[10px] uppercase tracking-[0.14em] text-[var(--color-text-subtle)]">
          <span>
            <span className="tnum text-[var(--color-text)]">3</span> agents
          </span>
          <span>
            <span className="tnum text-[var(--color-text)]">14</span> tables
          </span>
          <span>
            <span className="tnum text-[var(--color-text)]">7</span> categories
          </span>
          <span>
            <span className="tnum text-[var(--color-text)]">218</span> tests
          </span>
        </div>
      </motion.header>

      <div className="relative mx-auto flex min-h-0 w-full max-w-[1440px] flex-1 items-center justify-center px-6 py-4">
        <svg
          viewBox="0 0 1400 820"
          preserveAspectRatio="xMidYMid meet"
          className="h-full w-full"
          aria-label="suppl.ai tech stack diagram"
        >
          {/* Connectors drawn first so boxes render on top of line endpoints */}
          <g>
            {CONNECTORS.map((c) => (
              <ArrowConnector key={c.id} c={c} />
            ))}
          </g>
          {/* Category boxes */}
          {BOXES.map((b) => (
            <BoxNode key={b.id} box={b} />
          ))}
          {/* Central hub — drawn last so it sits on top of any connector endpoints */}
          <HubNode />
        </svg>
      </div>
    </main>
  );
}
