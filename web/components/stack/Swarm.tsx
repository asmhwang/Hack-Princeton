"use client";

import { motion } from "motion/react";

const EASE_OUT: [number, number, number, number] = [0.23, 1, 0.32, 1];

type Node = {
  id: string;
  label: string;
  sublabel: string;
  x: number;
  y: number;
  accent: string;
};

const NODES: Node[] = [
  { id: "scout", label: "Scout", sublabel: "Gemini Flash · 5 source loops", x: 120, y: 110, accent: "var(--color-cat-news)" },
  { id: "analyst", label: "Analyst", sublabel: "Gemini Pro · function-calling", x: 680, y: 110, accent: "var(--color-cat-logistics)" },
  { id: "strategist", label: "Strategist", sublabel: "Gemini Pro · OpenClaw actions", x: 680, y: 400, accent: "var(--color-cat-policy)" },
  { id: "bus", label: "Postgres", sublabel: "LISTEN / NOTIFY · 14 tables", x: 400, y: 255, accent: "var(--color-info)" },
  { id: "ui", label: "War Room", sublabel: "Next.js 15 · WS /ws/updates", x: 120, y: 400, accent: "var(--color-ok)" },
];

const FLOWS: {
  id: string;
  from: string;
  to: string;
  channel: string;
  color: string;
  delay: number;
}[] = [
  { id: "scout-bus",      from: "scout",      to: "bus", channel: "new_signal",      color: "#A3BE8C", delay: 0 },
  { id: "bus-analyst",    from: "bus", to: "analyst",    channel: "new_disruption",  color: "#5E81AC", delay: 0.6 },
  { id: "analyst-bus",    from: "analyst",    to: "bus", channel: "new_impact",      color: "#EBCB8B", delay: 1.2 },
  { id: "bus-strategist", from: "bus", to: "strategist", channel: "new_mitigation",  color: "#B48EAD", delay: 1.8 },
  { id: "strategist-bus", from: "strategist", to: "bus", channel: "new_approval",    color: "#D08770", delay: 2.4 },
  { id: "bus-ui",         from: "bus", to: "ui",         channel: "WS relay",        color: "#4A8FD4", delay: 2.8 },
];

function path(fromId: string, toId: string): string {
  const a = NODES.find((n) => n.id === fromId)!;
  const b = NODES.find((n) => n.id === toId)!;
  // control point pulled toward center vertical for gentle bow
  const mx = (a.x + b.x) / 2;
  const my = (a.y + b.y) / 2;
  const cx = mx + (b.y - a.y) * 0.08;
  const cy = my - (b.x - a.x) * 0.08;
  return `M ${a.x} ${a.y} Q ${cx} ${cy} ${b.x} ${b.y}`;
}

export function Swarm() {
  return (
    <div className="relative w-full">
      <svg
        viewBox="0 0 800 510"
        className="w-full h-auto"
        style={{ maxHeight: 620 }}
        aria-label="suppl.ai agent swarm architecture"
      >
        <defs>
          <filter id="soft-glow" x="-50%" y="-50%" width="200%" height="200%">
            <feGaussianBlur stdDeviation="2.5" result="blur" />
            <feMerge>
              <feMergeNode in="blur" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>
          {FLOWS.map((f) => (
            <path key={`p-${f.id}`} id={`path-${f.id}`} d={path(f.from, f.to)} fill="none" />
          ))}
        </defs>

        {/* Edges — rendered behind nodes */}
        <g stroke="var(--color-border-strong)" strokeWidth={1} fill="none" strokeDasharray="2 4">
          {FLOWS.map((f) => (
            <motion.path
              key={f.id}
              d={path(f.from, f.to)}
              initial={{ pathLength: 0, opacity: 0 }}
              whileInView={{ pathLength: 1, opacity: 1 }}
              viewport={{ once: true, margin: "-10%" }}
              transition={{ duration: 0.6, delay: 0.2 + f.delay * 0.1, ease: EASE_OUT }}
            />
          ))}
        </g>

        {/* Animated pulses — each dot loops along its path */}
        <g>
          {FLOWS.map((f) => (
            <g key={`pulse-${f.id}`}>
              <circle r={5} fill={f.color} filter="url(#soft-glow)" opacity={0.95}>
                <animateMotion
                  dur="3.6s"
                  begin={`${f.delay}s`}
                  repeatCount="indefinite"
                  rotate="auto"
                >
                  <mpath href={`#path-${f.id}`} />
                </animateMotion>
              </circle>
              <circle r={2} fill="#ffffff" opacity={0.9}>
                <animateMotion
                  dur="3.6s"
                  begin={`${f.delay}s`}
                  repeatCount="indefinite"
                >
                  <mpath href={`#path-${f.id}`} />
                </animateMotion>
              </circle>
            </g>
          ))}
        </g>

        {/* Nodes */}
        {NODES.map((n, i) => (
          <motion.g
            key={n.id}
            initial={{ opacity: 0, scale: 0.95 }}
            whileInView={{ opacity: 1, scale: 1 }}
            viewport={{ once: true, margin: "-10%" }}
            transition={{ duration: 0.32, delay: i * 0.06, ease: EASE_OUT }}
          >
            {/* outer subtle halo */}
            <circle cx={n.x} cy={n.y} r={52} fill={n.accent} opacity={0.06} />
            {/* main disc */}
            <circle
              cx={n.x}
              cy={n.y}
              r={42}
              fill="var(--color-surface-raised)"
              stroke={n.accent}
              strokeWidth={1.5}
            />
            <text
              x={n.x}
              y={n.y - 4}
              textAnchor="middle"
              fill="var(--color-text)"
              fontFamily="var(--font-sans)"
              fontSize={14}
              fontWeight={500}
            >
              {n.label}
            </text>
            <text
              x={n.x}
              y={n.y + 12}
              textAnchor="middle"
              fill="var(--color-text-subtle)"
              fontFamily="var(--font-mono)"
              fontSize={9}
            >
              {n.id}
            </text>
          </motion.g>
        ))}

        {/* Channel labels — hug each edge */}
        {FLOWS.map((f, i) => {
          const a = NODES.find((n) => n.id === f.from)!;
          const b = NODES.find((n) => n.id === f.to)!;
          const mx = (a.x + b.x) / 2;
          const my = (a.y + b.y) / 2;
          return (
            <motion.g
              key={`lbl-${f.id}`}
              initial={{ opacity: 0 }}
              whileInView={{ opacity: 1 }}
              viewport={{ once: true, margin: "-10%" }}
              transition={{ duration: 0.3, delay: 0.6 + i * 0.06, ease: EASE_OUT }}
            >
              <rect
                x={mx - 44}
                y={my - 10}
                width={88}
                height={18}
                rx={4}
                fill="var(--color-surface)"
                stroke="var(--color-border)"
              />
              <text
                x={mx}
                y={my + 3}
                textAnchor="middle"
                fontFamily="var(--font-mono)"
                fontSize={10}
                fill={f.color}
              >
                {f.channel}
              </text>
            </motion.g>
          );
        })}
      </svg>

      {/* Legend */}
      <div className="mt-6 grid grid-cols-2 md:grid-cols-3 gap-x-8 gap-y-3 text-[13px]">
        {FLOWS.map((f) => (
          <div key={`legend-${f.id}`} className="flex items-center gap-3">
            <span
              aria-hidden
              className="inline-block h-1.5 w-8 rounded-full"
              style={{ background: f.color }}
            />
            <span className="font-mono text-[var(--color-text-muted)]">{f.channel}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
