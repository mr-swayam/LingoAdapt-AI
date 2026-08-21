"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { Card } from "@/components/ui/Card";
import { EmptyState } from "@/components/ui/EmptyState";
import { ErrorState } from "@/components/ui/ErrorState";
import { SkeletonCard } from "@/components/ui/Skeleton";
import { useRequireAuth } from "@/hooks/use-require-auth";
import { ApiError, getMistakes, getRepeatedMistakes } from "@/lib/mistakes-api";
import { practiceAgain } from "@/lib/practice-api";
import type { Mistake, MistakeSource, RepeatedMistakeGroup } from "@/types/mistakes";

const PAGE_SIZE = 10;

const SOURCE_LABEL: Record<MistakeSource, string> = {
  LESSON: "Lesson",
  PRACTICE: "Practice",
  TUTOR: "AI Tutor",
};

const SOURCE_FILTERS: { value: MistakeSource | "ALL"; label: string }[] = [
  { value: "ALL", label: "All" },
  { value: "LESSON", label: "Lessons" },
  { value: "PRACTICE", label: "Practice" },
  { value: "TUTOR", label: "AI Tutor" },
];

type PracticeAgainTarget = { skillId: string } | { exerciseId: string };

/** V3.3 Mistake Notebook. Unifies wrong lesson/practice answers and tutor
 * corrections that already existed in the database but were never shown to
 * the learner before - every mistake here traces to a real stored attempt
 * (backend mistake_service.py), nothing invented for display. */
export default function MistakesPage() {
  const { status, accessToken } = useRequireAuth();
  const router = useRouter();

  const [groups, setGroups] = useState<RepeatedMistakeGroup[] | null>(null);
  const [source, setSource] = useState<MistakeSource | "ALL">("ALL");
  const [actionError, setActionError] = useState<string | null>(null);
  const [pendingAction, setPendingAction] = useState<string | null>(null);

  useEffect(() => {
    if (status !== "authenticated" || !accessToken) return;
    let cancelled = false;
    getRepeatedMistakes(accessToken)
      .then((data) => {
        if (!cancelled) setGroups(data);
      })
      .catch(() => {
        if (!cancelled) setGroups([]);
      });
    return () => {
      cancelled = true;
    };
  }, [status, accessToken]);

  async function handlePracticeAgain(key: string, target: PracticeAgainTarget) {
    if (!accessToken) return;
    setPendingAction(key);
    setActionError(null);
    try {
      await practiceAgain(target, accessToken);
      router.push("/practice");
    } catch (err) {
      setActionError(err instanceof ApiError ? err.message : "Couldn't start that practice session.");
      setPendingAction(null);
    }
  }

  if (status !== "authenticated" || !accessToken) {
    return (
      <div className="flex flex-1 flex-col items-center px-6 py-12">
        <div className="w-full max-w-2xl">
          <SkeletonCard />
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-1 flex-col items-center px-6 py-12">
      <div className="flex w-full max-w-2xl flex-col gap-6">
        <div>
          <h1 className="text-2xl font-semibold text-slate-50">Mistake Notebook</h1>
          <p className="mt-1 text-sm text-slate-400">
            Every mistake here comes from something you actually got wrong - in a lesson,
            practice, or a conversation with the AI Tutor.
          </p>
        </div>

        {actionError && <p className="text-sm text-red-300">{actionError}</p>}

        {groups && groups.length > 0 && (
          <div className="flex flex-col gap-3">
            <h2 className="text-sm font-semibold uppercase tracking-wide text-amber-300">
              Keeps coming up
            </h2>
            {groups.map((group) => {
              const key = `${group.type}:${group.skill_id}:${group.exercise_id ?? ""}`;
              const isExact = group.type === "REPEATED_EXACT_MISTAKE";
              return (
                <Card key={key} variant="warning">
                  <p className="text-sm text-slate-200">
                    {isExact
                      ? `You've missed this exact question in ${group.skill_name} ${group.count} times`
                      : `Repeated difficulty in ${group.skill_name} (${group.count} mistakes)`}
                  </p>
                  <button
                    type="button"
                    disabled={pendingAction === key}
                    onClick={() =>
                      handlePracticeAgain(
                        key,
                        isExact
                          ? { exerciseId: group.exercise_id as string }
                          : { skillId: group.skill_id },
                      )
                    }
                    className="mt-3 rounded-lg border border-amber-700 px-4 py-2 text-sm font-semibold text-amber-300 transition-colors duration-standard hover:bg-amber-950/40 disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    {pendingAction === key
                      ? "Starting…"
                      : isExact
                        ? "Retry this exercise"
                        : "Practice this skill again"}
                  </button>
                </Card>
              );
            })}
          </div>
        )}

        <div className="flex flex-wrap gap-2">
          {SOURCE_FILTERS.map((filter) => (
            <button
              key={filter.value}
              type="button"
              onClick={() => setSource(filter.value)}
              className={`rounded-full px-3 py-1.5 text-xs font-medium transition-colors duration-standard ${
                source === filter.value
                  ? "bg-cyan-500 text-slate-950"
                  : "border border-slate-700 text-slate-300 hover:bg-slate-800"
              }`}
            >
              {filter.label}
            </button>
          ))}
        </div>

        <MistakeListSection
          key={source}
          accessToken={accessToken}
          source={source}
          pendingAction={pendingAction}
          onPracticeAgain={handlePracticeAgain}
        />
      </div>
    </div>
  );
}

/** Owns its own loading/error/pagination state, keyed by `source` at the
 * call site so switching filters remounts (and cleanly resets) it instead
 * of resetting state via a synchronous setState call inside an effect -
 * the same pattern this app's leaderboard tab switcher already uses. */
function MistakeListSection({
  accessToken,
  source,
  pendingAction,
  onPracticeAgain,
}: {
  accessToken: string;
  source: MistakeSource | "ALL";
  pendingAction: string | null;
  onPracticeAgain: (key: string, target: PracticeAgainTarget) => void;
}) {
  const [mistakes, setMistakes] = useState<Mistake[]>([]);
  const [hasMore, setHasMore] = useState(false);
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    getMistakes(accessToken, {
      limit: PAGE_SIZE,
      offset: 0,
      source: source === "ALL" ? undefined : source,
    })
      .then((page) => {
        if (cancelled) return;
        setMistakes(page.items);
        setHasMore(page.has_more);
      })
      .catch((err) => {
        if (cancelled) return;
        setError(err instanceof ApiError ? err.message : "Couldn't load your mistakes.");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [accessToken, source]);

  async function handleLoadMore() {
    setLoadingMore(true);
    try {
      const page = await getMistakes(accessToken, {
        limit: PAGE_SIZE,
        offset: mistakes.length,
        source: source === "ALL" ? undefined : source,
      });
      setMistakes((prev) => [...prev, ...page.items]);
      setHasMore(page.has_more);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Couldn't load more mistakes.");
    } finally {
      setLoadingMore(false);
    }
  }

  if (loading) return <SkeletonCard />;
  if (error) return <ErrorState description={error} />;
  if (mistakes.length === 0) {
    return (
      <EmptyState
        title="No mistakes here"
        description="Once you get something wrong in a lesson, practice, or a tutor conversation, it'll show up here."
      />
    );
  }

  return (
    <div className="flex flex-col gap-3">
      {mistakes.map((mistake) => {
        const key = `mistake:${mistake.id}`;
        const canRetryExercise = mistake.exercise_id !== null;
        return (
          <Card key={mistake.id} padding="sm">
            <div className="mb-2 flex items-center justify-between text-xs text-slate-400">
              <span>
                {SOURCE_LABEL[mistake.source]} · {mistake.skill_name}
              </span>
              <span>{new Date(mistake.created_at).toLocaleDateString()}</span>
            </div>
            {mistake.prompt && <p className="mb-2 text-sm text-slate-300">{mistake.prompt}</p>}
            <p className="text-sm text-red-300">
              <span className="text-slate-400">You answered: </span>
              {mistake.submitted_text || "—"}
            </p>
            {mistake.correct_text && (
              <p className="text-sm text-emerald-300">
                <span className="text-slate-400">Correct: </span>
                {mistake.correct_text}
              </p>
            )}
            {mistake.explanation && (
              <p className="mt-1 text-xs text-slate-400">{mistake.explanation}</p>
            )}
            <button
              type="button"
              disabled={pendingAction === key}
              onClick={() =>
                onPracticeAgain(
                  key,
                  canRetryExercise
                    ? { exerciseId: mistake.exercise_id as string }
                    : { skillId: mistake.skill_id },
                )
              }
              className="mt-3 rounded-lg border border-cyan-700 px-3 py-1.5 text-xs font-semibold text-cyan-300 transition-colors duration-standard hover:bg-cyan-950/40 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {pendingAction === key
                ? "Starting…"
                : canRetryExercise
                  ? "Retry this exercise"
                  : "Practice this skill"}
            </button>
          </Card>
        );
      })}

      {hasMore && (
        <button
          type="button"
          onClick={handleLoadMore}
          disabled={loadingMore}
          className="self-center rounded-lg border border-slate-700 px-4 py-2 text-sm font-semibold text-slate-200 transition-colors duration-standard hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {loadingMore ? "Loading…" : "Load more"}
        </button>
      )}
    </div>
  );
}
