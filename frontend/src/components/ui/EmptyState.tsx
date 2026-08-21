import type { ReactNode } from "react";

/** Replaces the ~8 independently-authored empty-state strings this app had
 * before the V2 redesign (each consistent in color by convention, but not
 * componentized - no icon slot, no consistent CTA pattern). */
export function EmptyState({
  icon,
  title,
  description,
  action,
}: {
  icon?: ReactNode;
  title: string;
  description?: string;
  action?: ReactNode;
}) {
  return (
    <div className="flex flex-col items-center gap-3 rounded-2xl border border-dashed border-slate-800 bg-slate-900/30 px-6 py-10 text-center">
      {icon && (
        <div className="text-3xl" aria-hidden="true">
          {icon}
        </div>
      )}
      <p className="text-sm font-medium text-slate-200">{title}</p>
      {description && <p className="max-w-sm text-sm text-slate-400">{description}</p>}
      {action}
    </div>
  );
}
