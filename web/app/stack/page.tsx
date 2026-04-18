"use client";

import { motion } from "motion/react";
import type { ReactNode } from "react";

const EASE_OUT: [number, number, number, number] = [0.23, 1, 0.32, 1];

const C = {
  agents: "#A3BE8C",
  bus: "#4A8FD4",
  llm: "#B48EAD",
  api: "#5E81AC",
  frontend: "#EBCB8B",
  platform: "#D08770",
  ext: "#8B9098",
} as const;

/**
 * A line with a traveling pulse. Base line dim + always visible; a short
 * bright dash travels along it via animated stroke-dashoffset. Uses
 * vectorEffect="non-scaling-stroke" so strokes stay crisp when the SVG
 * stretches to fill non-square containers.
 */
function Pulse({
  orientation,
  accent,
  dur = 2.6,
  delay = 0,
}: {
  orientation: "vertical" | "horizontal";
  accent: string;
  dur?: number;
  delay?: number;
}) {
  const id = `glow-${accent.replace("#", "")}-${orientation}-${Math.round(delay * 10)}`;
  const isV = orientation === "vertical";
  const d = isV ? "M 50 0 L 50 100" : "M 0 50 L 100 50";
  return (
    <div className="relative h-full w-full">
      <svg
        viewBox="0 0 100 100"
        preserveAspectRatio="none"
        className="absolute inset-0 h-full w-full overflow-visible"
      >
        <defs>
          <filter id={id} x="-50%" y="-50%" width="200%" height="200%">
            <feGaussianBlur stdDeviation="1.2" result="b" />
            <feMerge>
              <feMergeNode in="b" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>
        </defs>
        <path
          d={d}
          stroke="var(--color-border-strong)"
          strokeWidth={1}
          fill="none"
          vectorEffect="non-scaling-stroke"
        />
        <path
          d={d}
          stroke={accent}
          strokeWidth={2}
          fill="none"
          strokeLinecap="round"
          strokeDasharray="8 140"
          vectorEffect="non-scaling-stroke"
          filter={`url(#${id})`}
        >
          <animate
            attributeName="stroke-dashoffset"
            from={-1 * delay * 40}
            to={-148 - delay * 40}
            dur={`${dur}s`}
            repeatCount="indefinite"
          />
        </path>
      </svg>
    </div>
  );
}

function Card({
  accent,
  label,
  title,
  children,
  delay = 0,
}: {
  accent: string;
  label: string;
  title: string;
  children: ReactNode;
  delay?: number;
}) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.32, delay, ease: EASE_OUT }}
      className="relative flex h-full min-h-0 flex-col overflow-hidden rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)]"
    >
      <div
        aria-hidden
        className="pointer-events-none absolute inset-y-0 left-0 w-40"
        style={{
          background: `radial-gradient(circle at 0% 50%, ${accent}1f 0%, transparent 70%)`,
        }}
      />
      <div
        aria-hidden
        className="absolute inset-y-0 left-0 w-[2px]"
        style={{ background: accent }}
      />
      <div className="relative flex min-h-0 flex-1 flex-col gap-2 p-3">
        <div className="flex items-baseline justify-between gap-2">
          <span
            className="font-mono text-[9px] uppercase tracking-[0.22em]"
            style={{ color: accent }}
          >
            {label}
          </span>
        </div>
        <div className="text-[15px] font-medium leading-tight">{title}</div>
        <div className="min-h-0 flex-1 overflow-hidden text-[11.5px] leading-relaxed">
          {children}
        </div>
      </div>
    </motion.div>
  );
}

function Mono({ children }: { children: ReactNode }) {
  return <span className="font-mono text-[11px] text-[var(--color-text)]">{children}</span>;
}

function Muted({ children }: { children: ReactNode }) {
  return <span className="text-[var(--color-text-muted)]">{children}</span>;
}

function Pill({ children }: { children: ReactNode }) {
  return (
    <span className="inline-block rounded border border-[var(--color-border)] bg-[var(--color-surface-raised)] px-1.5 py-0.5 font-mono text-[10px] text-[var(--color-text)]">
      {children}
    </span>
  );
}

function AgentBlock({
  color,
  name,
  model,
  body,
}: {
  color: string;
  name: string;
  model: string;
  body: ReactNode;
}) {
  return (
    <div className="flex min-h-0 flex-1 flex-col gap-1 border-t border-[var(--color-border)] pt-2 first:border-t-0 first:pt-0">
      <div className="flex items-baseline justify-between gap-2">
        <span className="text-[13px] font-medium" style={{ color }}>
          {name}
        </span>
        <span className="font-mono text-[10px] text-[var(--color-text-subtle)]">{model}</span>
      </div>
      <div className="text-[11px] leading-snug text-[var(--color-text-muted)]">{body}</div>
    </div>
  );
}

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
            Tech stack
          </span>
          <h1 className="text-[16px] font-medium tracking-tight">
            suppl<span className="text-[var(--color-info)]">.</span>ai
          </h1>
        </div>
        <div className="font-mono text-[10px] uppercase tracking-[0.14em] text-[var(--color-text-subtle)]">
          3 agents · 14 tables · 6 layers · 48 deps · 218 tests
        </div>
      </motion.header>

      {/* Diagram grid */}
      <div className="relative mx-auto flex min-h-0 w-full max-w-[1440px] flex-1 flex-col px-6 py-5">
        <div
          className="grid min-h-0 flex-1 grid-cols-12 gap-x-3"
          style={{
            gridTemplateRows:
              "auto 16px minmax(0, 1fr) 16px minmax(0, 0.55fr) 16px auto",
          }}
        >
          {/* Row 1 — External inputs (centered across cols 4-9) */}
          <div className="col-span-6 col-start-4 row-start-1">
            <Card accent={C.ext} label="Inputs" title="External sources" delay={0.05}>
              <div className="flex flex-wrap items-baseline gap-x-4 gap-y-1">
                <span className="text-[12px]">Tavily</span>
                <Muted>
                  <span className="font-mono text-[10px]">
                    news · policy · logistics · macro
                  </span>
                </Muted>
                <span className="text-[12px]">Open-Meteo</span>
                <Muted>
                  <span className="font-mono text-[10px]">weather · no auth</span>
                </Muted>
              </div>
            </Card>
          </div>

          {/* Row 2 — vertical pulse from external down to bus */}
          <div className="col-span-2 col-start-6 row-start-2">
            <Pulse orientation="vertical" accent={C.agents} />
          </div>

          {/* Row 3 — Agents | H-pulse | Bus | H-pulse | LLM */}
          <div className="col-span-3 row-start-3">
            <Card
              accent={C.agents}
              label="Agents"
              title="Three specialized processes"
              delay={0.1}
            >
              <div className="flex min-h-0 flex-1 flex-col gap-2">
                <AgentBlock
                  color={C.agents}
                  name="Scout"
                  model="Gemini Flash"
                  body={
                    <>
                      5 parallel source loops —{" "}
                      <Muted>news 60s · weather 5m · policy 15m · logistics 10m · macro 30m</Muted>
                    </>
                  }
                />
                <AgentBlock
                  color="#EBCB8B"
                  name="Analyst"
                  model="Gemini Pro"
                  body={
                    <>
                      function-calling loop over <Mono>7 analyst tools</Mono>; produces impact report + reasoning trace
                    </>
                  }
                />
                <AgentBlock
                  color="#B48EAD"
                  name="Strategist"
                  model="Gemini Pro"
                  body={
                    <>
                      drafts 2–4 mitigation options + 3 comms per option via <Mono>OpenClaw</Mono> action layer
                    </>
                  }
                />
              </div>
            </Card>
          </div>

          {/* HPulse: agents → bus (3 lines, one per agent) */}
          <div className="col-span-1 row-start-3 flex min-h-0 flex-col justify-around py-4">
            <div className="h-3 w-full">
              <Pulse orientation="horizontal" accent={C.agents} delay={0} />
            </div>
            <div className="h-3 w-full">
              <Pulse orientation="horizontal" accent="#EBCB8B" delay={0.6} />
            </div>
            <div className="h-3 w-full">
              <Pulse orientation="horizontal" accent="#B48EAD" delay={1.2} />
            </div>
          </div>

          {/* Bus card */}
          <div className="col-span-4 row-start-3">
            <Card accent={C.bus} label="Runtime" title="Postgres 16 — the bus" delay={0.15}>
              <div className="flex min-h-0 flex-1 flex-col gap-2">
                <div className="text-[11px] text-[var(--color-text-muted)]">
                  Agents talk only through shared DB + <Mono>LISTEN / NOTIFY</Mono>. No RPC. No queue. Swarm discipline.
                </div>
                <div className="rounded border border-[var(--color-border)] bg-[var(--color-bg)] p-2 font-mono text-[10px] leading-[1.6] text-[var(--color-text-muted)]">
                  <div>
                    <span className="text-[var(--color-cat-news)]">new_signal</span>
                    <span className="text-[var(--color-text-subtle)]"> → </span>
                    <span className="text-[var(--color-cat-weather)]">new_disruption</span>
                  </div>
                  <div>
                    <span className="text-[var(--color-text-subtle)]">→ </span>
                    <span className="text-[var(--color-cat-logistics)]">new_impact</span>
                    <span className="text-[var(--color-text-subtle)]"> → </span>
                    <span className="text-[var(--color-cat-policy)]">new_mitigation</span>
                  </div>
                  <div>
                    <span className="text-[var(--color-text-subtle)]">→ </span>
                    <span className="text-[var(--color-cat-macro)]">new_approval</span>
                  </div>
                </div>
                <div className="mt-auto flex flex-wrap gap-1.5">
                  <Pill>SQLAlchemy 2.x async</Pill>
                  <Pill>asyncpg</Pill>
                  <Pill>Alembic</Pill>
                  <Pill>Pydantic v2</Pill>
                  <Pill>structlog</Pill>
                </div>
              </div>
            </Card>
          </div>

          {/* HPulse: bus ↔ llm (2 lines, opposite directions) */}
          <div className="col-span-1 row-start-3 flex min-h-0 flex-col justify-center gap-3 py-4">
            <div className="h-3 w-full">
              <Pulse orientation="horizontal" accent={C.llm} delay={0.3} />
            </div>
            <div className="h-3 w-full">
              <Pulse orientation="horizontal" accent={C.bus} delay={0.9} />
            </div>
          </div>

          {/* LLM card */}
          <div className="col-span-3 row-start-3">
            <Card accent={C.llm} label="LLM" title="Gemini 2.x — no text-to-SQL" delay={0.2}>
              <div className="flex min-h-0 flex-1 flex-col gap-1.5">
                <div className="flex items-baseline gap-2">
                  <Pill>Flash</Pill>
                  <Muted>Scout classifier</Muted>
                </div>
                <div className="flex items-baseline gap-2">
                  <Pill>Pro</Pill>
                  <Muted>Analyst + Strategist reasoning</Muted>
                </div>
                <div className="mt-1 flex flex-wrap gap-1">
                  <Pill>response_schema</Pill>
                  <Pill>function calling</Pill>
                  <Pill>cached_contents</Pill>
                  <Pill>SQLite cache</Pill>
                </div>
                <div className="mt-auto text-[10px] text-[var(--color-text-subtle)]">
                  <Mono>google-genai</Mono> · retry via <Mono>tenacity</Mono> · offline cache for demo
                </div>
              </div>
            </Card>
          </div>

          {/* Row 4 — vpulse down to API/Frontend */}
          <div className="col-span-2 col-start-6 row-start-4">
            <Pulse orientation="vertical" accent={C.bus} delay={0.2} />
          </div>

          {/* Row 5 — API + Frontend */}
          <div className="col-span-6 row-start-5">
            <Card accent={C.api} label="API · safety" title="FastAPI + WebSocket" delay={0.25}>
              <div className="flex min-h-0 flex-1 flex-col gap-1.5">
                <div className="flex flex-wrap gap-1">
                  <Pill>uvicorn</Pill>
                  <Pill>/ws/updates</Pill>
                  <Pill>OpenAPI</Pill>
                  <Pill>openapi-typescript</Pill>
                </div>
                <div className="text-[11px] leading-snug text-[var(--color-text-muted)]">
                  <Mono>sql_guard</Mono> rejects non-SELECT + DoS functions (token-level, 22 tests).
                  Atomic approvals: shipment flip + audit + status flip wrapped in one transaction.
                </div>
                <div className="mt-auto flex flex-wrap gap-1">
                  <Pill>zero SQL mutations</Pill>
                  <Pill>zero emails sent</Pill>
                  <Pill>all-or-nothing</Pill>
                  <Pill>idempotent writes</Pill>
                </div>
              </div>
            </Card>
          </div>

          <div className="col-span-6 row-start-5">
            <Card
              accent={C.frontend}
              label="Frontend"
              title="Next.js 15 · React 19 · Tailwind v4"
              delay={0.3}
            >
              <div className="flex min-h-0 flex-1 flex-col gap-1.5">
                <div className="text-[11px] text-[var(--color-text-muted)]">
                  Dense, dark, detail-obsessed. No default shadcn stacks; heavy customization. Motion for spring physics + layout morphs on approve.
                </div>
                <div className="flex flex-wrap gap-1">
                  <Pill>Motion</Pill>
                  <Pill>Zustand</Pill>
                  <Pill>TanStack Query</Pill>
                  <Pill>zod</Pill>
                  <Pill>shadcn/ui</Pill>
                  <Pill>Leaflet</Pill>
                  <Pill>Recharts</Pill>
                  <Pill>Playwright</Pill>
                </div>
                <div className="mt-auto text-[10px] text-[var(--color-text-subtle)]">
                  TS <Mono>strict</Mono> · App Router · Turbopack · prefers-reduced-motion respected
                </div>
              </div>
            </Card>
          </div>

          {/* Row 6 — vpulse down to platform */}
          <div className="col-span-2 col-start-6 row-start-6">
            <Pulse orientation="vertical" accent={C.platform} delay={0.5} />
          </div>

          {/* Row 7 — Platform strip (full width) */}
          <div className="col-span-12 row-start-7">
            <Card
              accent={C.platform}
              label="Platform & DX"
              title="Persistent VMs · trunk-based CI · gates on every commit"
              delay={0.35}
            >
              <div className="flex flex-wrap items-center gap-1.5">
                <Pill>4× Dedalus Machines</Pill>
                <Pill>systemd</Pill>
                <Pill>/var/lib/supplai/state.json</Pill>
                <Pill>Vercel</Pill>
                <Pill>GitHub Actions</Pill>
                <Pill>uv</Pill>
                <Pill>ruff</Pill>
                <Pill>mypy --strict</Pill>
                <Pill>pytest</Pill>
                <Pill>pre-commit</Pill>
                <Pill>gitleaks</Pill>
              </div>
            </Card>
          </div>
        </div>
      </div>
    </main>
  );
}
