"use client";

import { useRouter } from "next/navigation";

import { PrimaryButton } from "@/components/ui/form";

/** Root error boundary - before the V2 redesign, an unhandled render error
 * anywhere in the app fell through to Next's unbranded default error UI.
 * Next.js requires this file to be a client component. */
export default function GlobalError({ reset }: { error: Error & { digest?: string }; reset: () => void }) {
  const router = useRouter();
  return (
    <div className="flex flex-1 flex-col items-center justify-center gap-4 px-6 text-center">
      <p className="text-lg font-semibold text-slate-100">Something went wrong.</p>
      <p className="text-sm text-slate-400">Try again, or head back to the dashboard.</p>
      <div className="flex gap-3">
        <PrimaryButton onClick={reset}>Try again</PrimaryButton>
        <PrimaryButton variant="secondary" onClick={() => router.push("/dashboard")}>
          Dashboard
        </PrimaryButton>
      </div>
    </div>
  );
}
