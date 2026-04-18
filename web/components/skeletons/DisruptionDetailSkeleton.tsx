export function DisruptionDetailSkeleton() {
  return (
    <div className="space-y-5 p-6">
      <div className="h-24 animate-pulse rounded bg-[var(--color-surface)]" />
      <div className="grid grid-cols-[minmax(0,1fr)_320px] gap-5">
        <div className="h-96 animate-pulse rounded bg-[var(--color-surface)]" />
        <div className="space-y-3">
          {Array.from({ length: 3 }).map((_, index) => (
            <div key={index} className="h-32 animate-pulse rounded bg-[var(--color-surface)]" />
          ))}
        </div>
      </div>
    </div>
  );
}
