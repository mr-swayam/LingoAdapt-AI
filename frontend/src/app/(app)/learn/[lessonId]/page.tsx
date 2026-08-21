"use client";

import Link from "next/link";
import { motion } from "framer-motion";
import { use, useEffect, useState } from "react";

import { ExerciseRenderer } from "@/components/exercise/ExerciseRenderer";
import { ExerciseTransition } from "@/components/exercise/ExerciseTransition";
import { AchievementCard } from "@/components/gamification/AchievementCard";
import { StreakBadge } from "@/components/gamification/StreakBadge";
import { Card } from "@/components/ui/Card";
import { SkeletonCard } from "@/components/ui/Skeleton";
import { useRequireAuth } from "@/hooks/use-require-auth";
import { ApiError, startLesson, submitAnswer, submitAnswerAudio } from "@/lib/course-api";
import { listAchievements } from "@/lib/progress-api";
import type { AnswerResult, LessonStartResponse, SubmittedAnswer } from "@/types/course";
import type { Achievement } from "@/types/progress";

type Rewards = {
  xpEarned: number;
  currentStreak: number | null;
  newAchievementCodes: string[];
};

export default function LessonPage({ params }: { params: Promise<{ lessonId: string }> }) {
  const { lessonId } = use(params);
  const { status, accessToken } = useRequireAuth();

  const [lessonData, setLessonData] = useState<LessonStartResponse | null>(null);
  const [currentIndex, setCurrentIndex] = useState(0);
  const [currentResult, setCurrentResult] = useState<AnswerResult | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  // Tracks the latest correct/total counts and any earned rewards, since
  // lessonData's own counts are a snapshot from the initial /start call and
  // go stale as the learner answers exercises.
  const [progress, setProgress] = useState({ correct: 0, total: 0 });
  const [rewards, setRewards] = useState<Rewards | null>(null);

  useEffect(() => {
    if (status !== "authenticated" || !accessToken) return;

    let cancelled = false;
    startLesson(lessonId, accessToken)
      .then((data) => {
        if (cancelled) return;
        setLessonData(data);
        setProgress({ correct: data.correct_count, total: data.total_count });
        const firstUnanswered = data.exercises.findIndex(
          (ex) => !data.answered_exercise_ids.includes(ex.id),
        );
        setCurrentIndex(firstUnanswered === -1 ? data.exercises.length : firstUnanswered);
      })
      .catch((err) => {
        if (cancelled) return;
        setError(err instanceof ApiError ? err.message : "Couldn't load this lesson.");
      });

    return () => {
      cancelled = true;
    };
  }, [status, accessToken, lessonId]);

  if (status !== "authenticated") {
    return (
      <div className="flex flex-1 flex-col items-center px-6 py-12">
        <div className="w-full max-w-xl">
          <SkeletonCard />
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex flex-1 flex-col items-center justify-center gap-4 px-6 text-center">
        <p className="text-red-300">{error}</p>
        <Link href="/learn" className="text-sm text-cyan-400 hover:text-cyan-300">
          ← Back to lessons
        </Link>
      </div>
    );
  }

  if (!lessonData) {
    return (
      <div className="flex flex-1 flex-col items-center px-6 py-12">
        <div className="w-full max-w-xl">
          <SkeletonCard />
        </div>
      </div>
    );
  }

  const isComplete = currentIndex >= lessonData.exercises.length;

  function applyResult(result: AnswerResult) {
    setCurrentResult(result);
    setProgress({ correct: result.correct_count, total: result.total_count });
    if (result.lesson_completed) {
      setRewards({
        xpEarned: result.xp_earned,
        currentStreak: result.current_streak,
        newAchievementCodes: result.new_achievements,
      });
    }
  }

  async function handleSubmit(answer: SubmittedAnswer) {
    if (!lessonData || !accessToken) return;
    const exercise = lessonData.exercises[currentIndex];
    setSubmitting(true);
    setError(null);
    try {
      applyResult(
        await submitAnswer(exercise.id, lessonData.lesson_attempt_id, answer, accessToken),
      );
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Couldn't submit your answer.");
    } finally {
      setSubmitting(false);
    }
  }

  async function handleSubmitAudio(audio: Blob) {
    if (!lessonData || !accessToken) return;
    const exercise = lessonData.exercises[currentIndex];
    setSubmitting(true);
    setError(null);
    try {
      applyResult(
        await submitAnswerAudio(exercise.id, lessonData.lesson_attempt_id, audio, accessToken),
      );
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
        {!isComplete && (
          <div className="mb-8 flex items-center gap-4">
            <Link href="/learn" className="text-slate-400 hover:text-slate-300">
              ✕
            </Link>
            <div className="h-2 flex-1 overflow-hidden rounded-full bg-slate-800">
              <div
                className="h-full rounded-full bg-cyan-500 transition-all"
                style={{
                  width: `${(currentIndex / lessonData.exercises.length) * 100}%`,
                }}
              />
            </div>
            <span className="text-sm text-slate-400">
              {currentIndex + 1} / {lessonData.exercises.length}
            </span>
          </div>
        )}

        {error && <p className="mb-4 text-sm text-red-300">{error}</p>}

        <ExerciseTransition transitionKey={String(currentIndex)}>
          {isComplete ? (
            <LessonCompleteScreen
              title={lessonData.lesson_title}
              correctCount={progress.correct}
              totalCount={progress.total}
              rewards={rewards}
              accessToken={accessToken}
            />
          ) : (
            <ExerciseRenderer
              key={lessonData.exercises[currentIndex].id}
              exercise={lessonData.exercises[currentIndex]}
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

/** Counts up from 0 to `value` over ~600ms - a restrained entrance for a
 * real, already-earned number (design.md §7: "do not cover the screen
 * with excessive animation" - this is the one deliberate exception, on
 * the one screen that celebrates a real accomplishment). */
function useCountUp(value: number, durationMs = 600): number {
  const [display, setDisplay] = useState(0);
  useEffect(() => {
    let raf: number;
    const start = performance.now();
    function tick(now: number) {
      const progress = Math.min(1, (now - start) / durationMs);
      setDisplay(Math.round(value * (1 - Math.pow(1 - progress, 3)))); // ease-out cubic
      if (progress < 1) raf = requestAnimationFrame(tick);
    }
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [value, durationMs]);
  return display;
}

function LessonCompleteScreen({
  title,
  correctCount,
  totalCount,
  rewards,
  accessToken,
}: {
  title: string;
  correctCount: number;
  totalCount: number;
  rewards: Rewards | null;
  accessToken: string | null;
}) {
  const [newAchievements, setNewAchievements] = useState<Achievement[]>([]);
  const displayedXp = useCountUp(rewards?.xpEarned ?? 0);

  useEffect(() => {
    if (!rewards || rewards.newAchievementCodes.length === 0 || !accessToken) return;
    listAchievements(accessToken)
      .then((all) =>
        setNewAchievements(
          all.filter((a) => rewards.newAchievementCodes.includes(a.code)),
        ),
      )
      .catch(() => setNewAchievements([]));
  }, [rewards, accessToken]);

  return (
    <Card variant="hero" padding="lg" className="flex flex-col items-center gap-6 text-center">
      <motion.h1
        initial={{ scale: 0.9, opacity: 0 }}
        animate={{ scale: 1, opacity: 1 }}
        transition={{ duration: 0.4, ease: "easeOut" }}
        className="text-2xl font-semibold text-slate-50"
      >
        Lesson complete! 🎉
      </motion.h1>
      <p className="text-slate-400">{title}</p>
      <p className="text-lg text-slate-200">
        {correctCount} / {totalCount} correct
      </p>

      {rewards && (
        <div className="flex items-center gap-3">
          <span className="rounded-full border border-gold-600 bg-gold-950 px-3 py-1.5 text-sm text-gold-300">
            +{displayedXp} XP
          </span>
          {rewards.currentStreak !== null && <StreakBadge days={rewards.currentStreak} />}
        </div>
      )}

      {newAchievements.length > 0 && (
        <motion.div
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.3, duration: 0.3 }}
          className="flex w-full flex-col gap-2"
        >
          <p className="text-sm font-semibold text-gold-400">New achievement!</p>
          <div className="grid grid-cols-1 gap-2">
            {newAchievements.map((achievement) => (
              <AchievementCard key={achievement.code} achievement={achievement} />
            ))}
          </div>
        </motion.div>
      )}

      <Link
        href="/learn"
        className="rounded-lg bg-cyan-500 px-5 py-2.5 text-sm font-semibold text-slate-950 transition-colors duration-standard hover:bg-cyan-400"
      >
        Back to lessons
      </Link>
    </Card>
  );
}
