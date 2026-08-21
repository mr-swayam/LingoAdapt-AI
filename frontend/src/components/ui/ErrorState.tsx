import type { ReactNode } from "react";

/** For a page/section that failed to load entirely (distinct from
 * ErrorText in ui/form.tsx, which is for inline form-validation errors).
 * Before the V2 redesign this case was a plain `<p className="text-sm
 * text-red-300">` with no visual container in most of the app. */
export function ErrorState({
  title = "Something went wrong.",
  description,
  action,
}: {
  title?: string;
  description?: string;
  action?: ReactNode;
}) {
  return (
    <div
      role="alert"
      className="flex flex-col items-center gap-3 rounded-2xl border border-red-900 bg-red-950/30 px-6 py-10 text-center"
    >
      <p className="text-sm font-medium text-red-200">{title}</p>
      {description && <p className="max-w-sm text-sm text-red-300/80">{description}</p>}
      {action}
    </div>
  );
}
