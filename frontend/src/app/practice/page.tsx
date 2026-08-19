"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { ExerciseRenderer } from "@/components/exercise/ExerciseRenderer";
import { useRequireAuth } from "@/hooks/use-require-auth";
import {
  ApiError,
  startPractice,
  submitPracticeAnswer,
  submitPracticeAnswerAudio,
} from "@/lib/practice-api";
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
      <div className="flex flex-1 items-center justify-center px-6">
        <h1 className="sr-only">Practice</h1>
        <p className="text-slate-400">Loading…</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex flex-1 flex-col items-center justify-center gap-4 px-6 text-center">
        <h1 className="sr-only">Practice</h1>
        <p className="text-red-300">{error}</p>
        <Link href="/dashboard" className="text-sm text-cyan-400 hover:text-cyan-300">
          ← Back to dashboard
        </Link>
      </div>
    );
  }

  if (!session) {
    return (
      <div className="flex flex-1 items-center justify-center px-6">
        <h1 className="sr-only">Practice</h1>
        <p className="text-slate-400">Building your practice set…</p>
      </div>
    );
  }

  if (session.total_count === 0) {
    return (
      <div className="flex flex-1 flex-col items-center justify-center gap-4 px-6 text-center">
        <h1 className="sr-only">Practice</h1>
        <p className="text-slate-300">Nothing to practice yet.</p>
        <p className="text-sm text-slate-400">
          Complete a lesson first - practice picks questions from skills you&apos;ve already
          started learning.
        </p>
        <Link
          href="/learn"
          className="rounded-lg bg-cyan-500 px-5 py-2.5 text-sm font-semibold text-slate-950 transition-colors hover:bg-cyan-400"
        >
          Go to lessons
        </Link>
      </div>
    );
  }

  const isComplete = currentIndex >= session.exercises.length;

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
          <div className="mb-8 flex items-center gap-4">
            <Link href="/dashboard" className="text-slate-400 hover:text-slate-300">
              ✕
            </Link>
            <div className="h-2 flex-1 overflow-hidden rounded-full bg-slate-800">
              <div
                className="h-full rounded-full bg-cyan-500 transition-all"
                style={{ width: `${(currentIndex / session.exercises.length) * 100}%` }}
              />
            </div>
            <span className="text-sm text-slate-400">
              {currentIndex + 1} / {session.exercises.length}
            </span>
          </div>
        )}

        {error && <p className="mb-4 text-sm text-red-300">{error}</p>}

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
    <div className="flex flex-col items-center gap-6 rounded-2xl border border-slate-800 bg-slate-900/60 p-10 text-center">
      <h1 className="text-2xl font-semibold text-slate-50">Practice complete! 💪</h1>
      <p className="text-lg text-slate-200">
        {correctCount} / {totalCount} correct
      </p>
      <Link
        href="/dashboard"
        className="rounded-lg bg-cyan-500 px-5 py-2.5 text-sm font-semibold text-slate-950 transition-colors hover:bg-cyan-400"
      >
        Back to dashboard
      </Link>
    </div>
  );
}
