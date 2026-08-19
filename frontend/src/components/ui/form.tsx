import type {
  InputHTMLAttributes,
  LabelHTMLAttributes,
  SelectHTMLAttributes,
  TextareaHTMLAttributes,
} from "react";

export function Field({
  label,
  htmlFor,
  children,
}: {
  label: string;
  htmlFor: string;
  children: React.ReactNode;
}) {
  return (
    <div className="flex flex-col gap-1.5">
      <label htmlFor={htmlFor} className="text-sm font-medium text-slate-300">
        {label}
      </label>
      {children}
    </div>
  );
}

const controlClasses =
  "rounded-lg border border-slate-800 bg-slate-950 px-3 py-2 text-sm text-slate-100 " +
  "placeholder:text-slate-600 focus:border-cyan-500 focus:outline-none focus:ring-1 focus:ring-cyan-500";

export function TextInput(props: InputHTMLAttributes<HTMLInputElement>) {
  return <input {...props} className={`${controlClasses} ${props.className ?? ""}`} />;
}

export function TextArea(props: TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return <textarea {...props} className={`${controlClasses} ${props.className ?? ""}`} />;
}

export function Select(props: SelectHTMLAttributes<HTMLSelectElement>) {
  return <select {...props} className={`${controlClasses} ${props.className ?? ""}`} />;
}

export function Label(props: LabelHTMLAttributes<HTMLLabelElement>) {
  return <label {...props} className={`text-sm font-medium text-slate-300 ${props.className ?? ""}`} />;
}

// Tailwind utility classes with equal specificity don't resolve by string
// order - which one "wins" depends on where each is declared in the
// compiled stylesheet, not where it appears in a className attribute. A
// caller passing className="text-slate-200" to override this component's
// own text-slate-950 was silently losing that fight (a real, live bug
// found in Phase 13's accessibility audit - the resulting near-invisible
// text passed unnoticed until an automated contrast scan caught it). Each
// variant below is a complete, non-overlapping class set instead, so
// there's never a same-property conflict to resolve.
const VARIANT_CLASSES = {
  primary:
    "bg-cyan-500 text-slate-950 hover:bg-cyan-400 disabled:bg-slate-700 disabled:text-slate-300",
  secondary:
    "bg-slate-800 text-slate-200 hover:bg-slate-700 disabled:bg-slate-900 disabled:text-slate-500",
  danger:
    "bg-red-500 text-slate-950 hover:bg-red-400 disabled:bg-slate-700 disabled:text-slate-300",
} as const;

export function PrimaryButton({
  variant = "primary",
  ...props
}: React.ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: keyof typeof VARIANT_CLASSES;
}) {
  return (
    <button
      {...props}
      className={
        "rounded-lg px-4 py-2 text-sm font-semibold transition-colors disabled:cursor-not-allowed " +
        VARIANT_CLASSES[variant] +
        " " +
        (props.className ?? "")
      }
    />
  );
}

export function ErrorText({ children }: { children: React.ReactNode }) {
  if (!children) return null;
  return <p className="rounded-lg border border-red-900 bg-red-950/50 px-3 py-2 text-sm text-red-300">{children}</p>;
}
