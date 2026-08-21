"use client";

import { useEffect, useState } from "react";

import { Card } from "@/components/ui/Card";
import { ProgressBar } from "@/components/ui/ProgressBar";
import { SkeletonCard } from "@/components/ui/Skeleton";
import { useRequireAuth } from "@/hooks/use-require-auth";
import { getMastery, getReviewQueue } from "@/lib/mastery-api";
import { getMyActivity, getMyErrors } from "@/lib/progress-api";
import type { DetectedError, LearnerActivity } from "@/types/analytics";
import type { ReviewItem, SkillLevel, SkillMastery } from "@/types/mastery";

const LEVEL_COLOR: Record<SkillLevel, string> = {
  strong: "bg-emerald-500",
  developing: "bg-cyan-500",
  weak: "bg-amber-500",
};

const LEVEL_LABEL: Record<SkillLevel, string> = {
  strong: "Strong",
  developing: "Developing",
  weak: "Needs work",
};

const ERROR_TYPE_LABEL: Record<string, string> = {
  GRAMMAR: "Grammar",
  VOCABULARY: "Vocabulary",
  SPELLING: "Spelling",
  WORD_ORDER: "Word order",
  OTHER: "Other",
};

/** Real, per-learner analytics - every number here traces to a real
 * backend query (see V2_PREMIUM_UI_AUDIT.md §11). Deliberately does not
 * show retention (not a coherent single-user metric) or a mastery-over-
 * time chart (SkillMastery is a snapshot with no stored history) -
 * accuracy-over-time (from the append-only LearningEvent log) is shown
 * instead, since that IS real. */
export default function ProgressPage() {
  const { status, accessToken } = useRequireAuth();
  const [skills, setSkills] = useState<SkillMastery[] | null>(null);
  const [reviewQueue, setReviewQueue] = useState<ReviewItem[]>([]);
  const [activity, setActivity] = useState<LearnerActivity | null>(null);
  const [errors, setErrors] = useState<DetectedError[]>([]);

  useEffect(() => {
    if (status !== "authenticated" || !accessToken) return;
    getMastery(accessToken)
      .then((data) => setSkills([...data].sort((a, b) => b.mastery - a.mastery)))
      .catch(() => setSkills([]));
    getReviewQueue(accessToken)
      .then(setReviewQueue)
      .catch(() => setReviewQueue([]));
    getMyActivity(accessToken)
      .then(setActivity)
      .catch(() => setActivity(null));
    getMyErrors(accessToken)
      .then(setErrors)
      .catch(() => setErrors([]));
  }, [status, accessToken]);

  if (status !== "authenticated" || skills === null) {
    return (
      <div className="flex flex-1 flex-col items-center px-6 py-16">
        <div className="w-full max-w-xl">
          <SkeletonCard />
        </div>
      </div>
    );
  }

  const weakSkills = skills.filter((s) => s.attempt_count > 0 && s.level === "weak");
  const mistakeCounts = errors.reduce<Record<string, number>>((acc, err) => {
    acc[err.error_type] = (acc[err.error_type] ?? 0) + 1;
    return acc;
  }, {});
  const topMistakes = Object.entries(mistakeCounts).sort((a, b) => b[1] - a[1]).slice(0, 5);

  return (
    <div className="flex flex-1 flex-col items-center px-6 py-16">
      <div className="flex w-full max-w-xl flex-col gap-6">
        <div>
          <h1 className="text-2xl font-semibold text-slate-50">Your Progress</h1>
          <p className="mt-1 text-sm text-slate-400">
            Skill mastery builds from every exercise you answer, weighted toward recent
            performance.
          </p>
        </div>

        {activity && (
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <Card>
              <p className="text-xs font-semibold uppercase tracking-wide text-slate-400">
                Lessons completed
              </p>
              <p className="mt-1 text-2xl font-semibold text-slate-50">
                {activity.lesson_completion.completed}
                <span className="text-sm font-normal text-slate-400">
                  {" "}
                  / {activity.lesson_completion.started} started
                </span>
              </p>
            </Card>
            <Card>
              <p className="text-xs font-semibold uppercase tracking-wide text-slate-400">
                Practice sessions completed
              </p>
              <p className="mt-1 text-2xl font-semibold text-slate-50">
                {activity.practice_completion.completed}
                <span className="text-sm font-normal text-slate-400">
                  {" "}
                  / {activity.practice_completion.started} started
                </span>
              </p>
            </Card>
          </div>
        )}

        {activity && activity.accuracy_trend.some((p) => p.total > 0) && (
          <Card>
            <p className="mb-3 text-xs font-semibold uppercase tracking-wide text-slate-400">
              Accuracy - last 8 weeks
            </p>
            <AccuracyTrend points={activity.accuracy_trend} />
          </Card>
        )}

        {reviewQueue.length > 0 && (
          <Card variant="warning">
            <h2 className="mb-2 text-sm font-semibold uppercase tracking-wide text-amber-300">
              Due for review
            </h2>
            <ul className="flex flex-col gap-1 text-sm text-slate-200">
              {reviewQueue.map((item) => (
                <li key={item.skill_code}>{item.skill_name}</li>
              ))}
            </ul>
          </Card>
        )}

        {weakSkills.length > 0 && (
          <Card>
            <h2 className="mb-2 text-sm font-semibold uppercase tracking-wide text-slate-400">
              Weak skills
            </h2>
            <ul className="flex flex-col gap-1 text-sm text-slate-200">
              {weakSkills.map((s) => (
                <li key={s.skill_code}>
                  {s.skill_name} <span className="text-slate-400">({Math.round(s.mastery)}%)</span>
                </li>
              ))}
            </ul>
          </Card>
        )}

        {topMistakes.length > 0 && (
          <Card>
            <h2 className="mb-2 text-sm font-semibold uppercase tracking-wide text-slate-400">
              Common mistakes
            </h2>
            <ul className="flex flex-col gap-1 text-sm text-slate-200">
              {topMistakes.map(([type, count]) => (
                <li key={type} className="flex justify-between">
                  <span>{ERROR_TYPE_LABEL[type] ?? type}</span>
                  <span className="text-slate-400">{count}</span>
                </li>
              ))}
            </ul>
          </Card>
        )}

        <div className="flex flex-col gap-4">
          <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-400">
            Skill mastery
          </h2>
          {skills.length === 0 ? (
            <div className="rounded-2xl border border-dashed border-slate-800 p-8 text-center text-sm text-slate-400">
              Complete a lesson to start building your skill profile.
            </div>
          ) : (
            skills.map((skill) => (
              <Card key={skill.skill_code} padding="sm">
                <div className="mb-2 flex items-center justify-between">
                  <span className="text-sm font-medium text-slate-100">{skill.skill_name}</span>
                  <span className="text-xs text-slate-400">
                    {LEVEL_LABEL[skill.level]} · {Math.round(skill.mastery)}%
                  </span>
                </div>
                <ProgressBar
                  value={skill.mastery}
                  max={100}
                  colorClassName={LEVEL_COLOR[skill.level]}
                  label={`${skill.skill_name} mastery`}
                />
                <p className="mt-2 text-xs text-slate-400">
                  {skill.correct_count} / {skill.attempt_count} correct
                </p>
              </Card>
            ))
          )}
        </div>
      </div>
    </div>
  );
}

function AccuracyTrend({ points }: { points: LearnerActivity["accuracy_trend"] }) {
  return (
    <div className="flex h-20 items-end gap-1.5">
      {points.map((point) => {
        const heightPercent = point.total > 0 ? Math.max(6, point.accuracy * 100) : 2;
        return (
          <div key={point.week_start} className="flex flex-1 flex-col items-center gap-1">
            <div
              className={`w-full rounded-t transition-all duration-large ${
                point.total > 0 ? "bg-cyan-500" : "bg-slate-800"
              }`}
              style={{ height: `${heightPercent}%` }}
              title={
                point.total > 0
                  ? `Week of ${point.week_start}: ${Math.round(point.accuracy * 100)}% (${point.correct}/${point.total})`
                  : `Week of ${point.week_start}: no activity`
              }
            />
          </div>
        );
      })}
    </div>
  );
}
