"use client";

import { motion } from "motion/react";
import type { ReactNode } from "react";

/* Emil's strong ease-out — snappier than the browser default. Used for all
 * entry animations (layers, chips, source cards). */
const EASE_OUT: [number, number, number, number] = [0.23, 1, 0.32, 1];

/* Arrow tint — muted-violet that reads clearly on the dark bg and doesn't
 * fight the category accent colors used inside each layer. */
const ARROW_DIM = "#A78BFA2C";

/* ── PulseLine ──────────────────────────────────────────────────────────
 * A top-to-bottom connector. Three stacked SVG strokes:
 *   1. Dim static dashed base — makes the connection always legible
 *   2. Halo (wide, blurred, 45% opacity)  ──╮ identical animation so the
 *   3. Main sharp pulse (narrow, drop-shadow)  ╯  halo reads as the dash's tail
 * Arrowhead sits at the bottom pointing down in the flow direction.
 * pathLength=100 normalizes the dash math, so one keyframe serves every
 * connector regardless of its actual pixel length. */

function PulseLine({ delay = 0, color }: { delay?: number; color: string }) {
  return (
    <div className="relative h-full w-full">
      <svg
        viewBox="0 0 10 40"
        preserveAspectRatio="none"
        className="absolute inset-0 h-full w-full overflow-visible"
      >
        {/* dim base */}
        <line
          x1="5" y1="0" x2="5" y2="40"
          stroke={ARROW_DIM}
          strokeWidth={1}
          strokeDasharray="2 3"
          vectorEffect="non-scaling-stroke"
        />
        {/* halo */}
        <line
          x1="5" y1="0" x2="5" y2="36"
          stroke={color}
          strokeWidth={5}
          strokeLinecap="round"
          pathLength={100}
          className="flow-line-halo"
          style={{ animationDelay: `${delay}s` }}
          vectorEffect="non-scaling-stroke"
        />
        {/* main bright pulse */}
        <line
          x1="5" y1="0" x2="5" y2="36"
          stroke={color}
          strokeWidth={2.5}
          strokeLinecap="round"
          pathLength={100}
          className="flow-line"
          style={{
            animationDelay: `${delay}s`,
            filter: `drop-shadow(0 0 4px ${color})`,
          }}
          vectorEffect="non-scaling-stroke"
        />
        {/* arrowhead pointing down */}
        <polygon
          points="1,36 9,36 5,40"
          fill={color}
          style={{ filter: `drop-shadow(0 0 3px ${color}cc)` }}
        />
      </svg>
    </div>
  );
}

/* ── Layer shell ────────────────────────────────────────────────────────
 * Wide horizontal band. Fixed-width left label column, flexible content,
 * fixed-width right deploy annotation. `emphasis="strong"` tints the
 * border with a subtle info-blue for the three agent VM layers. */

function Layer({
  index,
  name,
  meta,
  deploy,
  delay = 0,
  children,
  emphasis = "normal",
}: {
  index: string;
  name: string;
  meta?: string;
  deploy?: string;
  delay?: number;
  children: ReactNode;
  emphasis?: "normal" | "strong";
}) {
  const borderStyle =
    emphasis === "strong"
      ? { borderColor: "color-mix(in oklab, var(--color-info) 35%, var(--color-border))" }
      : undefined;
  return (
    <motion.div
      initial={{ opacity: 0, y: 6, scale: 0.985 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      transition={{ duration: 0.3, delay, ease: EASE_OUT }}
      className="relative flex min-h-0 flex-1 items-stretch overflow-hidden rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)]"
      style={borderStyle}
    >
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
      <div className="flex min-w-0 flex-1 items-stretch">{children}</div>
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
        ) : null}
      </div>
    </motion.div>
  );
}

/* ── SourceCard (one per external feed, inside Layer 01) ────────────── */

function SourceCard({
  name,
  feed,
  color,
  delay = 0,
}: {
  name: string;
  feed: string;
  color: string;
  delay?: number;
}) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 4, scale: 0.98 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      transition={{ duration: 0.26, delay, ease: EASE_OUT }}
      className="relative flex min-w-0 flex-1 flex-col justify-center gap-0.5 overflow-hidden rounded-md border border-[var(--color-border)] bg-[var(--color-surface-raised)] px-3 py-2"
      style={{ boxShadow: `inset 3px 0 0 0 ${color}, 0 0 0 1px ${color}1C` }}
    >
      <div className="text-[12px] font-medium leading-tight text-[var(--color-text)]">
        {name}
      </div>
      <div className="font-mono text-[10px] uppercase tracking-[0.1em] leading-tight text-[var(--color-text-subtle)]">
        {feed}
      </div>
    </motion.div>
  );
}

/* ── Pill helper ─────────────────────────────────────────────────────── */

function Pill({ children, accent }: { children: ReactNode; accent?: string }) {
  return (
    <span
      className="inline-flex items-center rounded border border-[var(--color-border)] bg-[var(--color-surface-raised)] px-2 py-0.5 font-mono text-[10px] text-[var(--color-text)]"
      style={
        accent
          ? { borderLeftColor: accent, borderLeftWidth: 2, borderLeftStyle: "solid" }
          : undefined
      }
    >
      {children}
    </span>
  );
}

function Mono({ children }: { children: ReactNode }) {
  return <span className="font-mono text-[11px] text-[var(--color-text)]">{children}</span>;
}

function Muted({ children }: { children: ReactNode }) {
  return <span className="text-[11px] text-[var(--color-text-muted)]">{children}</span>;
}

/* ── Connector rows ─────────────────────────────────────────────────── */

/* Single centered arrow (used between solo layers 02→07). */
function SingleArrow({ delay, color }: { delay: number; color: string }) {
  return (
    <div className="flex h-7 flex-none items-stretch justify-center">
      <div className="w-10">
        <PulseLine delay={delay} color={color} />
      </div>
    </div>
  );
}

/* Fan of 5 arrows, one per source box in the row above. The outer
 * left/right spacers match the Layer shell's 160px/170px label columns so
 * each arrow sits directly under its source card. */
function SourceFan({
  sources,
}: {
  sources: { color: string; delay: number }[];
}) {
  return (
    <div className="flex h-7 flex-none items-stretch">
      <div className="w-[160px] flex-none" aria-hidden />
      <div className="flex min-w-0 flex-1 items-stretch gap-2 px-2">
        {sources.map((s, i) => (
          <div key={i} className="relative min-w-0 flex-1">
            <PulseLine delay={s.delay} color={s.color} />
          </div>
        ))}
      </div>
      <div className="w-[170px] flex-none" aria-hidden />
    </div>
  );
}

/* ── Page ────────────────────────────────────────────────────────────── */

export default function StackPage() {
  const sources = [
    { name: "Tavily",     feed: "news",      color: "#A3BE8C" },
    { name: "Tavily",     feed: "policy",    color: "#B48EAD" },
    { name: "Tavily",     feed: "logistics", color: "#EBCB8B" },
    { name: "Tavily",     feed: "macro",     color: "#D08770" },
    { name: "Open-Meteo", feed: "weather",   color: "#5E81AC" },
  ];

  const fanDelays = sources.map((s, i) => ({
    color: s.color,
    delay: i * 0.22, // staggered entries so the 5 arrows read as continuous rain
  }));

  return (
    <main className="flex h-screen w-screen flex-col overflow-hidden bg-[var(--color-bg)] text-[var(--color-text)]">
      {/* Header */}
      <motion.header
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ duration: 0.28, ease: EASE_OUT }}
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
          <span>
            data flows <span className="text-[var(--color-text)]">↓</span> downward
          </span>
          <span>
            <span className="tnum text-[var(--color-text)]">7</span> layers
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
      <div className="mx-auto flex min-h-0 w-full max-w-[1440px] flex-1 flex-col px-6 py-4">
        {/* Layer 01 — External sources (5 sub-cards) */}
        <Layer
          index="01"
          name="External sources"
          meta="what the system reads"
          deploy="external SaaS"
          delay={0}
        >
          <div className="flex flex-1 items-stretch gap-2 px-2 py-2">
            {sources.map((src, i) => (
              <SourceCard
                key={`${src.name}-${src.feed}`}
                name={src.name}
                feed={src.feed}
                color={src.color}
                delay={0.04 + i * 0.04}
              />
            ))}
          </div>
        </Layer>

        {/* 5 arrows — one per source, each in its own accent color */}
        <SourceFan sources={fanDelays} />

        {/* Layer 02 — Data bus */}
        <Layer
          index="02"
          name="Data bus"
          meta="shared source of truth"
          deploy="Dedalus DB VM"
          delay={0.08}
        >
          <div className="flex flex-1 flex-wrap content-center items-center gap-3 px-4">
            <span className="text-[14px] font-medium">Postgres 16</span>
            <Muted>
              <Mono>LISTEN / NOTIFY</Mono> · 14 tables
            </Muted>
            <div className="flex items-center gap-1 rounded border border-[var(--color-border)] bg-[var(--color-bg)] px-2 py-1 font-mono text-[10px] text-[var(--color-text-muted)]">
              <span className="text-[var(--color-cat-news)]">new_signal</span>
              <span>→</span>
              <span className="text-[var(--color-cat-weather)]">new_disruption</span>
              <span>→</span>
              <span className="text-[var(--color-cat-logistics)]">new_impact</span>
              <span>→</span>
              <span className="text-[var(--color-cat-policy)]">new_mitigation</span>
              <span>→</span>
              <span className="text-[var(--color-cat-macro)]">new_approval</span>
            </div>
            <div className="ml-auto flex flex-wrap items-center gap-1">
              <Pill>SQLAlchemy 2.x</Pill>
              <Pill>asyncpg</Pill>
              <Pill>Alembic</Pill>
            </div>
          </div>
        </Layer>

        <SingleArrow delay={0.15} color="#A3BE8C" />

        {/* Layer 03 — Scout VM */}
        <Layer
          index="03"
          name="Scout VM"
          meta="Python 3.12 · asyncio"
          deploy="Dedalus VM #1"
          delay={0.12}
          emphasis="strong"
        >
          <div className="flex flex-1 flex-wrap content-center items-center gap-3 px-4">
            <span className="text-[14px] font-medium" style={{ color: "#A3BE8C" }}>
              Scout agent
            </span>
            <Pill accent="#8AB4F8">Gemini Flash</Pill>
            <Muted>
              5 parallel source loops — classifies, deduplicates (72h window), promotes to{" "}
              <Mono>disruption</Mono>
            </Muted>
          </div>
        </Layer>

        <SingleArrow delay={0.35} color="#EBCB8B" />

        {/* Layer 04 — Analyst VM */}
        <Layer
          index="04"
          name="Analyst VM"
          meta="Python 3.12 · asyncio"
          deploy="Dedalus VM #2"
          delay={0.16}
          emphasis="strong"
        >
          <div className="flex flex-1 flex-wrap content-center items-center gap-3 px-4">
            <span className="text-[14px] font-medium" style={{ color: "#EBCB8B" }}>
              Analyst agent
            </span>
            <Pill accent="#8AB4F8">Gemini Pro</Pill>
            <Muted>
              LISTEN <Mono>new_disruption</Mono> → tool-calling loop over 7 parameterized reads →
              emits <Mono>impact_reports</Mono>
            </Muted>
          </div>
        </Layer>

        <SingleArrow delay={0.55} color="#B48EAD" />

        {/* Layer 05 — Strategist VM */}
        <Layer
          index="05"
          name="Strategist VM"
          meta="Python 3.12 · asyncio"
          deploy="Dedalus VM #3"
          delay={0.2}
          emphasis="strong"
        >
          <div className="flex flex-1 flex-wrap content-center items-center gap-3 px-4">
            <span className="text-[14px] font-medium" style={{ color: "#B48EAD" }}>
              Strategist agent
            </span>
            <Pill accent="#8AB4F8">Gemini Pro</Pill>
            <Pill accent="#FFB454">OpenClaw</Pill>
            <Muted>
              LISTEN <Mono>new_impact</Mono> → drafts 2–4 mitigation options + 3 comms each →
              atomic DB mutations
            </Muted>
          </div>
        </Layer>

        <SingleArrow delay={0.75} color="#5E81AC" />

        {/* Layer 06 — Edge */}
        <Layer
          index="06"
          name="Edge"
          meta="HTTP + WebSocket"
          deploy="Dedalus VM #4"
          delay={0.24}
        >
          <div className="flex flex-1 flex-wrap content-center items-center gap-1.5 px-4">
            <Pill accent="#009688">FastAPI</Pill>
            <Pill>uvicorn</Pill>
            <Pill accent="#A78BFA">/ws/updates</Pill>
            <Pill accent="#E92063">Pydantic v2</Pill>
            <Pill accent="#E5484D">sql_guard</Pill>
            <Pill>atomic approvals</Pill>
            <Pill>OpenAPI → openapi-typescript</Pill>
          </div>
        </Layer>

        <SingleArrow delay={0.95} color="#E8EAED" />

        {/* Layer 07 — Client */}
        <Layer
          index="07"
          name="Client"
          meta="browser"
          deploy="Vercel"
          delay={0.28}
        >
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
      </div>
    </main>
  );
}
