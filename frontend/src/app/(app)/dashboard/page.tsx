"use client";

import Link from "next/link";
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
import { getQuests } from "@/lib/gamification-api";
import { LEAGUE_TIER_ICONS, LEAGUE_TIER_LABELS } from "@/lib/league-labels";
import { getMastery, getReviewQueue } from "@/lib/mastery-api";
import { getProgress } from "@/lib/progress-api";
import type { CourseSummary } from "@/types/course";
import type { Quest } from "@/types/gamification";
import type { ReviewItem, SkillMastery } from "@/types/mastery";
import type { Progress } from "@/types/progress";

/** The learning "command center" - prioritizes one clear next action
 * (continue the current lesson) instead of the previous 9-equal-weight
 * card stack, and surfaces review-due/weakest-skill using data that was
 * already available via /me/review and /me/mastery but wasn't shown here
 * before. Every number on this page comes from a real API response -
 * nothing here is a placeholder or invented statistic. */
export default function DashboardPage() {
  const { status, user, accessToken } = useRequireAuth();
  const [course, setCourse] = useState<CourseSummary | null>(null);
  const [progress, setProgress] = useState<Progress | null>(null);
  const [quests, setQuests] = useState<Quest[] | null>(null);
  const [reviewQueue, setReviewQueue] = useState<ReviewItem[] | null>(null);
  const [weakestSkill, setWeakestSkill] = useState<SkillMastery | null>(null);

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
    getReviewQueue(accessToken)
      .then(setReviewQueue)
      .catch(() => setReviewQueue([]));
    getMastery(accessToken)
      .then((skills) => {
        const practiced = skills.filter((s) => s.attempt_count > 0);
        setWeakestSkill(
          practiced.length > 0
            ? practiced.reduce((weakest, s) => (s.mastery < weakest.mastery ? s : weakest))
            : null,
        );
      })
      .catch(() => setWeakestSkill(null));
  }, [status, accessToken]);

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

        <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
          {reviewQueue && reviewQueue.length > 0 && (
            <Card>
              <h2 className="mb-1 text-sm font-semibold uppercase tracking-wide text-amber-300">
                Review due
              </h2>
              <p className="text-sm text-slate-400">
                {reviewQueue.length} skill{reviewQueue.length === 1 ? "" : "s"} ready for review.
              </p>
              <ul className="mt-3 flex flex-col gap-1 text-sm text-slate-200">
                {reviewQueue.slice(0, 3).map((item) => (
                  <li key={item.skill_code}>{item.skill_name}</li>
                ))}
              </ul>
              <Link href="/progress" className="mt-4 inline-block text-sm font-medium text-cyan-400 hover:text-cyan-300">
                View progress →
              </Link>
            </Card>
          )}

          {weakestSkill && (
            <Card>
              <h2 className="mb-1 text-sm font-semibold uppercase tracking-wide text-slate-400">
                Recommended for you
              </h2>
              <p className="text-sm text-slate-400">
                Your weakest skill is{" "}
                <span className="text-slate-200">{weakestSkill.skill_name}</span> at{" "}
                {Math.round(weakestSkill.mastery)}%.
              </p>
              <Link
                href="/practice"
                className="mt-4 inline-block rounded-lg border border-cyan-700 px-4 py-2 text-sm font-semibold text-cyan-300 transition-colors duration-standard hover:bg-cyan-950/40"
              >
                Practice now
              </Link>
            </Card>
          )}

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
