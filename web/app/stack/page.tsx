"use client";

import { motion } from "motion/react";

const EASE_OUT: [number, number, number, number] = [0.23, 1, 0.32, 1];

type Chip = { name: string; detail?: string; mono?: boolean };

type Band = {
  id: string;
  title: string;
  blurb: string;
  accent: string;
  chips: Chip[];
};

const BANDS: Band[] = [
  {
    id: "agents",
    title: "Agents",
    blurb: "three specialized processes, one responsibility each",
    accent: "#A3BE8C",
    chips: [
      { name: "Scout", detail: "5 source loops · Gemini Flash" },
      { name: "Analyst", detail: "tool-calling · Gemini Pro" },
      { name: "Strategist", detail: "mitigation drafts · OpenClaw" },
      { name: "AgentBase", detail: "lifecycle + checkpoint", mono: true },
    ],
  },
  {
    id: "llm",
    title: "LLM & external sources",
    blurb: "structured output, function calling, cached contexts — no text-to-SQL",
    accent: "#B48EAD",
    chips: [
      { name: "Gemini 2.x Flash" },
      { name: "Gemini 2.x Pro" },
      { name: "response_schema", mono: true },
      { name: "function calling", detail: "7 analyst tools" },
      { name: "cached_contents", mono: true },
      { name: "SQLite cache", detail: "offline demo" },
      { name: "OpenClaw", detail: "action layer" },
      { name: "Tavily", detail: "4 source loops" },
      { name: "Open-Meteo", detail: "no auth" },
    ],
  },
  {
    id: "runtime",
    title: "Runtime & data layer",
    blurb: "Postgres is the bus. Agents talk only through LISTEN/NOTIFY.",
    accent: "#4A8FD4",
    chips: [
      { name: "Postgres 16", detail: "LISTEN / NOTIFY" },
      { name: "EventBus", detail: "reconnect + resubscribe", mono: true },
      { name: "SQLAlchemy 2.x", detail: "async" },
      { name: "asyncpg" },
      { name: "Alembic", detail: "migrations" },
      { name: "Pydantic v2", detail: "strict" },
      { name: "structlog", detail: "trace_id ctx" },
      { name: "tenacity", detail: "retry" },
    ],
  },
  {
    id: "api",
    title: "API & safety",
    blurb: "typed routes, OpenAPI-driven FE codegen, defense-in-depth SQL guard",
    accent: "#5E81AC",
    chips: [
      { name: "FastAPI", detail: "async" },
      { name: "uvicorn" },
      { name: "WebSocket", detail: "/ws/updates", mono: true },
      { name: "sql_guard", detail: "token-level · 22 tests", mono: true },
      { name: "OpenAPI", detail: "→ openapi-typescript" },
      { name: "Atomic approvals", detail: "all-or-nothing" },
    ],
  },
  {
    id: "frontend",
    title: "Frontend",
    blurb: "dense, dark, detail-obsessed — Linear / Vercel aesthetic",
    accent: "#EBCB8B",
    chips: [
      { name: "Next.js 15", detail: "App Router · Turbopack" },
      { name: "React 19", detail: "useOptimistic" },
      { name: "TypeScript", detail: "strict" },
      { name: "Tailwind v4" },
      { name: "shadcn/ui", detail: "customized" },
      { name: "Motion", detail: "spring physics" },
      { name: "Zustand" },
      { name: "TanStack Query", detail: "v5" },
      { name: "zod" },
      { name: "Leaflet" },
      { name: "Recharts" },
      { name: "Playwright", detail: "e2e" },
    ],
  },
  {
    id: "platform",
    title: "Platform & DX",
    blurb: "persistent agent VMs, trunk-based CI, lint + type gates on every commit",
    accent: "#D08770",
    chips: [
      { name: "Dedalus Machines", detail: "4 VMs · systemd" },
      { name: "Vercel", detail: "preview on PR" },
      { name: "GitHub Actions", detail: "CI" },
      { name: "uv", detail: "pkg manager", mono: true },
      { name: "ruff", detail: "lint + format", mono: true },
      { name: "mypy --strict", mono: true },
      { name: "pytest", detail: "+ asyncio", mono: true },
      { name: "pre-commit" },
      { name: "gitleaks", detail: "secret scan" },
    ],
  },
];

/**
 * Vertical connector with a traveling pulse. Base line is dim and static;
 * the pulse is a short bright dash that travels top-to-bottom along the
 * line on a 3s loop via stroke-dashoffset — hardware-accelerated, off the
 * main thread. dasharray "10 200" means one 10-unit bright segment with
 * a 200-unit gap, so only one pulse is visible at a time.
 */
function Connector({ accent, delay }: { accent: string; delay: number }) {
  const glowId = `glow-${accent.replace("#", "")}`;
  return (
    <div
      aria-hidden
      className="pointer-events-none mx-auto flex h-14 w-10 items-stretch justify-center"
    >
      <svg viewBox="0 0 40 56" width="40" height="56" className="overflow-visible">
        <defs>
          <filter id={glowId} x="-50%" y="-50%" width="200%" height="200%">
            <feGaussianBlur stdDeviation="2" result="blur" />
            <feMerge>
              <feMergeNode in="blur" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>
        </defs>
        <path
          d="M 20 0 L 20 56"
          stroke="var(--color-border-strong)"
          strokeWidth={1}
          fill="none"
        />
        <path
          d="M 20 0 L 20 56"
          stroke={accent}
          strokeWidth={2}
          strokeLinecap="round"
          fill="none"
          strokeDasharray="10 200"
          filter={`url(#${glowId})`}
        >
          <animate
            attributeName="stroke-dashoffset"
            from={-1 * delay}
            to={-210 - delay}
            dur="3s"
            repeatCount="indefinite"
          />
        </path>
      </svg>
    </div>
  );
}

function Chip({ chip, accent, index }: { chip: Chip; accent: string; index: number }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 6 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, margin: "-10%" }}
      transition={{ duration: 0.28, delay: 0.05 + index * 0.025, ease: EASE_OUT }}
      whileHover={{ y: -1 }}
      className="group relative inline-flex items-baseline gap-2 rounded-md border border-[var(--color-border)] bg-[var(--color-surface-raised)] px-3 py-2 pl-4 transition-colors hover:border-[var(--color-border-strong)]"
    >
      <span
        aria-hidden
        className="absolute left-0 top-0 bottom-0 w-[2px] rounded-l-md"
        style={{ background: accent }}
      />
      <span
        className={
          (chip.mono ? "font-mono " : "font-medium ") +
          "text-[13px] text-[var(--color-text)]"
        }
      >
        {chip.name}
      </span>
      {chip.detail ? (
        <span className="font-mono text-[11px] text-[var(--color-text-subtle)] truncate">
          {chip.detail}
        </span>
      ) : null}
    </motion.div>
  );
}

function BandBlock({ band, index }: { band: Band; index: number }) {
  return (
    <motion.section
      initial={{ opacity: 0, y: 10 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, margin: "-10%" }}
      transition={{ duration: 0.32, delay: index * 0.04, ease: EASE_OUT }}
      className="relative overflow-hidden rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)]"
    >
      <div
        aria-hidden
        className="pointer-events-none absolute inset-y-0 left-0 w-64"
        style={{
          background: `radial-gradient(circle at 0% 50%, ${band.accent}22 0%, transparent 70%)`,
        }}
      />
      <div
        aria-hidden
        className="absolute inset-y-0 left-0 w-[3px]"
        style={{ background: band.accent }}
      />
      <div className="relative grid grid-cols-1 md:grid-cols-[240px_1fr] gap-6 md:gap-10 p-6 md:p-7">
        <div className="md:pr-4">
          <div
            className="mb-2 text-[10px] font-mono uppercase tracking-[0.22em]"
            style={{ color: band.accent }}
          >
            Layer {String(index + 1).padStart(2, "0")}
          </div>
          <h3 className="text-[20px] md:text-[22px] font-medium tracking-tight">
            {band.title}
          </h3>
          <p className="mt-2 text-[13px] leading-relaxed text-[var(--color-text-muted)]">
            {band.blurb}
          </p>
          <div className="mt-4 inline-flex items-center gap-2 rounded-full border border-[var(--color-border)] bg-[var(--color-bg)]/60 px-2.5 py-1 font-mono text-[10px] uppercase tracking-[0.12em] text-[var(--color-text-subtle)]">
            <span
              aria-hidden
              className="h-1 w-1 rounded-full"
              style={{ background: band.accent }}
            />
            {band.chips.length} deps
          </div>
        </div>
        <div className="flex flex-wrap gap-2 items-start content-start">
          {band.chips.map((chip, i) => (
            <Chip key={chip.name} chip={chip} accent={band.accent} index={i} />
          ))}
        </div>
      </div>
    </motion.section>
  );
}

export default function StackPage() {
  const totalDeps = BANDS.reduce((n, b) => n + b.chips.length, 0);
  return (
    <main className="min-h-screen bg-[var(--color-bg)] text-[var(--color-text)]">
      <div className="mx-auto w-full max-w-[1080px] px-6 py-16 md:py-20">
        <motion.header
          initial={{ opacity: 0, y: 6 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.32, ease: EASE_OUT }}
          className="mb-10 flex flex-wrap items-baseline justify-between gap-4"
        >
          <div>
            <div className="font-mono text-[11px] uppercase tracking-[0.22em] text-[var(--color-text-subtle)]">
              Tech stack
            </div>
            <h1 className="mt-1 font-medium tracking-tight text-[32px] md:text-[40px] leading-tight">
              suppl<span className="text-[var(--color-info)]">.</span>ai
            </h1>
          </div>
          <div className="font-mono text-[11px] text-[var(--color-text-subtle)]">
            {BANDS.length} layers · {totalDeps} deps
          </div>
        </motion.header>

        {BANDS.map((band, i) => (
          <div key={band.id}>
            <BandBlock band={band} index={i} />
            {i < BANDS.length - 1 ? (
              <Connector accent={band.accent} delay={i * 18} />
            ) : null}
          </div>
        ))}
      </div>
    </main>
  );
}
