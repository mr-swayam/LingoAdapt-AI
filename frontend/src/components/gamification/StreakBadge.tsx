export function StreakBadge({ days }: { days: number }) {
  return (
    <div className="flex items-center gap-1.5 rounded-full border border-slate-800 bg-slate-950 px-3 py-1.5 text-sm text-slate-200">
      <span aria-hidden>🔥</span>
      <span>
        {days} day{days === 1 ? "" : "s"}
      </span>
    </div>
  );
}
