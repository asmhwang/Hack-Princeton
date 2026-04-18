"use client";

import { motion } from "motion/react";
import type { ReactNode } from "react";

import { Swarm } from "@/components/stack/Swarm";

const EASE_OUT: [number, number, number, number] = [0.23, 1, 0.32, 1];

type Layer = {
  group: string;
  accent: string;
  items: { name: string; detail: string; mono?: boolean }[];
};

const LAYERS: Layer[] = [
  {
    group: "Backend",
    accent: "var(--color-cat-news)",
    items: [
      { name: "Python", detail: "3.12", mono: true },
      { name: "FastAPI", detail: "async + OpenAPI" },
      { name: "SQLAlchemy", detail: "2.x async" },
      { name: "asyncpg", detail: "Postgres driver" },
      { name: "Alembic", detail: "migrations" },
      { name: "Pydantic", detail: "v2 · strict" },
      { name: "structlog", detail: "JSON + trace_id" },
      { name: "tenacity", detail: "retry w/ jitter" },
      { name: "uv", detail: "pkg manager" },
      { name: "ruff", detail: "lint + format" },
      { name: "mypy", detail: "--strict" },
      { name: "pytest", detail: "+ asyncio" },
    ],
  },
  {
    group: "Frontend",
    accent: "var(--color-cat-weather)",
    items: [
      { name: "Next.js", detail: "15 App Router", mono: true },
      { name: "React", detail: "19 · useOptimistic" },
      { name: "TypeScript", detail: "strict" },
      { name: "Tailwind CSS", detail: "v4" },
      { name: "shadcn/ui", detail: "customized" },
      { name: "Zustand", detail: "client state" },
      { name: "TanStack Query", detail: "v5 server state" },
      { name: "zod", detail: "runtime validation" },
      { name: "openapi-typescript", detail: "codegen" },
      { name: "Motion", detail: "spring physics" },
      { name: "Leaflet", detail: "+ react-leaflet" },
      { name: "Recharts", detail: "analytics" },
      { name: "Playwright", detail: "e2e" },
    ],
  },
  {
    group: "LLM",
    accent: "var(--color-cat-policy)",
    items: [
      { name: "Gemini 2.x Flash", detail: "Scout classifier" },
      { name: "Gemini 2.x Pro", detail: "Analyst + Strategist" },
      { name: "response_schema", detail: "Pydantic-bound" },
      { name: "Function calling", detail: "7 tools, no SQL" },
      { name: "cached_contents", detail: "schema ref reuse" },
      { name: "SQLite cache", detail: "offline demo" },
      { name: "OpenClaw", detail: "action layer" },
      { name: "Tavily", detail: "4 source loops" },
      { name: "Open-Meteo", detail: "weather, no auth" },
    ],
  },
  {
    group: "Infra",
    accent: "var(--color-cat-macro)",
    items: [
      { name: "4× Dedalus Machines", detail: "scout · analyst · strategist · db" },
      { name: "systemd", detail: "restart + checkpoint" },
      { name: "Postgres", detail: "16 · LISTEN/NOTIFY" },
      { name: "Vercel", detail: "frontend preview on PR" },
      { name: "GitHub Actions", detail: "CI on every PR" },
      { name: "pre-commit", detail: "ruff · mypy · gitleaks" },
      { name: "gitleaks", detail: "secret scan" },
    ],
  },
];

type Gate = { title: string; detail: string };

const GATES: Gate[] = [
  {
    title: "Zero SQL mutations",
    detail:
      "Analyst never emits raw SQL. Gemini picks from 7 parameterized read-only tools; the defense-in-depth sql_guard rejects any DROP / DELETE / UPDATE / COPY / pg_sleep / dblink at the token level.",
  },
  {
    title: "Zero emails sent",
    detail:
      "draft_communications.sent_at is always NULL — enforced by Pydantic validator. Zero SMTP libraries in the dependency graph; grep smtplib returns empty.",
  },
  {
    title: "Atomic approvals",
    detail:
      "Shipment flip + audit write + mitigation status flip wrapped in async with session.begin(). Mid-transaction failure leaves zero partial state — tested under simulated audit + flip failures.",
  },
  {
    title: "Idempotent writes",
    detail:
      "Every agent insert uses ON CONFLICT DO NOTHING or content-hash dedupe. Restart an agent mid-run, no duplicate signals.",
  },
  {
    title: "Bus auto-reconnect",
    detail:
      "Postgres LISTEN/NOTIFY drops silently on connection loss. EventBus has an explicit reconnect loop with exponential backoff — demo survives flaky wifi.",
  },
];

type Scenario = {
  id: string;
  category: string;
  accent: string;
  epicenter: string;
  exposure: string;
  mitigation: string;
};

const SCENARIOS: Scenario[] = [
  { id: "typhoon_kaia",    category: "weather",    accent: "var(--color-cat-weather)",   epicenter: "Shenzhen",        exposure: "$1.8M – $2.8M",  mitigation: "reroute via HCM" },
  { id: "busan_strike",    category: "logistics",  accent: "var(--color-cat-logistics)", epicenter: "Busan",           exposure: "$1.1M – $1.7M",  mitigation: "reroute to Kaohsiung" },
  { id: "cbam_tariff",     category: "policy",     accent: "var(--color-cat-policy)",    epicenter: "EU",              exposure: "$350K – $700K",  mitigation: "switch compliant supplier" },
  { id: "luxshare_fire",   category: "industrial", accent: "var(--color-cat-macro)",     epicenter: "Bắc Giang",       exposure: "$700K – $1.1M",  mitigation: "activate backup supplier" },
  { id: "redsea_advisory", category: "logistics",  accent: "var(--color-cat-logistics)", epicenter: "Bab-el-Mandeb",   exposure: "$2.7M – $3.5M",  mitigation: "accept delay / expedite air" },
];

const SPONSORS = [
  {
    name: "Dedalus Labs",
    tagline: "Best Agent Swarm · Containers",
    detail:
      "3 agent processes on 3 Machines, coordinating only through shared Postgres. State persists to /var/lib/supplai/state.json — kill + restart resumes cleanly.",
  },
  {
    name: "Eragon — OpenClaw",
    tagline: "Action layer for Strategist",
    detail:
      "Strategist wraps every mutation in OpenClaw Actions — supplier lookup, draft save, shipment flip, audit. Mapped to Eragon rubric: Depth / Context / Workflow.",
  },
  {
    name: "Gemini API (MLH)",
    tagline: "Flash + Pro across 3 agents",
    detail:
      "Flash for high-volume Scout classification; Pro for Analyst tool-calling loops and Strategist multi-step reasoning + drafting. All calls structured-output + cached.",
  },
  {
    name: "Tavily",
    tagline: "4 of 5 Scout source loops",
    detail:
      "News, policy, logistics, macro — each with a tuned query library documented per source. Weather goes through Open-Meteo (no auth).",
  },
];

function Section({
  id,
  eyebrow,
  title,
  subtitle,
  children,
}: {
  id: string;
  eyebrow: string;
  title: string;
  subtitle?: string;
  children: ReactNode;
}) {
  return (
    <section id={id} className="mx-auto max-w-[1120px] px-6 py-20 md:py-28">
      <motion.div
        initial={{ opacity: 0, y: 16 }}
        whileInView={{ opacity: 1, y: 0 }}
        viewport={{ once: true, margin: "-20%" }}
        transition={{ duration: 0.32, ease: EASE_OUT }}
        className="mb-10 md:mb-14"
      >
        <div className="mb-3 text-[11px] font-mono uppercase tracking-[0.18em] text-[var(--color-text-subtle)]">
          {eyebrow}
        </div>
        <h2 className="text-[28px] md:text-[36px] font-medium tracking-tight">{title}</h2>
        {subtitle ? (
          <p className="mt-2 max-w-2xl text-[var(--color-text-muted)]">{subtitle}</p>
        ) : null}
      </motion.div>
      {children}
    </section>
  );
}

function TechChip({
  label,
  detail,
  accent,
  index,
  mono,
}: {
  label: string;
  detail: string;
  accent: string;
  index: number;
  mono?: boolean;
}) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, margin: "-10%" }}
      transition={{ duration: 0.28, delay: index * 0.03, ease: EASE_OUT }}
      whileHover={{ y: -1 }}
      className="group inline-flex min-w-0 items-baseline gap-2 rounded-md border border-[var(--color-border)] bg-[var(--color-surface)] px-3 py-2 transition-colors hover:border-[var(--color-border-strong)]"
      style={{ borderLeft: `2px solid ${accent}` }}
    >
      <span className={mono ? "font-mono text-[13px]" : "text-[13px] font-medium"}>{label}</span>
      <span className="text-[11px] font-mono text-[var(--color-text-subtle)] truncate">{detail}</span>
    </motion.div>
  );
}

export default function StackPage() {
  return (
    <main className="min-h-screen bg-[var(--color-bg)] text-[var(--color-text)]">
      {/* Hero */}
      <section className="mx-auto max-w-[1120px] px-6 pt-24 md:pt-32 pb-12">
        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4, ease: EASE_OUT }}
        >
          <div className="mb-4 inline-flex items-center gap-2 rounded-full border border-[var(--color-border)] bg-[var(--color-surface)] px-3 py-1 text-[11px] font-mono text-[var(--color-text-muted)]">
            <span className="h-1.5 w-1.5 rounded-full bg-[var(--color-ok)]" aria-hidden />
            HackPrinceton Spring &apos;26
          </div>
          <h1 className="font-medium tracking-tight text-[56px] md:text-[80px] leading-[0.95]">
            suppl<span className="text-[var(--color-info)]">.</span>ai
          </h1>
          <p className="mt-5 max-w-2xl text-[18px] md:text-[22px] text-[var(--color-text)] leading-snug">
            Three agents. Zero SQL mutations. Sixty seconds to mitigation.
          </p>
          <p className="mt-3 max-w-2xl text-[var(--color-text-muted)]">
            An agentic supply-chain war-room. When a typhoon hits or a port goes on
            strike, Scout detects, Analyst quantifies, Strategist drafts — while
            the operator pours her coffee.
          </p>
        </motion.div>

        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ duration: 0.4, delay: 0.25, ease: EASE_OUT }}
          className="mt-10 grid grid-cols-2 md:grid-cols-4 gap-px rounded-lg overflow-hidden border border-[var(--color-border)] bg-[var(--color-border)]"
        >
          {[
            { k: "Agents", v: "3" },
            { k: "Dedalus VMs", v: "4" },
            { k: "DB tables", v: "14" },
            { k: "Backend tests", v: "218" },
          ].map((s) => (
            <div key={s.k} className="bg-[var(--color-surface)] px-5 py-6">
              <div className="tnum text-[28px] font-medium">{s.v}</div>
              <div className="mt-1 text-[11px] font-mono uppercase tracking-[0.14em] text-[var(--color-text-subtle)]">
                {s.k}
              </div>
            </div>
          ))}
        </motion.div>
      </section>

      {/* Swarm */}
      <Section
        id="architecture"
        eyebrow="Architecture"
        title="Three agents. One nervous system."
        subtitle="Each agent runs in its own Dedalus Machine. They never talk to each other — they write to Postgres, and LISTEN/NOTIFY wakes the next one. This is the swarm discipline."
      >
        <div className="rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] p-6 md:p-10">
          <Swarm />
        </div>
      </Section>

      {/* Layers */}
      <Section
        id="stack"
        eyebrow="Stack"
        title="Every layer earns its place."
        subtitle="No LangChain. No Redis queue. No Celery. Direct Gemini SDK, asyncio event loops, Postgres as the source of truth. Short surface area, less to break during a live demo."
      >
        <div className="space-y-6">
          {LAYERS.map((layer, li) => (
            <motion.div
              key={layer.group}
              initial={{ opacity: 0, y: 10 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true, margin: "-10%" }}
              transition={{ duration: 0.32, delay: li * 0.08, ease: EASE_OUT }}
              className="grid grid-cols-1 md:grid-cols-[180px_1fr] gap-6 md:gap-10 items-start"
            >
              <div className="flex items-baseline gap-3 md:block">
                <div
                  aria-hidden
                  className="inline-block h-2 w-2 rounded-full"
                  style={{ background: layer.accent, boxShadow: `0 0 18px ${layer.accent}` }}
                />
                <div className="md:mt-3">
                  <div className="text-[18px] font-medium">{layer.group}</div>
                  <div className="text-[11px] font-mono uppercase tracking-[0.14em] text-[var(--color-text-subtle)]">
                    {layer.items.length} deps
                  </div>
                </div>
              </div>
              <div className="flex flex-wrap gap-2">
                {layer.items.map((item, ii) => (
                  <TechChip
                    key={item.name}
                    label={item.name}
                    detail={item.detail}
                    accent={layer.accent}
                    index={ii}
                    mono={item.mono}
                  />
                ))}
              </div>
            </motion.div>
          ))}
        </div>
      </Section>

      {/* Safety gates */}
      <Section
        id="safety"
        eyebrow="Safety"
        title="Guarantees, not aspirations."
        subtitle="Every one of these is enforced by tests that fail if the guarantee breaks. No hand-waving."
      >
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {GATES.map((g, i) => (
            <motion.div
              key={g.title}
              initial={{ opacity: 0, y: 10 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true, margin: "-10%" }}
              transition={{ duration: 0.32, delay: i * 0.05, ease: EASE_OUT }}
              className="rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] p-6 transition-colors hover:border-[var(--color-border-strong)]"
            >
              <div className="mb-2 flex items-center gap-3">
                <span
                  aria-hidden
                  className="inline-flex h-5 w-5 items-center justify-center rounded-full"
                  style={{
                    background: "color-mix(in oklab, var(--color-ok) 18%, transparent)",
                    border: "1px solid color-mix(in oklab, var(--color-ok) 40%, transparent)",
                  }}
                >
                  <svg viewBox="0 0 12 12" className="h-3 w-3 text-[var(--color-ok)]">
                    <path
                      d="M2.5 6.2l2.2 2.2 4.8-4.8"
                      fill="none"
                      stroke="currentColor"
                      strokeWidth="1.6"
                      strokeLinecap="round"
                      strokeLinejoin="round"
                    />
                  </svg>
                </span>
                <h3 className="text-[16px] font-medium">{g.title}</h3>
              </div>
              <p className="text-[13px] leading-relaxed text-[var(--color-text-muted)]">{g.detail}</p>
            </motion.div>
          ))}
        </div>
      </Section>

      {/* Scenarios */}
      <Section
        id="scenarios"
        eyebrow="Demo"
        title="Five scripted scenarios, 60 seconds each."
        subtitle="Canned Tavily / Open-Meteo payloads trigger the full cascade. Deterministic. Offline-cache primed. The demo never depends on a live feed being eventful at 3am on judging day."
      >
        <div className="overflow-hidden rounded-xl border border-[var(--color-border)]">
          <div className="grid grid-cols-[120px_1fr_120px_130px_1fr] text-[11px] font-mono uppercase tracking-[0.12em] text-[var(--color-text-subtle)] border-b border-[var(--color-border)] bg-[var(--color-surface)]">
            <div className="px-4 py-3">ID</div>
            <div className="px-4 py-3">Scenario</div>
            <div className="px-4 py-3">Epicenter</div>
            <div className="px-4 py-3 text-right">Exposure</div>
            <div className="px-4 py-3">Mitigation</div>
          </div>
          {SCENARIOS.map((s, i) => (
            <motion.div
              key={s.id}
              initial={{ opacity: 0 }}
              whileInView={{ opacity: 1 }}
              viewport={{ once: true, margin: "-10%" }}
              transition={{ duration: 0.28, delay: i * 0.04, ease: EASE_OUT }}
              className="grid grid-cols-[120px_1fr_120px_130px_1fr] items-center border-t border-[var(--color-border)] bg-[var(--color-surface)] hover:bg-[var(--color-surface-raised)] transition-colors"
            >
              <div className="px-4 py-4 font-mono text-[12px] text-[var(--color-text-muted)]">{s.id}</div>
              <div className="px-4 py-4 flex items-center gap-3">
                <span
                  aria-hidden
                  className="inline-block h-1.5 w-1.5 rounded-full"
                  style={{ background: s.accent }}
                />
                <span className="text-[13px] font-medium capitalize">{s.category}</span>
              </div>
              <div className="px-4 py-4 text-[13px] text-[var(--color-text-muted)]">{s.epicenter}</div>
              <div className="px-4 py-4 text-right font-mono tnum text-[13px]">{s.exposure}</div>
              <div className="px-4 py-4 text-[13px] text-[var(--color-text-muted)]">{s.mitigation}</div>
            </motion.div>
          ))}
        </div>
      </Section>

      {/* Sponsors */}
      <Section
        id="sponsors"
        eyebrow="Sponsors"
        title="Built to be judged."
        subtitle="Every sponsor rubric maps to a load-bearing part of the system — not a badge bolted on afterwards."
      >
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {SPONSORS.map((s, i) => (
            <motion.div
              key={s.name}
              initial={{ opacity: 0, y: 8 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true, margin: "-10%" }}
              transition={{ duration: 0.3, delay: i * 0.06, ease: EASE_OUT }}
              className="rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] p-6 transition-colors hover:border-[var(--color-border-strong)]"
            >
              <div className="text-[16px] font-medium">{s.name}</div>
              <div className="mt-1 text-[11px] font-mono uppercase tracking-[0.14em] text-[var(--color-text-subtle)]">
                {s.tagline}
              </div>
              <p className="mt-4 text-[13px] leading-relaxed text-[var(--color-text-muted)]">{s.detail}</p>
            </motion.div>
          ))}
        </div>
      </Section>

      {/* Footer */}
      <footer className="mx-auto max-w-[1120px] px-6 py-12 text-[12px] font-mono text-[var(--color-text-subtle)] flex flex-wrap items-center justify-between gap-4">
        <span>Teammate C · 2026-04-18</span>
        <span>HackPrinceton Spring &apos;26</span>
      </footer>
    </main>
  );
}
