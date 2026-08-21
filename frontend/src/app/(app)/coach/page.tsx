"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { Card } from "@/components/ui/Card";
import { ErrorState } from "@/components/ui/ErrorState";
import { SkeletonCard } from "@/components/ui/Skeleton";
import { useRequireAuth } from "@/hooks/use-require-auth";
import { ApiError, getCoachInsight, refreshCoachInsight } from "@/lib/coach-api";
import type { CoachResponse } from "@/types/coach";

/** V3.1 AI Learning Coach. Every fact behind the insight is real learner
 * data (see backend coach_service.py's observed_facts/calculated_trends
 * split) - only the summary/focus-area framing and the recommended action
 * are AI-generated, and the recommended action is the only field allowed
 * to be a genuine synthesized suggestion rather than a grounded restatement. */
export default function CoachPage() {
  const { status, accessToken } = useRequireAuth();
  const [response, setResponse] = useState<CoachResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [refreshing, setRefreshing] = useState(false);
  const [refreshNotice, setRefreshNotice] = useState<string | null>(null);

  useEffect(() => {
    if (status !== "authenticated" || !accessToken) return;
    let cancelled = false;
    getCoachInsight(accessToken)
      .then((data) => {
        if (!cancelled) setResponse(data);
      })
      .catch((err) => {
        if (cancelled) return;
        setError(err instanceof ApiError ? err.message : "Couldn't load your coach insight.");
      });
    return () => {
      cancelled = true;
    };
  }, [status, accessToken]);

  async function handleRefresh() {
    if (!accessToken) return;
    setRefreshing(true);
    setRefreshNotice(null);
    try {
      const data = await refreshCoachInsight(accessToken);
      setResponse(data);
    } catch (err) {
      // Deliberately never calls setError() here: a failed refresh (a 429
      // cooldown, or a transient AI-provider failure) must not discard the
      // already-successfully-loaded insight still on screen - only the
      // initial load's own failure should replace the page with ErrorState.
      if (err instanceof ApiError && err.status === 429) {
        setRefreshNotice("Please wait a few minutes before refreshing again.");
      } else {
        setRefreshNotice(
          err instanceof ApiError ? err.message : "Couldn't refresh your coach insight - please try again.",
        );
      }
    } finally {
      setRefreshing(false);
    }
  }

  return (
    <div className="flex flex-1 flex-col items-center px-6 py-12">
      <div className="flex w-full max-w-xl flex-col gap-6">
        <div>
          <h1 className="text-2xl font-semibold text-slate-50">Your AI Coach</h1>
          <p className="mt-1 text-sm text-slate-400">
            A grounded read on how you&rsquo;re doing, based on your real activity - not a
            generic tip.
          </p>
        </div>

        {status !== "authenticated" || (!response && !error) ? (
          <SkeletonCard />
        ) : error ? (
          <ErrorState description={error} />
        ) : response && !response.has_sufficient_data ? (
          <Card>
            <p className="text-sm text-slate-300">{response.message}</p>
            <Link
              href="/learn"
              className="mt-4 inline-block rounded-lg bg-cyan-500 px-5 py-2.5 text-sm font-semibold text-slate-950 transition-colors duration-standard hover:bg-cyan-400"
            >
              Start learning
            </Link>
          </Card>
        ) : response?.insight ? (
          <>
            <Card variant="hero">
              <div className="mb-3 flex items-start justify-between gap-3">
                <h2 className="text-sm font-semibold uppercase tracking-wide text-cyan-400">
                  Summary
                </h2>
                {response.insight.from_cache && (
                  <span className="rounded-full border border-slate-700 px-2 py-0.5 text-[11px] text-slate-400">
                    cached
                  </span>
                )}
              </div>
              <p className="text-sm text-slate-200">{response.insight.summary}</p>
              {response.insight.data_note && (
                <p className="mt-3 text-xs text-slate-400">{response.insight.data_note}</p>
              )}
            </Card>

            {response.insight.strengths.length > 0 && (
              <Card>
                <h2 className="mb-2 text-sm font-semibold uppercase tracking-wide text-emerald-400">
                  Strengths
                </h2>
                <ul className="flex flex-col gap-1 text-sm text-slate-200">
                  {response.insight.strengths.map((s) => (
                    <li key={s}>• {s}</li>
                  ))}
                </ul>
              </Card>
            )}

            {response.insight.focus_areas.length > 0 && (
              <Card>
                <h2 className="mb-2 text-sm font-semibold uppercase tracking-wide text-amber-400">
                  Focus areas
                </h2>
                <ul className="flex flex-col gap-1 text-sm text-slate-200">
                  {response.insight.focus_areas.map((f) => (
                    <li key={f}>• {f}</li>
                  ))}
                </ul>
              </Card>
            )}

            <Card variant="interactive">
              <h2 className="mb-2 text-sm font-semibold uppercase tracking-wide text-slate-400">
                Recommended next step
              </h2>
              <p className="text-sm text-slate-200">{response.insight.recommended_action}</p>
              <Link
                href="/practice"
                className="mt-4 inline-block rounded-lg border border-cyan-700 px-4 py-2 text-sm font-semibold text-cyan-300 transition-colors duration-standard hover:bg-cyan-950/40"
              >
                Go practice
              </Link>
            </Card>

            <div className="flex flex-col items-start gap-2">
              <button
                type="button"
                onClick={handleRefresh}
                disabled={refreshing}
                className="rounded-lg border border-slate-700 px-4 py-2 text-sm font-semibold text-slate-200 transition-colors duration-standard hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-50"
              >
                {refreshing ? "Refreshing…" : "Refresh"}
              </button>
              {refreshNotice && <p className="text-xs text-slate-400">{refreshNotice}</p>}
            </div>
          </>
        ) : (
          <SkeletonCard />
        )}
      </div>
    </div>
  );
}
