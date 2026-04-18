import type { SourceCategory } from "@/types/schemas";

export const categoryTokens: Record<SourceCategory, { label: string; color: string; bg: string }> = {
  news: { label: "News", color: "var(--color-cat-news)", bg: "rgba(143, 174, 130, 0.12)" },
  weather: { label: "Weather", color: "var(--color-cat-weather)", bg: "rgba(156, 163, 175, 0.12)" },
  policy: { label: "Policy", color: "var(--color-cat-policy)", bg: "rgba(184, 163, 143, 0.12)" },
  logistics: { label: "Logistics", color: "var(--color-cat-logistics)", bg: "rgba(194, 164, 109, 0.12)" },
  macro: { label: "Macro", color: "var(--color-cat-macro)", bg: "rgba(189, 141, 107, 0.12)" },
  industrial: { label: "Industrial", color: "var(--color-cat-industrial)", bg: "rgba(169, 143, 122, 0.12)" },
};

export const motionSpring = {
  duration: 0.16,
  ease: "easeOut",
} as const;
