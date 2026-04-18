export function formatCurrency(value: string | number): string {
  const numeric = typeof value === "number" ? value : Number(value);
  if (!Number.isFinite(numeric)) {
    return "$0";
  }

  if (Math.abs(numeric) >= 1_000_000) {
    return `$${(numeric / 1_000_000).toFixed(1)}M`;
  }

  if (Math.abs(numeric) >= 1_000) {
    return `$${(numeric / 1_000).toFixed(0)}K`;
  }

  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 0,
  }).format(numeric);
}

export function formatRelativeTime(value: string): string {
  const then = new Date(value).getTime();
  const now = Date.now();
  const diffMinutes = Math.max(0, Math.round((now - then) / 60_000));

  if (diffMinutes < 1) {
    return "just now";
  }
  if (diffMinutes < 60) {
    return `${diffMinutes}m ago`;
  }

  const diffHours = Math.round(diffMinutes / 60);
  if (diffHours < 24) {
    return `${diffHours}h ago`;
  }

  return new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  }).format(new Date(value));
}

export function eventTime(value?: string | null): string {
  return value ?? new Date(0).toISOString();
}

export function formatPercent(value: number): string {
  return `${Math.round(value * 100)}%`;
}
