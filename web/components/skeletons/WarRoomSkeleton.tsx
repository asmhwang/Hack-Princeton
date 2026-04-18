export function WarRoomSkeleton() {
  return (
    <div className="grid h-full grid-cols-[256px_minmax(0,1fr)_300px] bg-[var(--color-bg)]">
      <div className="space-y-3 border-r border-[var(--color-border)] bg-[var(--color-surface)] p-3">
        {Array.from({ length: 4 }).map((_, index) => (
          <div key={index} className="h-24 animate-pulse rounded bg-[var(--color-surface-raised)]" />
        ))}
      </div>
      <div className="space-y-4 p-6">
        <div className="h-8 w-1/3 animate-pulse rounded bg-[var(--color-surface-raised)]" />
        <div className="h-64 animate-pulse rounded bg-[var(--color-surface)]" />
        <div className="h-48 animate-pulse rounded bg-[var(--color-surface)]" />
      </div>
      <div className="space-y-3 border-l border-[var(--color-border)] bg-[var(--color-surface)] p-4">
        {Array.from({ length: 5 }).map((_, index) => (
          <div key={index} className="h-20 animate-pulse rounded bg-[var(--color-surface-raised)]" />
        ))}
      </div>
    </div>
  );
}
