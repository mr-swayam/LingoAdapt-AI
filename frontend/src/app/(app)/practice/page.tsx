"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { ExerciseRenderer } from "@/components/exercise/ExerciseRenderer";
import { ExerciseTransition } from "@/components/exercise/ExerciseTransition";
import { Card } from "@/components/ui/Card";
import { EmptyState } from "@/components/ui/EmptyState";
import { ErrorState } from "@/components/ui/ErrorState";
import { SkeletonCard } from "@/components/ui/Skeleton";
import { useRequireAuth } from "@/hooks/use-require-auth";
import {
  ApiError,
  startPractice,
  submitPracticeAnswer,
  submitPracticeAnswerAudio,
} from "@/lib/practice-api";
import { reasonLabel } from "@/lib/reason-label";
import type { ExerciseFeedback, SubmittedAnswer } from "@/types/course";
import type { PracticeStartResponse } from "@/types/practice";

export default function PracticePage() {
  const { status, accessToken } = useRequireAuth();

  const [session, setSession] = useState<PracticeStartResponse | null>(null);
  const [currentIndex, setCurrentIndex] = useState(0);
  const [currentResult, setCurrentResult] = useState<ExerciseFeedback | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [progress, setProgress] = useState({ correct: 0, total: 0 });

  useEffect(() => {
    if (status !== "authenticated" || !accessToken) return;

    let cancelled = false;
    startPractice(accessToken)
      .then((data) => {
        if (cancelled) return;
        setSession(data);
        setProgress({ correct: data.correct_count, total: data.total_count });
        const firstUnanswered = data.exercises.findIndex(
          (ex) => !data.answered_exercise_ids.includes(ex.id),
        );
        setCurrentIndex(firstUnanswered === -1 ? data.exercises.length : firstUnanswered);
      })
      .catch((err) => {
        if (cancelled) return;
        setError(err instanceof ApiError ? err.message : "Couldn't start a practice session.");
      });

    return () => {
      cancelled = true;
    };
  }, [status, accessToken]);

  if (status !== "authenticated") {
    return (
      <div className="flex flex-1 flex-col items-center px-6 py-12">
        <div className="w-full max-w-xl">
          <h1 className="sr-only">Practice</h1>
          <SkeletonCard />
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex flex-1 flex-col items-center justify-center gap-4 px-6 text-center">
        <h1 className="sr-only">Practice</h1>
        <ErrorState description={error} />
      </div>
    );
  }

  if (!session) {
    return (
      <div className="flex flex-1 flex-col items-center px-6 py-12">
        <div className="w-full max-w-xl">
          <h1 className="sr-only">Practice</h1>
          <SkeletonCard />
        </div>
      </div>
    );
  }

  if (session.total_count === 0) {
    return (
      <div className="flex flex-1 flex-col items-center justify-center px-6 text-center">
        <h1 className="sr-only">Practice</h1>
        <EmptyState
          title="Nothing to practice yet"
          description="Complete a lesson first - practice picks questions from skills you've already started learning."
          action={
            <Link
              href="/learn"
              className="rounded-lg bg-cyan-500 px-5 py-2.5 text-sm font-semibold text-slate-950 transition-colors duration-standard hover:bg-cyan-400"
            >
              Go to lessons
            </Link>
          }
        />
      </div>
    );
  }

  const isComplete = currentIndex >= session.exercises.length;
  const currentExercise = !isComplete ? session.exercises[currentIndex] : null;
  const currentReason = currentExercise ? session.reasons[currentExercise.id] : undefined;

  async function handleSubmit(answer: SubmittedAnswer) {
    if (!session || !accessToken) return;
    const exercise = session.exercises[currentIndex];
    setSubmitting(true);
    setError(null);
    try {
      const result = await submitPracticeAnswer(
        session.practice_session_id,
        exercise.id,
        answer,
        accessToken,
      );
      setCurrentResult(result);
      setProgress({ correct: result.correct_count, total: result.total_count });
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Couldn't submit your answer.");
    } finally {
      setSubmitting(false);
    }
  }

  async function handleSubmitAudio(audio: Blob) {
    if (!session || !accessToken) return;
    const exercise = session.exercises[currentIndex];
    setSubmitting(true);
    setError(null);
    try {
      const result = await submitPracticeAnswerAudio(
        session.practice_session_id,
        exercise.id,
        audio,
        accessToken,
      );
      setCurrentResult(result);
      setProgress({ correct: result.correct_count, total: result.total_count });
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Couldn't submit your recording.");
    } finally {
      setSubmitting(false);
    }
  }

  function handleContinue() {
    setCurrentResult(null);
    setCurrentIndex((i) => i + 1);
  }

  return (
    <div className="flex flex-1 flex-col items-center px-6 py-12">
      <div className="w-full max-w-xl">
        {!isComplete && <h1 className="sr-only">Practice</h1>}
        {!isComplete && (
          <div className="mb-6 flex items-center gap-4">
            <Link href="/dashboard" className="text-slate-400 hover:text-slate-300">
              ✕
            </Link>
            <div className="h-2 flex-1 overflow-hidden rounded-full bg-slate-800">
              <div
                className="h-full rounded-full bg-cyan-500 transition-all duration-standard"
                style={{ width: `${(currentIndex / session.exercises.length) * 100}%` }}
              />
            </div>
            <span className="text-sm text-slate-400">
              {currentIndex + 1} / {session.exercises.length}
            </span>
          </div>
        )}

        {!isComplete && currentReason && (
          <p className="mb-4 rounded-lg border border-cyan-900/60 bg-cyan-950/20 px-3 py-2 text-xs text-cyan-300">
            Recommended: {reasonLabel(currentReason)}
          </p>
        )}

        {error && <p className="mb-4 text-sm text-red-300">{error}</p>}

        <ExerciseTransition transitionKey={String(currentIndex)}>
          {isComplete ? (
            <PracticeCompleteScreen correctCount={progress.correct} totalCount={progress.total} />
          ) : (
            <ExerciseRenderer
              key={session.exercises[currentIndex].id}
              exercise={session.exercises[currentIndex]}
              result={currentResult}
              submitting={submitting}
              accessToken={accessToken ?? ""}
              onSubmit={handleSubmit}
              onSubmitAudio={handleSubmitAudio}
              onContinue={handleContinue}
            />
          )}
        </ExerciseTransition>
      </div>
    </div>
  );
}

function PracticeCompleteScreen({
  correctCount,
  totalCount,
}: {
  correctCount: number;
  totalCount: number;
}) {
  return (
    <Card variant="hero" padding="lg" className="flex flex-col items-center gap-6 text-center">
      <h1 className="text-2xl font-semibold text-slate-50">Practice complete! 💪</h1>
      <p className="text-lg text-slate-200">
        {correctCount} / {totalCount} correct
      </p>
      <Link
        href="/dashboard"
        className="rounded-lg bg-cyan-500 px-5 py-2.5 text-sm font-semibold text-slate-950 transition-colors duration-standard hover:bg-cyan-400"
      >
        Back to dashboard
      </Link>
    </Card>
  );
}
