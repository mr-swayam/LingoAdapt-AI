"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { AchievementCard } from "@/components/gamification/AchievementCard";
import { GemBadge } from "@/components/gamification/GemBadge";
import { QuestCard } from "@/components/gamification/QuestCard";
import { StreakBadge } from "@/components/gamification/StreakBadge";
import { Card } from "@/components/ui/Card";
import { EmptyState } from "@/components/ui/EmptyState";
import { ProgressBar } from "@/components/ui/ProgressBar";
import { ProgressRing } from "@/components/ui/ProgressRing";
import { SkeletonCard } from "@/components/ui/Skeleton";
import { useRequireAuth } from "@/hooks/use-require-auth";
import { listCourses } from "@/lib/course-api";
import { ApiError, getDailyPlan } from "@/lib/daily-plan-api";
import { getQuests } from "@/lib/gamification-api";
import { LEAGUE_TIER_ICONS, LEAGUE_TIER_LABELS } from "@/lib/league-labels";
import { practiceAgain } from "@/lib/practice-api";
import { getProgress } from "@/lib/progress-api";
import { reasonLabel } from "@/lib/reason-label";
import type { CourseSummary } from "@/types/course";
import type { DailyPlan, DailyPlanTask } from "@/types/daily-plan";
import type { Quest } from "@/types/gamification";
import type { Progress } from "@/types/progress";

const TASK_ICON: Record<DailyPlanTask["task_type"], string> = {
  REVIEW: "🔁",
  PRACTICE: "🎯",
  LESSON: "📘",
};

/** The learning "command center" - prioritizes one clear next action
 * (continue the current lesson) instead of the previous 9-equal-weight
 * card stack. "Today's Plan" (V3.2) replaces the old separate Review-due
 * and Recommended-for-you cards with one unified, ordered list from the
 * same real backend priority logic - no two cards silently disagreeing
 * about what to do next. Every number on this page comes from a real API
 * response - nothing here is a placeholder or invented statistic. */
export default function DashboardPage() {
  const { status, user, accessToken } = useRequireAuth();
  const router = useRouter();
  const [course, setCourse] = useState<CourseSummary | null>(null);
  const [progress, setProgress] = useState<Progress | null>(null);
  const [quests, setQuests] = useState<Quest[] | null>(null);
  const [dailyPlan, setDailyPlan] = useState<DailyPlan | null>(null);
  const [pendingTaskKey, setPendingTaskKey] = useState<string | null>(null);
  const [taskError, setTaskError] = useState<string | null>(null);

  useEffect(() => {
    if (status !== "authenticated" || !accessToken) return;
    listCourses()
      .then((courses) => setCourse(courses[0] ?? null))
      .catch(() => setCourse(null));
    getProgress(accessToken)
      .then(setProgress)
      .catch(() => setProgress(null));
    getQuests(accessToken)
      .then(setQuests)
      .catch(() => setQuests(null));
    getDailyPlan(accessToken)
      .then(setDailyPlan)
      .catch(() => setDailyPlan(null));
  }, [status, accessToken]);

  async function handleTaskAction(task: DailyPlanTask) {
    if (!accessToken) return;
    const key = `${task.task_type}:${task.skill_id ?? task.lesson_id}`;
    if (task.task_type === "LESSON") {
      if (task.lesson_id) router.push(`/learn/${task.lesson_id}`);
      return;
    }
    if (!task.skill_id) return;
    setPendingTaskKey(key);
    setTaskError(null);
    try {
      await practiceAgain({ skillId: task.skill_id }, accessToken);
      router.push("/practice");
    } catch (err) {
      setTaskError(err instanceof ApiError ? err.message : "Couldn't start that task.");
      setPendingTaskKey(null);
    }
  }

  if (status !== "authenticated" || !user) {
    return (
      <div className="flex flex-1 flex-col items-center px-6 py-10">
        <div className="flex w-full max-w-5xl flex-col gap-4">
          <SkeletonCard />
          <SkeletonCard />
        </div>
      </div>
    );
  }

  const courseProgress = progress?.course_progress.find((cp) => cp.course_id === course?.id);
  const courseCompletionPercent = courseProgress
    ? Math.round((courseProgress.completed_lessons / Math.max(1, courseProgress.total_lessons)) * 100)
    : 0;

  return (
    <div className="flex flex-1 flex-col items-center px-6 py-10 md:py-12">
      <div className="flex w-full max-w-5xl flex-col gap-6">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h1 className="text-2xl font-semibold text-slate-50">Good to see you 👋</h1>
            <p className="text-sm text-slate-400">{user.email}</p>
          </div>
          <div className="flex items-center gap-3">
            {progress && <StreakBadge days={progress.current_streak} />}
            {progress && <GemBadge count={progress.gem_balance} />}
          </div>
        </div>

        {course ? (
          <Card variant="hero" className="flex flex-col gap-5 md:flex-row md:items-center md:justify-between">
            <div>
              <p className="text-xs font-semibold uppercase tracking-wide text-cyan-400">
                Continue learning
              </p>
              <p className="mt-1 text-xl font-semibold text-slate-50">{course.title}</p>
              <p className="mt-1 text-sm text-slate-400">
                {course.unit_count} units · {course.lesson_count} lessons
                {courseProgress &&
                  ` · ${courseProgress.completed_lessons}/${courseProgress.total_lessons} complete`}
              </p>
            </div>
            <div className="flex items-center gap-5">
              {courseProgress && (
                <ProgressRing
                  value={courseProgress.completed_lessons}
                  max={courseProgress.total_lessons}
                  label={`${course.title} course progress`}
                  size={56}
                  colorClassName="stroke-cyan-400"
                >
                  <span className="text-xs font-semibold text-slate-100">{courseCompletionPercent}%</span>
                </ProgressRing>
              )}
              <Link
                href="/learn"
                className="rounded-lg bg-cyan-500 px-5 py-2.5 text-sm font-semibold text-slate-950 transition-colors duration-standard hover:bg-cyan-400"
              >
                Continue lesson
              </Link>
            </div>
          </Card>
        ) : (
          <EmptyState
            title="No course yet"
            description="Pick a lesson to get started."
            action={
              <Link
                href="/learn"
                className="rounded-lg bg-cyan-500 px-5 py-2.5 text-sm font-semibold text-slate-950 transition-colors duration-standard hover:bg-cyan-400"
              >
                Browse lessons
              </Link>
            }
          />
        )}

        {progress && (
          <Card>
            <div className="mb-2 flex items-center justify-between text-sm">
              <h2 className="font-semibold uppercase tracking-wide text-slate-400">Daily goal</h2>
              <span className="text-slate-300">
                {progress.xp_today} / {progress.daily_goal_xp} XP
              </span>
            </div>
            <ProgressBar value={progress.xp_today} max={progress.daily_goal_xp} label="Daily goal progress" />
          </Card>
        )}

        {dailyPlan && dailyPlan.tasks.length > 0 && (
          <Card>
            <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-slate-400">
              Today&rsquo;s plan
            </h2>
            <div className="flex flex-col gap-2">
              {dailyPlan.tasks.map((task) => {
                const key = `${task.task_type}:${task.skill_id ?? task.lesson_id}`;
                const label =
                  task.task_type === "LESSON"
                    ? `Continue: ${task.lesson_title}`
                    : task.reason
                      ? reasonLabel(task.reason)
                      : (task.skill_name ?? "");
                return (
                  <div
                    key={key}
                    className={`flex items-center justify-between gap-3 rounded-lg border px-3 py-2.5 ${
                      task.completed
                        ? "border-emerald-900 bg-emerald-950/20"
                        : "border-slate-800 bg-slate-900/40"
                    }`}
                  >
                    <div className="flex items-center gap-2 text-sm">
                      <span aria-hidden>{task.completed ? "✅" : TASK_ICON[task.task_type]}</span>
                      <span className={task.completed ? "text-slate-400 line-through" : "text-slate-200"}>
                        {label}
                      </span>
                    </div>
                    {!task.completed && (
                      <button
                        type="button"
                        onClick={() => handleTaskAction(task)}
                        disabled={pendingTaskKey === key}
                        className="shrink-0 rounded-lg border border-cyan-700 px-3 py-1 text-xs font-semibold text-cyan-300 transition-colors duration-standard hover:bg-cyan-950/40 disabled:cursor-not-allowed disabled:opacity-50"
                      >
                        {pendingTaskKey === key ? "Starting…" : task.task_type === "LESSON" ? "Go" : "Practice"}
                      </button>
                    )}
                  </div>
                );
              })}
            </div>
            {taskError && <p className="mt-3 text-xs text-red-300">{taskError}</p>}
          </Card>
        )}

        <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
          <Card variant="interactive">
            <h2 className="mb-1 text-sm font-semibold uppercase tracking-wide text-slate-400">
              AI Coach
            </h2>
            <p className="text-sm text-slate-400">
              A grounded read on how you&rsquo;re doing, based on your real activity.
            </p>
            <Link
              href="/coach"
              className="mt-4 inline-block rounded-lg border border-cyan-700 px-4 py-2 text-sm font-semibold text-cyan-300 transition-colors duration-standard hover:bg-cyan-950/40"
            >
              View insight
            </Link>
          </Card>

          <Card variant="interactive">
            <h2 className="mb-1 text-sm font-semibold uppercase tracking-wide text-slate-400">
              Mistake Notebook
            </h2>
            <p className="text-sm text-slate-400">
              Review what you&rsquo;ve gotten wrong in lessons, practice, and tutor conversations.
            </p>
            <Link
              href="/mistakes"
              className="mt-4 inline-block rounded-lg border border-cyan-700 px-4 py-2 text-sm font-semibold text-cyan-300 transition-colors duration-standard hover:bg-cyan-950/40"
            >
              Review mistakes
            </Link>
          </Card>

          {quests && quests.length > 0 && (
            <Card>
              <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-slate-400">
                Daily quests
              </h2>
              <div className="flex flex-col gap-2">
                {quests.map((quest) => (
                  <QuestCard key={quest.id} quest={quest} />
                ))}
              </div>
            </Card>
          )}

          <Card>
            <h2 className="mb-1 text-sm font-semibold uppercase tracking-wide text-slate-400">Compete</h2>
            <p className="text-sm text-slate-400">
              {progress
                ? `You're in the ${LEAGUE_TIER_LABELS[progress.league_tier] ?? progress.league_tier} league this week.`
                : "See how you stack up against other learners."}
            </p>
            <div className="mt-4 flex gap-4">
              <Link
                href="/leaderboard"
                className="inline-flex items-center gap-1.5 rounded-lg border border-cyan-700 px-4 py-2 text-sm font-semibold text-cyan-300 transition-colors duration-standard hover:bg-cyan-950/40"
              >
                {progress && <span aria-hidden>{LEAGUE_TIER_ICONS[progress.league_tier] ?? "🏅"}</span>}
                Leaderboard
              </Link>
              <Link
                href="/friends"
                className="inline-flex items-center rounded-lg border border-slate-700 px-4 py-2 text-sm font-semibold text-slate-200 transition-colors duration-standard hover:bg-slate-800"
              >
                Friends
              </Link>
            </div>
          </Card>
        </div>

        {progress && progress.achievements.length > 0 && (
          <Card>
            <h2 className="mb-4 text-sm font-semibold uppercase tracking-wide text-gold-400">
              Achievements
            </h2>
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
              {progress.achievements.map((achievement) => (
                <AchievementCard key={achievement.code} achievement={achievement} />
              ))}
            </div>
          </Card>
        )}

        <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
          <Card variant="interactive">
            <h2 className="mb-1 text-sm font-semibold uppercase tracking-wide text-slate-400">Practice</h2>
            <p className="text-sm text-slate-400">
              A personalized set of questions targeting your weakest skills, past mistakes, and
              anything due for review.
            </p>
            <Link
              href="/practice"
              className="mt-4 inline-block rounded-lg border border-cyan-700 px-4 py-2 text-sm font-semibold text-cyan-300 transition-colors duration-standard hover:bg-cyan-950/40"
            >
              Start practice
            </Link>
          </Card>

          <Card variant="interactive">
            <h2 className="mb-1 text-sm font-semibold uppercase tracking-wide text-slate-400">AI Tutor</h2>
            <p className="text-sm text-slate-400">
              Practice a real conversation - pick a scenario and get corrections as you go.
            </p>
            <Link
              href="/tutor"
              className="mt-4 inline-block rounded-lg border border-cyan-700 px-4 py-2 text-sm font-semibold text-cyan-300 transition-colors duration-standard hover:bg-cyan-950/40"
            >
              Start a conversation
            </Link>
          </Card>
        </div>

        {user.is_admin && (
          <Card variant="admin">
            <h2 className="mb-1 text-sm font-semibold uppercase tracking-wide text-amber-400">Admin</h2>
            <p className="text-sm text-slate-400">
              Create and manage courses, units, lessons, and exercises.
            </p>
            <Link
              href="/admin"
              className="mt-4 inline-block rounded-lg border border-amber-700 px-4 py-2 text-sm font-semibold text-amber-300 transition-colors duration-standard hover:bg-amber-950/40"
            >
              Open course editor
            </Link>
          </Card>
        )}
      </div>
    </div>
  );
}
