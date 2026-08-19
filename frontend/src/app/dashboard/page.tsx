"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { AchievementCard } from "@/components/gamification/AchievementCard";
import { GemBadge } from "@/components/gamification/GemBadge";
import { QuestCard } from "@/components/gamification/QuestCard";
import { StreakBadge } from "@/components/gamification/StreakBadge";
import { PrimaryButton } from "@/components/ui/form";
import { ProgressBar } from "@/components/ui/ProgressBar";
import { useRequireAuth } from "@/hooks/use-require-auth";
import { listCourses } from "@/lib/course-api";
import { getQuests } from "@/lib/gamification-api";
import { languageName } from "@/lib/languages";
import { LEAGUE_TIER_ICONS, LEAGUE_TIER_LABELS } from "@/lib/league-labels";
import { getProgress } from "@/lib/progress-api";
import type { CourseSummary } from "@/types/course";
import type { Quest } from "@/types/gamification";
import type { Progress } from "@/types/progress";

export default function DashboardPage() {
  const router = useRouter();
  const { status, user, accessToken, logout } = useRequireAuth();
  const [loggingOut, setLoggingOut] = useState(false);
  const [course, setCourse] = useState<CourseSummary | null>(null);
  const [progress, setProgress] = useState<Progress | null>(null);
  const [quests, setQuests] = useState<Quest[] | null>(null);

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
  }, [status, accessToken]);

  if (status !== "authenticated" || !user) {
    return (
      <div className="flex flex-1 items-center justify-center px-6">
        <p className="text-slate-400">Loading…</p>
      </div>
    );
  }

  async function handleLogout() {
    setLoggingOut(true);
    try {
      await logout();
      router.push("/login");
    } finally {
      setLoggingOut(false);
    }
  }

  const courseProgress = progress?.course_progress.find((cp) => cp.course_id === course?.id);

  return (
    <div className="flex flex-1 flex-col items-center px-6 py-16">
      <div className="flex w-full max-w-xl flex-col gap-6">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-semibold text-slate-50">Good to see you 👋</h1>
            <p className="text-sm text-slate-400">{user.email}</p>
          </div>
          <div className="flex items-center gap-3">
            {progress && <StreakBadge days={progress.current_streak} />}
            {progress && <GemBadge count={progress.gem_balance} />}
            <PrimaryButton onClick={handleLogout} disabled={loggingOut} variant="secondary">
              {loggingOut ? "Logging out…" : "Log out"}
            </PrimaryButton>
          </div>
        </div>

        {progress && (
          <div className="rounded-2xl border border-slate-800 bg-slate-900/60 p-6">
            <div className="mb-2 flex items-center justify-between text-sm">
              <h2 className="font-semibold uppercase tracking-wide text-slate-400">Daily goal</h2>
              <span className="text-slate-300">
                {progress.xp_today} / {progress.daily_goal_xp} XP
              </span>
            </div>
            <ProgressBar
              value={progress.xp_today}
              max={progress.daily_goal_xp}
              label="Daily goal progress"
            />
          </div>
        )}

        {quests && quests.length > 0 && (
          <div className="rounded-2xl border border-slate-800 bg-slate-900/60 p-6">
            <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-slate-400">
              Daily quests
            </h2>
            <div className="flex flex-col gap-2">
              {quests.map((quest) => (
                <QuestCard key={quest.id} quest={quest} />
              ))}
            </div>
          </div>
        )}

        <div className="rounded-2xl border border-slate-800 bg-slate-900/60 p-6">
          <h2 className="mb-1 text-sm font-semibold uppercase tracking-wide text-slate-400">
            Compete
          </h2>
          <p className="text-sm text-slate-400">
            {progress
              ? `You're in the ${LEAGUE_TIER_LABELS[progress.league_tier] ?? progress.league_tier} league this week.`
              : "See how you stack up against other learners."}
          </p>
          <div className="mt-4 flex gap-4">
            <Link
              href="/leaderboard"
              className="inline-flex items-center gap-1.5 rounded-lg border border-cyan-700 px-4 py-2 text-sm font-semibold text-cyan-300 transition-colors hover:bg-cyan-950/40"
            >
              {progress && (
                <span aria-hidden>{LEAGUE_TIER_ICONS[progress.league_tier] ?? "🏅"}</span>
              )}
              Leaderboard
            </Link>
            <Link
              href="/friends"
              className="inline-flex items-center rounded-lg border border-slate-700 px-4 py-2 text-sm font-semibold text-slate-200 transition-colors hover:bg-slate-800"
            >
              Friends
            </Link>
          </div>
        </div>

        {course && (
          <div className="rounded-2xl border border-slate-800 bg-slate-900/60 p-6">
            <h2 className="mb-1 text-sm font-semibold uppercase tracking-wide text-slate-400">
              Continue learning
            </h2>
            <p className="text-lg text-slate-100">{course.title}</p>
            <p className="mt-1 text-sm text-slate-400">
              {course.unit_count} units · {course.lesson_count} lessons
            </p>
            {courseProgress && (
              <div className="mt-3 flex flex-col gap-1.5">
                <ProgressBar
                  value={courseProgress.completed_lessons}
                  max={courseProgress.total_lessons}
                  colorClassName="bg-emerald-500"
                  label={`${course.title} course progress`}
                />
                <span className="text-xs text-slate-400">
                  {courseProgress.completed_lessons} / {courseProgress.total_lessons} lessons
                  complete
                </span>
              </div>
            )}
            <Link
              href="/learn"
              className="mt-4 inline-block rounded-lg bg-cyan-500 px-4 py-2 text-sm font-semibold text-slate-950 transition-colors hover:bg-cyan-400"
            >
              Continue lesson
            </Link>
          </div>
        )}

        <div className="rounded-2xl border border-slate-800 bg-slate-900/60 p-6">
          <h2 className="mb-1 text-sm font-semibold uppercase tracking-wide text-slate-400">
            Practice
          </h2>
          <p className="text-sm text-slate-400">
            A personalized set of questions targeting your weakest skills, past mistakes, and
            anything due for review.
          </p>
          <Link
            href="/practice"
            className="mt-4 inline-block rounded-lg border border-cyan-700 px-4 py-2 text-sm font-semibold text-cyan-300 transition-colors hover:bg-cyan-950/40"
          >
            Start practice
          </Link>
        </div>

        <div className="rounded-2xl border border-slate-800 bg-slate-900/60 p-6">
          <h2 className="mb-4 text-sm font-semibold uppercase tracking-wide text-slate-400">
            Your learning profile
          </h2>
          <dl className="grid grid-cols-2 gap-y-3 text-sm">
            <dt className="text-slate-400">Native language</dt>
            <dd className="text-slate-100">{languageName(user.preferences.native_language)}</dd>

            <dt className="text-slate-400">Learning</dt>
            <dd className="text-slate-100">{languageName(user.preferences.target_language)}</dd>

            <dt className="text-slate-400">Total XP</dt>
            <dd className="text-slate-100">{progress?.total_xp ?? 0} XP</dd>
          </dl>
          <div className="mt-4 flex gap-4">
            <Link
              href="/settings"
              className="text-sm font-medium text-cyan-400 hover:text-cyan-300"
            >
              Edit preferences →
            </Link>
            <Link
              href="/progress"
              className="text-sm font-medium text-cyan-400 hover:text-cyan-300"
            >
              Skill breakdown →
            </Link>
          </div>
        </div>

        {progress && (
          <div className="rounded-2xl border border-slate-800 bg-slate-900/60 p-6">
            <h2 className="mb-4 text-sm font-semibold uppercase tracking-wide text-slate-400">
              Achievements
            </h2>
            <div className="grid grid-cols-2 gap-3">
              {progress.achievements.map((achievement) => (
                <AchievementCard key={achievement.code} achievement={achievement} />
              ))}
            </div>
          </div>
        )}

        <div className="rounded-2xl border border-slate-800 bg-slate-900/60 p-6">
          <h2 className="mb-1 text-sm font-semibold uppercase tracking-wide text-slate-400">
            AI Tutor
          </h2>
          <p className="text-sm text-slate-400">
            Practice a real conversation in English - pick a scenario and get corrections as
            you go.
          </p>
          <Link
            href="/tutor"
            className="mt-4 inline-block rounded-lg border border-cyan-700 px-4 py-2 text-sm font-semibold text-cyan-300 transition-colors hover:bg-cyan-950/40"
          >
            Start a conversation
          </Link>
        </div>

        {user.is_admin && (
          <div className="rounded-2xl border border-amber-800 bg-amber-950/20 p-6">
            <h2 className="mb-1 text-sm font-semibold uppercase tracking-wide text-amber-400">
              Admin
            </h2>
            <p className="text-sm text-slate-400">
              Create and manage courses, units, lessons, and exercises.
            </p>
            <Link
              href="/admin"
              className="mt-4 inline-block rounded-lg border border-amber-700 px-4 py-2 text-sm font-semibold text-amber-300 transition-colors hover:bg-amber-950/40"
            >
              Open course editor
            </Link>
          </div>
        )}
      </div>
    </div>
  );
}
