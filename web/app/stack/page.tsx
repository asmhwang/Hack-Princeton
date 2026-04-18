"use client";

import { motion } from "motion/react";
import type { ReactNode } from "react";

const EASE_OUT: [number, number, number, number] = [0.23, 1, 0.32, 1];

const ARROW = "#A78BFA";
const ARROW_DIM = "#A78BFA40";

/* ── Pulse between layers ────────────────────────────────────────────────── */

function VerticalPulse({
  accent = ARROW,
  delay = 0,
  count = 1,
}: {
  accent?: string;
  delay?: number;
  count?: number;
}) {
  const lines = Array.from({ length: count }, (_, i) => i);
  return (
    <div className="relative flex h-6 w-full items-stretch justify-center gap-8">
      {lines.map((i) => (
        <div key={i} className="relative h-full w-px">
          <svg
            viewBox="0 0 2 24"
            preserveAspectRatio="none"
            className="absolute inset-0 h-full w-[14px] -translate-x-1/2 overflow-visible"
          >
            {/* dashed base */}
            <line
              x1={1}
              y1={0}
              x2={1}
              y2={24}
              stroke={ARROW_DIM}
              strokeWidth={1}
              strokeDasharray="3 3"
              vectorEffect="non-scaling-stroke"
            />
            {/* bright pulse (pathLength=100 normalizes the dash math) */}
            <line
              x1={1}
              y1={24}
              x2={1}
              y2={0}
              stroke={accent}
              strokeWidth={2}
              strokeLinecap="round"
              pathLength={100}
              className="stack-pulse"
              style={{
                animationDelay: `${delay + i * 0.25}s`,
                filter: `drop-shadow(0 0 4px ${accent}cc)`,
              }}
              vectorEffect="non-scaling-stroke"
            />
            {/* arrowhead at top */}
            <polygon
              points="-3,4 1,0 5,4"
              fill={accent}
              style={{ filter: `drop-shadow(0 0 2px ${accent}88)` }}
            />
          </svg>
        </div>
      ))}
    </div>
  );
}

/* ── Layer shell ─────────────────────────────────────────────────────────── */

function Layer({
  index,
  name,
  meta,
  deploy,
  children,
  delay = 0,
  emphasis = "normal",
}: {
  index: string;
  name: string;
  meta?: string;
  deploy?: string;
  children: ReactNode;
  delay?: number;
  emphasis?: "normal" | "strong";
}) {
  const strongStyle = emphasis === "strong"
    ? "border-[color-mix(in_oklab,var(--color-info)_45%,var(--color-border))] bg-[color-mix(in_oklab,var(--color-info)_8%,var(--color-surface))]"
    : "";
  return (
    <motion.div
      initial={{ opacity: 0, y: 4 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.28, delay, ease: EASE_OUT }}
      className={`relative flex min-h-0 flex-1 items-stretch gap-0 rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] ${strongStyle}`}
    >
      {/* left label column */}
      <div className="flex w-[160px] flex-none flex-col justify-center gap-0.5 border-r border-[var(--color-border)] px-4">
        <div className="font-mono text-[9px] uppercase tracking-[0.22em] text-[var(--color-text-subtle)]">
          Layer {index}
        </div>
        <div className="text-[14px] font-medium leading-tight">{name}</div>
        {meta ? (
          <div className="font-mono text-[10px] leading-tight text-[var(--color-text-subtle)]">
            {meta}
          </div>
        ) : null}
      </div>

      {/* content */}
      <div className="flex min-w-0 flex-1 items-stretch">{children}</div>

      {/* deploy annotation column (right) */}
      <div className="flex w-[170px] flex-none flex-col items-end justify-center gap-0.5 border-l border-[var(--color-border)] px-4 text-right">
        {deploy ? (
          <>
            <div className="font-mono text-[9px] uppercase tracking-[0.2em] text-[var(--color-text-subtle)]">
              Deploy
            </div>
            <div className="font-mono text-[11px] leading-tight text-[var(--color-text-muted)]">
              {deploy}
            </div>
          </>
        ) : (
          <div className="font-mono text-[10px] text-[var(--color-text-subtle)]">
            local · CI
          </div>
        )}
      </div>
    </motion.div>
  );
}

/* ── Content helpers ─────────────────────────────────────────────────────── */

function Pill({ children, accent }: { children: ReactNode; accent?: string }) {
  return (
    <span
      className="inline-flex items-center gap-1.5 rounded border border-[var(--color-border)] bg-[var(--color-surface-raised)] px-2 py-0.5 font-mono text-[10px] text-[var(--color-text)]"
      style={accent ? { borderLeft: `2px solid ${accent}` } : undefined}
    >
      {children}
    </span>
  );
}

function Mono({ children }: { children: ReactNode }) {
  return (
    <span className="font-mono text-[11px] text-[var(--color-text)]">{children}</span>
  );
}

function Muted({ children }: { children: ReactNode }) {
  return <span className="text-[var(--color-text-muted)]">{children}</span>;
}

function AgentCard({
  color,
  name,
  model,
  lines,
}: {
  color: string;
  name: string;
  model: string;
  lines: ReactNode[];
}) {
  return (
    <div
      className="relative flex min-w-0 flex-1 flex-col gap-1 rounded-md border border-[var(--color-border)] bg-[var(--color-surface-raised)] p-3"
      style={{
        boxShadow: `inset 2px 0 0 0 ${color}, 0 0 0 1px ${color}22`,
      }}
    >
      <div className="flex items-baseline justify-between gap-2">
        <span className="text-[13px] font-medium" style={{ color }}>
          {name}
        </span>
        <span className="font-mono text-[10px] text-[var(--color-text-subtle)]">{model}</span>
      </div>
      {lines.map((line, i) => (
        <div key={i} className="text-[11px] leading-snug text-[var(--color-text-muted)]">
          {line}
        </div>
      ))}
    </div>
  );
}

/* ── Page ─────────────────────────────────────────────────────────────────── */

export default function StackPage() {
  return (
    <main className="flex h-screen w-screen flex-col overflow-hidden bg-[var(--color-bg)] text-[var(--color-text)]">
      {/* Header */}
      <motion.header
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ duration: 0.3, ease: EASE_OUT }}
        className="flex h-12 flex-none items-baseline justify-between border-b border-[var(--color-border)] px-6"
      >
        <div className="flex items-baseline gap-3">
          <span className="font-mono text-[10px] uppercase tracking-[0.22em] text-[var(--color-text-subtle)]">
            System architecture
          </span>
          <h1 className="text-[16px] font-medium tracking-tight">
            suppl<span className="text-[var(--color-info)]">.</span>ai
          </h1>
        </div>
        <div className="flex items-baseline gap-6 font-mono text-[10px] uppercase tracking-[0.14em] text-[var(--color-text-subtle)]">
          <span>data flows <span className="text-[var(--color-text)]">↑</span> upward</span>
          <span>
            <span className="tnum text-[var(--color-text)]">6</span> layers
          </span>
          <span>
            <span className="tnum text-[var(--color-text)]">3</span> agents
          </span>
          <span>
            <span className="tnum text-[var(--color-text)]">14</span> tables
          </span>
          <span>
            <span className="tnum text-[var(--color-text)]">218</span> tests
          </span>
        </div>
      </motion.header>

      {/* Diagram */}
      <div className="mx-auto flex min-h-0 w-full max-w-[1440px] flex-1 flex-col gap-0 px-6 py-4">
        {/* Layer 01 — Client */}
        <Layer index="01" name="Client" meta="browser · Vercel" deploy="Vercel" delay={0.05}>
          <div className="flex flex-1 flex-wrap content-center items-center gap-1.5 px-4">
            <Pill accent="#E8EAED">Next.js 15</Pill>
            <Pill accent="#61DAFB">React 19</Pill>
            <Pill accent="#3178C6">TypeScript</Pill>
            <Pill accent="#38BDF8">Tailwind v4</Pill>
            <Pill accent="#E8EAED">Motion</Pill>
            <Pill accent="#FFB454">Zustand</Pill>
            <Pill accent="#FF4154">TanStack Query</Pill>
            <Pill accent="#3E67B1">zod</Pill>
            <Pill accent="#E8EAED">shadcn/ui</Pill>
            <Pill accent="#8DC73F">Leaflet</Pill>
            <Pill accent="#A3BE8C">Recharts</Pill>
            <Pill accent="#2EAD33">Playwright</Pill>
          </div>
        </Layer>

        <VerticalPulse delay={0} />

        {/* Layer 02 — Edge */}
        <Layer index="02" name="Edge" meta="HTTP + WebSocket" deploy="Dedalus VM #4" delay={0.1}>
          <div className="flex flex-1 flex-wrap content-center items-center gap-1.5 px-4">
            <Pill accent="#009688">FastAPI</Pill>
            <Pill>uvicorn</Pill>
            <Pill accent="#A78BFA">/ws/updates</Pill>
            <Pill accent="#E92063">Pydantic v2</Pill>
            <Pill accent="#E5484D">sql_guard</Pill>
            <Pill>Atomic approvals</Pill>
            <Pill>OpenAPI → openapi-typescript</Pill>
          </div>
        </Layer>

        <VerticalPulse delay={0.2} />

        {/* Layer 03 — Agent swarm */}
        <Layer
          index="03"
          name="Agent swarm"
          meta="Python 3.12 · asyncio"
          deploy="Dedalus VMs #1 / #2 / #3"
          delay={0.15}
          emphasis="strong"
        >
          <div className="flex flex-1 items-stretch gap-2 p-3">
            <AgentCard
              color="#A3BE8C"
              name="Scout"
              model="Gemini Flash"
              lines={[
                <>5 parallel source loops — <Muted>news 60s · weather 5m · policy 15m · logistics 10m · macro 30m</Muted></>,
                <>classifies → deduplicates (72h window) → promotes to <Mono>disruption</Mono></>,
              ]}
            />
            <AgentCard
              color="#EBCB8B"
              name="Analyst"
              model="Gemini Pro"
              lines={[
                <>LISTENs on <Mono>new_disruption</Mono>; runs function-calling loop over 7 parameterized tools</>,
                <>emits <Mono>impact_reports</Mono> + <Mono>affected_shipments</Mono> + reasoning trace</>,
              ]}
            />
            <AgentCard
              color="#B48EAD"
              name="Strategist"
              model="Gemini Pro"
              lines={[
                <>LISTENs on <Mono>new_impact</Mono>; drafts 2–4 mitigation options + 3 comms each</>,
                <>all DB mutations through <Mono>OpenClaw</Mono> action layer</>,
              ]}
            />
          </div>
        </Layer>

        <VerticalPulse count={3} delay={0.4} />

        {/* Layer 04 — Data bus */}
        <Layer
          index="04"
          name="Data bus"
          meta="shared source of truth"
          deploy="Dedalus VM DB"
          delay={0.2}
        >
          <div className="flex flex-1 flex-col justify-center gap-1.5 px-4">
            <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
              <span className="text-[14px] font-medium">Postgres 16</span>
              <Muted>
                <span className="text-[11px]">14 tables · 30 ports / 50 suppliers / 40 SKUs / 200 POs / 500 shipments seeded</span>
              </Muted>
            </div>
            <div className="rounded border border-[var(--color-border)] bg-[var(--color-bg)] px-2 py-1 font-mono text-[10px] leading-[1.5] text-[var(--color-text-muted)]">
              LISTEN/NOTIFY channels:{" "}
              <span className="text-[var(--color-cat-news)]">new_signal</span> →{" "}
              <span className="text-[var(--color-cat-weather)]">new_disruption</span> →{" "}
              <span className="text-[var(--color-cat-logistics)]">new_impact</span> →{" "}
              <span className="text-[var(--color-cat-policy)]">new_mitigation</span> →{" "}
              <span className="text-[var(--color-cat-macro)]">new_approval</span>
            </div>
            <div className="flex flex-wrap gap-1.5">
              <Pill>SQLAlchemy 2.x async</Pill>
              <Pill>asyncpg</Pill>
              <Pill>Alembic migrations</Pill>
              <Pill>structlog · trace_id</Pill>
            </div>
          </div>
        </Layer>

        <VerticalPulse count={2} delay={0.6} />

        {/* Layer 05 — Inputs & AI */}
        <Layer
          index="05"
          name="Inputs & AI"
          meta="what the agents read"
          deploy="external SaaS"
          delay={0.25}
        >
          <div className="flex flex-1 items-stretch gap-2 p-3">
            <div className="flex min-w-0 flex-1 flex-col gap-1 rounded-md border border-[var(--color-border)] bg-[var(--color-surface-raised)] p-3">
              <div className="flex items-baseline justify-between gap-2">
                <span className="text-[12px] font-medium text-[var(--color-text)]">External sources</span>
                <span className="font-mono text-[9px] uppercase tracking-[0.18em] text-[var(--color-text-subtle)]">
                  → Scout
                </span>
              </div>
              <div className="text-[11px] leading-snug text-[var(--color-text-muted)]">
                <span className="text-[var(--color-text)]">Tavily</span>{" "}
                <Muted>news · policy · logistics · macro — tuned query library per source</Muted>
              </div>
              <div className="text-[11px] leading-snug text-[var(--color-text-muted)]">
                <span className="text-[var(--color-text)]">Open-Meteo</span>{" "}
                <Muted>weather · no auth · polls 30 ports + 50 supplier coords every 5 min</Muted>
              </div>
            </div>
            <div className="flex min-w-0 flex-1 flex-col gap-1 rounded-md border border-[var(--color-border)] bg-[var(--color-surface-raised)] p-3">
              <div className="flex items-baseline justify-between gap-2">
                <span className="text-[12px] font-medium text-[var(--color-text)]">LLM reasoning</span>
                <span className="font-mono text-[9px] uppercase tracking-[0.18em] text-[var(--color-text-subtle)]">
                  → all 3 agents
                </span>
              </div>
              <div className="flex flex-wrap gap-1">
                <Pill accent="#8AB4F8">Gemini 2.x Flash</Pill>
                <Pill accent="#8AB4F8">Gemini 2.x Pro</Pill>
                <Pill accent="#FFB454">OpenClaw</Pill>
              </div>
              <div className="text-[11px] leading-snug text-[var(--color-text-muted)]">
                <Mono>response_schema</Mono> · <Mono>function_calling</Mono> · <Mono>cached_contents</Mono> · SQLite offline cache for demo
              </div>
            </div>
          </div>
        </Layer>

        {/* Layer 06 — CI / DX (bottom strip, no pulse below) */}
        <div className="pt-2">
          <Layer index="06" name="CI / DX" meta="every commit" delay={0.3}>
            <div className="flex flex-1 flex-wrap content-center items-center gap-1.5 px-4">
              <Pill accent="#E8EAED">GitHub</Pill>
              <Pill accent="#E8EAED">GitHub Actions</Pill>
              <Pill accent="#EBCB8B">pre-commit</Pill>
              <Pill accent="#E5484D">gitleaks</Pill>
              <Pill accent="#DE52D9">uv</Pill>
              <Pill accent="#D7FF64">ruff</Pill>
              <Pill accent="#2A6DB0">mypy --strict</Pill>
              <Pill accent="#4A8FD4">pytest</Pill>
              <Pill accent="#2EAD33">Playwright</Pill>
              <span className="ml-auto font-mono text-[10px] text-[var(--color-text-subtle)]">
                green CI → Vercel + Dedalus deploys
              </span>
            </div>
          </Layer>
        </div>
      </div>
    </main>
  );
}
