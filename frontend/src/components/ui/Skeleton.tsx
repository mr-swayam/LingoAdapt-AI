/** Replaces the ad hoc `<p>Loading…</p>` text this app repeated
 * independently across 14 pages/components before the V2 redesign, with a
 * content-shaped placeholder instead. Intentionally a small set of shape
 * primitives (not bespoke per-page skeletons) - composed by callers. */
export function Skeleton({ className = "" }: { className?: string }) {
  return <div className={`animate-pulse rounded-md bg-slate-800/80 ${className}`} aria-hidden="true" />;
}

export function SkeletonText({ lines = 1, className = "" }: { lines?: number; className?: string }) {
  return (
    <div className={`flex flex-col gap-2 ${className}`} aria-hidden="true">
      {Array.from({ length: lines }).map((_, i) => (
        <Skeleton key={i} className={`h-3 ${i === lines - 1 && lines > 1 ? "w-2/3" : "w-full"}`} />
      ))}
    </div>
  );
}

export function SkeletonCard({ className = "" }: { className?: string }) {
  return (
    <div
      className={`flex flex-col gap-3 rounded-2xl border border-slate-800 bg-slate-900/60 p-6 ${className}`}
      aria-hidden="true"
    >
      <Skeleton className="h-4 w-1/3" />
      <Skeleton className="h-3 w-full" />
      <Skeleton className="h-3 w-5/6" />
    </div>
  );
}

/** Use for a full page/section's loading state - carries the accessible
 * "Loading" announcement the individual shapes above (aria-hidden, purely
 * decorative) deliberately don't. */
export function LoadingRegion({
  label = "Loading",
  children,
}: {
  label?: string;
  children: React.ReactNode;
}) {
  return (
    <div role="status" aria-label={label}>
      {children}
    </div>
  );
}
