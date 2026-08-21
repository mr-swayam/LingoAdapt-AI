import type { HTMLAttributes } from "react";

/** Replaces the hand-typed `rounded-2xl border border-slate-800
 * bg-slate-900/60 p-6` string this app repeated by hand in ~8+ places per
 * page before the V2 redesign. `hero` is for the single "next action" card
 * a page should ever have - not a general-purpose emphasis variant, so it
 * stays rare on purpose. */
const VARIANT_CLASSES = {
  default: "rounded-2xl border border-slate-800 bg-slate-900/60",
  hero: "rounded-2xl border border-cyan-800/60 bg-slate-900/80 shadow-glow-cyan",
  interactive:
    "rounded-2xl border border-slate-800 bg-slate-900/60 transition-colors duration-standard hover:border-cyan-700 hover:bg-slate-900",
  // Own complete class set (not a className override on `default`) -
  // Tailwind resolves same-property utility conflicts by stylesheet
  // order, not className source order, so swapping border/bg color via an
  // appended override string is unreliable (the exact bug Phase 12 found
  // and fixed for PrimaryButton's variants).
  admin: "rounded-2xl border border-amber-800 bg-amber-950/20",
  warning: "rounded-2xl border border-amber-800 bg-amber-950/30",
} as const;

const PADDING_CLASSES = {
  none: "",
  sm: "p-4",
  md: "p-6",
  lg: "p-8",
} as const;

export function Card({
  variant = "default",
  padding = "md",
  className = "",
  ...props
}: HTMLAttributes<HTMLDivElement> & {
  variant?: keyof typeof VARIANT_CLASSES;
  padding?: keyof typeof PADDING_CLASSES;
}) {
  return (
    <div
      {...props}
      className={`${VARIANT_CLASSES[variant]} ${PADDING_CLASSES[padding]} ${className}`}
    />
  );
}
