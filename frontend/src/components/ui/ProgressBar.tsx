export function ProgressBar({
  value,
  max,
  label,
  colorClassName = "bg-cyan-500",
}: {
  value: number;
  max: number;
  label: string;
  colorClassName?: string;
}) {
  const percent = max > 0 ? Math.min(100, Math.round((value / max) * 100)) : 0;
  return (
    <div
      className="h-2 w-full overflow-hidden rounded-full bg-slate-800"
      role="progressbar"
      aria-label={label}
      aria-valuenow={value}
      aria-valuemin={0}
      aria-valuemax={max}
    >
      <div
        className={`h-full rounded-full transition-all ${colorClassName}`}
        style={{ width: `${percent}%` }}
      />
    </div>
  );
}
