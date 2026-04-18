"use client";

import { motion } from "motion/react";

const EASE_OUT: [number, number, number, number] = [0.23, 1, 0.32, 1];

type Tool = { name: string; detail?: string; color: string };

type Band = {
  id: string;
  label: string;
  title: string;
  blurb: string;
  accent: string;
  tools: Tool[];
};

/* Tech "brand" colors — muted so they read clean against the dark bg. */
const COL = {
  python: "#4B8BBE",
  fastapi: "#009688",
  sqlalchemy: "#C44536",
  asyncpg: "#4A8FD4",
  alembic: "#7C9885",
  pydantic: "#E92063",
  structlog: "#8B9098",
  tenacity: "#A3BE8C",
  uv: "#DE52D9",
  ruff: "#D7FF64",
  mypy: "#2A6DB0",
  pytest: "#4A8FD4",

  gemini: "#8AB4F8",
  openclaw: "#FFB454",
  tavily: "#6B9BD2",
  openmeteo: "#A3BE8C",

  postgres: "#4A8FD4",
  listen: "#5E81AC",
  sqlguard: "#E5484D",
  openapi: "#6BA6C1",

  next: "#E8EAED",
  react: "#61DAFB",
  ts: "#3178C6",
  tailwind: "#38BDF8",
  motion: "#E8EAED",
  zustand: "#FFB454",
  tanstack: "#FF4154",
  zod: "#3E67B1",
  shadcn: "#E8EAED",
  leaflet: "#8DC73F",
  recharts: "#A3BE8C",
  playwright: "#2EAD33",

  dedalus: "#B48EAD",
  systemd: "#8B9098",
  vercel: "#E8EAED",
  gha: "#8B9098",
  precommit: "#EBCB8B",
  gitleaks: "#E5484D",
} as const;

const BANDS: Band[] = [
  {
    id: "ingestion",
    label: "Layer 01",
    title: "Ingestion & AI",
    blurb: "external feeds + structured-output LLM calls",
    accent: "#B48EAD",
    tools: [
      { name: "Gemini Flash", detail: "Scout classifier", color: COL.gemini },
      { name: "Gemini Pro", detail: "Analyst + Strategist", color: COL.gemini },
      { name: "OpenClaw", detail: "action layer", color: COL.openclaw },
      { name: "Tavily", detail: "4 source loops", color: COL.tavily },
      { name: "Open-Meteo", detail: "weather · no auth", color: COL.openmeteo },
    ],
  },
  {
    id: "backend",
    label: "Layer 02",
    title: "Agent runtime",
    blurb: "async Python, Pydantic-strict contracts, structured retry",
    accent: "#A3BE8C",
    tools: [
      { name: "Python", detail: "3.12", color: COL.python },
      { name: "FastAPI", detail: "async", color: COL.fastapi },
      { name: "SQLAlchemy 2.x", detail: "async", color: COL.sqlalchemy },
      { name: "asyncpg", detail: "driver", color: COL.asyncpg },
      { name: "Alembic", detail: "migrations", color: COL.alembic },
      { name: "Pydantic v2", detail: "strict", color: COL.pydantic },
      { name: "structlog", detail: "trace_id", color: COL.structlog },
      { name: "tenacity", detail: "retry + jitter", color: COL.tenacity },
    ],
  },
  {
    id: "data",
    label: "Layer 03",
    title: "Data bus & safety",
    blurb: "Postgres LISTEN/NOTIFY coordinates every agent — no RPC",
    accent: "#4A8FD4",
    tools: [
      { name: "Postgres 16", detail: "14 tables", color: COL.postgres },
      { name: "LISTEN / NOTIFY", detail: "event bus", color: COL.listen },
      { name: "sql_guard", detail: "22 tests · token-level", color: COL.sqlguard },
      { name: "Atomic approvals", detail: "all-or-nothing", color: COL.listen },
      { name: "OpenAPI", detail: "→ openapi-typescript", color: COL.openapi },
    ],
  },
  {
    id: "frontend",
    label: "Layer 04",
    title: "War Room frontend",
    blurb: "Next.js 15 · React 19 · Tailwind v4 — dense, dark, details-obsessed",
    accent: "#EBCB8B",
    tools: [
      { name: "Next.js", detail: "15 · Turbopack", color: COL.next },
      { name: "React", detail: "19", color: COL.react },
      { name: "TypeScript", detail: "strict", color: COL.ts },
      { name: "Tailwind", detail: "v4", color: COL.tailwind },
      { name: "Motion", detail: "spring physics", color: COL.motion },
      { name: "Zustand", detail: "client state", color: COL.zustand },
      { name: "TanStack Query", detail: "v5", color: COL.tanstack },
      { name: "zod", detail: "runtime validation", color: COL.zod },
      { name: "shadcn/ui", detail: "customized", color: COL.shadcn },
      { name: "Leaflet", detail: "world map", color: COL.leaflet },
      { name: "Recharts", detail: "analytics", color: COL.recharts },
      { name: "Playwright", detail: "e2e", color: COL.playwright },
    ],
  },
  {
    id: "platform",
    label: "Layer 05",
    title: "Platform & DX",
    blurb: "persistent VMs, trunk-based CI, lint + type gates on every commit",
    accent: "#D08770",
    tools: [
      { name: "Dedalus", detail: "4 Machines", color: COL.dedalus },
      { name: "systemd", detail: "restart + checkpoint", color: COL.systemd },
      { name: "Vercel", detail: "preview on PR", color: COL.vercel },
      { name: "GitHub Actions", detail: "CI", color: COL.gha },
      { name: "uv", detail: "pkg manager", color: COL.uv },
      { name: "ruff", detail: "lint + format", color: COL.ruff },
      { name: "mypy", detail: "--strict", color: COL.mypy },
      { name: "pytest", detail: "+ asyncio", color: COL.pytest },
      { name: "pre-commit", detail: "hooks", color: COL.precommit },
      { name: "gitleaks", detail: "secret scan", color: COL.gitleaks },
    ],
  },
];

function Tile({ tool, i }: { tool: Tool; i: number }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 4 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.22, delay: 0.04 + i * 0.015, ease: EASE_OUT }}
      className="group flex min-w-0 items-center gap-2.5 rounded-md border border-[var(--color-border)] bg-[var(--color-surface-raised)] px-2.5 py-1.5 transition-colors hover:border-[var(--color-border-strong)]"
    >
      <span
        aria-hidden
        className="h-5 w-1 flex-none rounded-full"
        style={{ background: tool.color, boxShadow: `0 0 10px ${tool.color}55` }}
      />
      <div className="flex min-w-0 flex-col">
        <span className="truncate text-[12px] font-medium leading-tight text-[var(--color-text)]">
          {tool.name}
        </span>
        {tool.detail ? (
          <span className="truncate font-mono text-[9.5px] leading-tight text-[var(--color-text-subtle)]">
            {tool.detail}
          </span>
        ) : null}
      </div>
    </motion.div>
  );
}

function BandRow({ band, i }: { band: Band; i: number }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3, delay: i * 0.06, ease: EASE_OUT }}
      className="relative flex min-h-0 flex-1 overflow-hidden rounded-xl border border-[var(--color-border)]"
      style={{
        background: `linear-gradient(90deg, ${band.accent}1c 0%, ${band.accent}08 45%, transparent 100%)`,
      }}
    >
      {/* Left accent bar */}
      <div aria-hidden className="absolute inset-y-0 left-0 w-[3px]" style={{ background: band.accent }} />

      {/* Label sidebar (fixed width) */}
      <div className="flex w-[200px] flex-none flex-col justify-center gap-1 border-r border-[var(--color-border)] pl-4 pr-3">
        <div
          className="font-mono text-[9px] uppercase tracking-[0.24em]"
          style={{ color: band.accent }}
        >
          {band.label}
        </div>
        <div className="text-[15px] font-medium leading-tight tracking-tight">{band.title}</div>
        <div className="text-[10.5px] leading-snug text-[var(--color-text-muted)]">{band.blurb}</div>
      </div>

      {/* Tiles grid */}
      <div className="flex min-w-0 flex-1 flex-wrap content-center items-center gap-2 px-4">
        {band.tools.map((tool, idx) => (
          <Tile key={tool.name} tool={tool} i={idx} />
        ))}
      </div>

      {/* Tool count pill */}
      <div className="flex flex-none items-center pr-4">
        <div className="rounded-full border border-[var(--color-border)] bg-[var(--color-bg)]/60 px-2 py-0.5 font-mono text-[10px] text-[var(--color-text-subtle)]">
          {band.tools.length}
        </div>
      </div>
    </motion.div>
  );
}

/**
 * Pulse connector between two bands. A dim line + a bright short segment
 * that travels along it via CSS stroke-dashoffset animation. Reliable,
 * hardware-accelerated, and respects prefers-reduced-motion via the global
 * `animation-duration: 0.001ms` rule in globals.css.
 */
function Pulse({ accent, delay = 0 }: { accent: string; delay?: number }) {
  return (
    <div aria-hidden className="relative h-3 w-full flex-none">
      <svg
        viewBox="0 0 100 12"
        preserveAspectRatio="none"
        className="h-full w-full overflow-visible"
      >
        {/* dim base line */}
        <path
          d="M 50 0 L 50 12"
          stroke="var(--color-border-strong)"
          strokeWidth={1}
          fill="none"
          vectorEffect="non-scaling-stroke"
        />
        {/* bright traveling pulse — CSS animation drives the dashoffset */}
        <path
          d="M 50 0 L 50 12"
          stroke={accent}
          strokeWidth={2}
          strokeLinecap="round"
          fill="none"
          className="stack-pulse-v"
          style={{ animationDelay: `${delay}s`, filter: `drop-shadow(0 0 4px ${accent}cc)` }}
          vectorEffect="non-scaling-stroke"
        />
      </svg>
    </div>
  );
}

export default function StackPage() {
  return (
    <main className="flex h-screen w-screen flex-col overflow-hidden bg-[var(--color-bg)] text-[var(--color-text)]">
      {/* Inline CSS for the pulse animation — CSS keyframes are the most
          reliable + performant way to animate stroke-dashoffset across
          browsers (SMIL has had mixed support historically). */}
      <style>{`
        @keyframes stack-pulse-v-kf {
          from { stroke-dashoffset: 0; }
          to   { stroke-dashoffset: -12; }
        }
        .stack-pulse-v {
          stroke-dasharray: 2 10;
          animation: stack-pulse-v-kf 1.1s linear infinite;
        }
        @media (prefers-reduced-motion: reduce) {
          .stack-pulse-v { animation: none; stroke-dasharray: 0; }
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
            <span className="tnum text-[var(--color-text)]">5</span> layers
          </span>
          <span>
            <span className="tnum text-[var(--color-text)]">40</span> deps
          </span>
          <span>
            <span className="tnum text-[var(--color-text)]">218</span> tests
          </span>
        </div>
      </motion.header>

      <div className="relative mx-auto flex min-h-0 w-full max-w-[1400px] flex-1 flex-col px-6 py-5">
        <div className="flex min-h-0 flex-1 flex-col">
          {BANDS.map((band, i) => (
            <div key={band.id} className="flex min-h-0 flex-1 flex-col">
              <BandRow band={band} i={i} />
              {i < BANDS.length - 1 ? (
                <Pulse accent={band.accent} delay={i * 0.18} />
              ) : null}
            </div>
          ))}
        </div>
      </div>
    </main>
  );
}
