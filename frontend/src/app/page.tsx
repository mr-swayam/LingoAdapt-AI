"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect } from "react";

import { useAuth } from "@/lib/auth-context";

export default function Home() {
  const router = useRouter();
  const { status } = useAuth();

  useEffect(() => {
    if (status === "authenticated") {
      router.replace("/dashboard");
    }
  }, [status, router]);

  if (status === "loading" || status === "authenticated") {
    return (
      <div className="flex flex-1 items-center justify-center px-6">
        <p className="text-slate-400">Loading…</p>
      </div>
    );
  }

  return (
    <div className="flex flex-1 flex-col items-center justify-center px-6 text-center">
      <div className="flex max-w-xl flex-col items-center gap-6">
        <h1 className="text-4xl font-semibold tracking-tight text-slate-50">
          Learn a language with an AI tutor that adapts to you
        </h1>
        <p className="text-lg text-slate-400">
          Short, gamified lessons paired with a persistent learner model — so practice always
          targets what you actually need to work on.
        </p>
        <div className="flex gap-3">
          <Link
            href="/signup"
            className="rounded-lg bg-cyan-500 px-5 py-2.5 text-sm font-semibold text-slate-950 transition-colors hover:bg-cyan-400"
          >
            Get started
          </Link>
          <Link
            href="/login"
            className="rounded-lg border border-slate-800 px-5 py-2.5 text-sm font-semibold text-slate-200 transition-colors hover:border-slate-700 hover:bg-slate-900"
          >
            Log in
          </Link>
        </div>
      </div>
    </div>
  );
}
