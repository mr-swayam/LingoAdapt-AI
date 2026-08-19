"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { ProgressBar } from "@/components/ui/ProgressBar";
import { useRequireAuth } from "@/hooks/use-require-auth";
import { getMastery, getReviewQueue } from "@/lib/mastery-api";
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

export default function ProgressPage() {
  const { status, accessToken } = useRequireAuth();
  const [skills, setSkills] = useState<SkillMastery[] | null>(null);
  const [reviewQueue, setReviewQueue] = useState<ReviewItem[]>([]);

  useEffect(() => {
    if (status !== "authenticated" || !accessToken) return;
    getMastery(accessToken)
      .then((data) => setSkills([...data].sort((a, b) => b.mastery - a.mastery)))
      .catch(() => setSkills([]));
    getReviewQueue(accessToken)
      .then(setReviewQueue)
      .catch(() => setReviewQueue([]));
  }, [status, accessToken]);

  if (status !== "authenticated" || skills === null) {
    return (
      <div className="flex flex-1 items-center justify-center px-6">
        <p className="text-slate-400">Loading…</p>
      </div>
    );
  }

  return (
    <div className="flex flex-1 flex-col items-center px-6 py-16">
      <div className="w-full max-w-xl">
        <Link href="/dashboard" className="text-sm text-cyan-400 hover:text-cyan-300">
          ← Back to dashboard
        </Link>

        <h1 className="mt-4 text-2xl font-semibold text-slate-50">Your Progress</h1>
        <p className="mt-1 text-sm text-slate-400">
          Skill mastery builds from every exercise you answer, weighted toward recent
          performance.
        </p>

        {reviewQueue.length > 0 && (
          <div className="mt-6 rounded-2xl border border-amber-800 bg-amber-950/30 p-6">
            <h2 className="mb-2 text-sm font-semibold uppercase tracking-wide text-amber-300">
              Due for review
            </h2>
            <ul className="flex flex-col gap-1 text-sm text-slate-200">
              {reviewQueue.map((item) => (
                <li key={item.skill_code}>{item.skill_name}</li>
              ))}
            </ul>
          </div>
        )}

        <div className="mt-6 flex flex-col gap-4">
          {skills.length === 0 ? (
            <div className="rounded-2xl border border-dashed border-slate-800 p-8 text-center text-sm text-slate-400">
              Complete a lesson to start building your skill profile.
            </div>
          ) : (
            skills.map((skill) => (
              <div
                key={skill.skill_code}
                className="rounded-2xl border border-slate-800 bg-slate-900/60 p-5"
              >
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
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
}
