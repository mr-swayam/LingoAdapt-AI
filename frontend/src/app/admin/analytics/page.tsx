"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { useRequireAuth } from "@/hooks/use-require-auth";
import { ApiError, getAnalyticsOverview } from "@/lib/admin-api";
import type { AnalyticsOverview } from "@/types/admin";

function pct(rate: number): string {
  return `${Math.round(rate * 100)}%`;
}

function Card({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <div className="rounded-2xl border border-slate-800 bg-slate-900/60 p-6">
      <p className="text-xs font-semibold uppercase tracking-wide text-slate-400">{label}</p>
      <p className="mt-2 text-3xl font-semibold text-slate-50">{value}</p>
      {sub && <p className="mt-1 text-xs text-slate-400">{sub}</p>}
    </div>
  );
}

function Bar({ fraction, label, tone = "bg-cyan-500" }: { fraction: number; label: string; tone?: string }) {
  const width = Math.max(0, Math.min(1, fraction)) * 100;
  return (
    <div className="flex items-center gap-3">
      <div className="h-2 flex-1 overflow-hidden rounded-full bg-slate-800">
        <div className={`h-full ${tone}`} style={{ width: `${width}%` }} />
      </div>
      <span className="w-40 shrink-0 text-right text-xs text-slate-400">{label}</span>
    </div>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="rounded-2xl border border-slate-800 bg-slate-900/60 p-6">
      <h2 className="mb-4 text-sm font-semibold uppercase tracking-wide text-slate-400">
        {title}
      </h2>
      {children}
    </div>
  );
}

export default function AdminAnalyticsPage() {
  const { status, user, accessToken } = useRequireAuth();
  const [overview, setOverview] = useState<AnalyticsOverview | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (status !== "authenticated" || !accessToken) return;
    getAnalyticsOverview(accessToken, 30)
      .then(setOverview)
      .catch((err) => setError(err instanceof ApiError ? err.message : "Couldn't load analytics."))
      .finally(() => setLoading(false));
  }, [status, accessToken]);

  if (status !== "authenticated" || !user) {
    return (
      <div className="flex flex-1 items-center justify-center px-6">
        <p className="text-slate-400">Loading…</p>
      </div>
    );
  }

  if (!user.is_admin) {
    return (
      <div className="flex flex-1 flex-col items-center justify-center gap-4 px-6 text-center">
        <p className="text-red-300">Admin access required.</p>
        <Link href="/dashboard" className="text-sm text-cyan-400 hover:text-cyan-300">
          ← Back to dashboard
        </Link>
      </div>
    );
  }

  return (
    <div className="flex flex-1 flex-col items-center px-6 py-12">
      <div className="w-full max-w-4xl">
        <div className="mb-6 flex items-center gap-4">
          <Link href="/admin" className="text-slate-400 hover:text-slate-300">
            ←
          </Link>
          <h1 className="text-2xl font-semibold text-slate-50">Analytics</h1>
          <span className="text-xs text-slate-400">Last 30 days</span>
        </div>

        {error && <p className="mb-4 text-sm text-red-300">{error}</p>}
        {loading && <p className="text-sm text-slate-400">Loading…</p>}

        {overview && (
          <div className="flex flex-col gap-6">
            <div className="grid grid-cols-2 gap-4 sm:grid-cols-3">
              <Card
                label="Active learners today"
                value={String(
                  overview.daily_active_users[overview.daily_active_users.length - 1]?.count ?? 0,
                )}
                sub={`peak ${Math.max(0, ...overview.daily_active_users.map((p) => p.count))} in 30d`}
              />
              <Card
                label="Lesson completion"
                value={pct(overview.lesson_completion.completion_rate)}
                sub={`${overview.lesson_completion.completed} / ${overview.lesson_completion.started} started`}
              />
              <Card
                label="Practice completion"
                value={pct(overview.practice_completion.completion_rate)}
                sub={`${overview.practice_completion.completed} / ${overview.practice_completion.started} started`}
              />
              <Card
                label="Day-1 retention"
                value={pct(overview.day1_retention.retention_rate)}
                sub={`${overview.day1_retention.retained} / ${overview.day1_retention.cohort_size} learners`}
              />
              <Card
                label="Day-7 retention"
                value={pct(overview.day7_retention.retention_rate)}
                sub={`${overview.day7_retention.retained} / ${overview.day7_retention.cohort_size} learners`}
              />
            </div>

            <Section title="Daily active learners">
              <div className="flex h-24 items-end gap-1">
                {overview.daily_active_users.map((point) => {
                  const max = Math.max(1, ...overview.daily_active_users.map((p) => p.count));
                  return (
                    <div
                      key={point.day}
                      title={`${point.day}: ${point.count}`}
                      className="flex-1 rounded-t bg-cyan-600/70"
                      style={{ height: `${(point.count / max) * 100}%`, minHeight: point.count > 0 ? "2px" : "0" }}
                    />
                  );
                })}
              </div>
            </Section>

            <Section title="AI latency &amp; error rate">
              {overview.ai_stats.length === 0 ? (
                <p className="text-sm text-slate-400">No AI calls in this period.</p>
              ) : (
                <div className="flex flex-col gap-3">
                  {overview.ai_stats.map((stat) => (
                    <div
                      key={stat.operation}
                      className="flex items-center justify-between text-sm text-slate-300"
                    >
                      <span className="font-medium text-slate-100">{stat.operation}</span>
                      <span className="text-slate-400">
                        {stat.total_calls} calls · {Math.round(stat.avg_latency_ms)}ms avg ·{" "}
                        <span className={stat.error_rate > 0.05 ? "text-red-300" : "text-slate-400"}>
                          {pct(stat.error_rate)} error rate
                        </span>
                      </span>
                    </div>
                  ))}
                </div>
              )}
            </Section>

            <Section title="Most common mistakes">
              {overview.top_mistakes.length === 0 ? (
                <p className="text-sm text-slate-400">No AI-detected mistakes yet.</p>
              ) : (
                <div className="flex flex-col gap-2">
                  {overview.top_mistakes.map((m) => {
                    const max = Math.max(...overview.top_mistakes.map((x) => x.count));
                    return (
                      <Bar
                        key={m.error_type}
                        fraction={m.count / max}
                        label={`${m.error_type} (${m.count})`}
                        tone="bg-amber-500"
                      />
                    );
                  })}
                </div>
              )}
            </Section>

            <Section title="Weakest skills">
              {overview.weakest_skills.length === 0 ? (
                <p className="text-sm text-slate-400">Not enough practice data yet.</p>
              ) : (
                <div className="flex flex-col gap-2">
                  {overview.weakest_skills.map((s) => (
                    <Bar
                      key={s.skill_id}
                      fraction={s.avg_mastery / 100}
                      label={`${s.skill_name} (${Math.round(s.avg_mastery)}/100)`}
                      tone="bg-rose-500"
                    />
                  ))}
                </div>
              )}
            </Section>

            <Section title="Improvement over time (weekly accuracy)">
              <div className="flex h-24 items-end gap-2">
                {overview.improvement_trend.map((point) => (
                  <div
                    key={point.week_start}
                    title={`Week of ${point.week_start}: ${pct(point.accuracy)} (${point.correct}/${point.total})`}
                    className="flex flex-1 flex-col items-center gap-1"
                  >
                    <div className="flex w-full flex-1 items-end">
                      <div
                        className="w-full rounded-t bg-emerald-600/70"
                        style={{
                          height: `${point.total > 0 ? point.accuracy * 100 : 0}%`,
                          minHeight: point.total > 0 ? "2px" : "0",
                        }}
                      />
                    </div>
                    <span className="text-[10px] text-slate-400">
                      {point.week_start.slice(5)}
                    </span>
                  </div>
                ))}
              </div>
            </Section>
          </div>
        )}
      </div>
    </div>
  );
}
