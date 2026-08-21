"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { EmptyState } from "@/components/ui/EmptyState";
import { ErrorState } from "@/components/ui/ErrorState";
import { SkeletonCard } from "@/components/ui/Skeleton";
import { useRequireAuth } from "@/hooks/use-require-auth";
import { ApiError, getCourse, listCourses } from "@/lib/course-api";
import type { CourseDetail, CourseSummary, LessonSummary } from "@/types/course";

export default function LearnPage() {
  const { status, accessToken } = useRequireAuth();
  const [courses, setCourses] = useState<CourseSummary[] | null>(null);
  const [selectedCourseId, setSelectedCourseId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (status !== "authenticated") return;

    let cancelled = false;
    listCourses()
      .then((courseList) => {
        if (cancelled) return;
        setCourses(courseList);
        // A single published course is still the common case - skip the
        // picker and go straight to it, same UX as before Phase 10 made
        // multiple courses possible.
        if (courseList.length === 1) setSelectedCourseId(courseList[0].id);
      })
      .catch((err) => {
        if (cancelled) return;
        setError(err instanceof ApiError ? err.message : "Couldn't load courses.");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [status]);

  if (status !== "authenticated" || !accessToken) {
    return (
      <div className="flex flex-1 flex-col items-center px-6 py-16">
        <div className="w-full max-w-2xl">
          <SkeletonCard />
        </div>
      </div>
    );
  }

  const showCoursePicker = Boolean(selectedCourseId && courses && courses.length > 1);

  return (
    <div className="flex flex-1 flex-col items-center px-6 py-16">
      <div className="w-full max-w-2xl">
        {showCoursePicker && (
          <button
            onClick={() => setSelectedCourseId(null)}
            className="mb-4 text-sm text-cyan-400 hover:text-cyan-300"
          >
            ← Back to courses
          </button>
        )}

        <div className="flex flex-col gap-8">
          {loading && <SkeletonCard />}
          {error && <ErrorState description={error} />}
          {!loading && !error && courses && courses.length === 0 && (
            <EmptyState title="No courses available yet" description="Check back soon." />
          )}

          {!loading && !error && courses && courses.length > 1 && !selectedCourseId && (
            <div className="flex flex-col gap-3">
              <h1 className="text-2xl font-semibold text-slate-50">Choose a course</h1>
              {courses.map((course) => (
                <button
                  key={course.id}
                  onClick={() => setSelectedCourseId(course.id)}
                  className="flex flex-col items-start rounded-xl border border-slate-800 bg-slate-900/60 px-4 py-3 text-left transition-colors duration-standard hover:border-cyan-700"
                >
                  <span className="text-slate-100">{course.title}</span>
                  <span className="text-xs text-slate-400">
                    {course.language_name} · {course.unit_count} units · {course.lesson_count}{" "}
                    lessons
                  </span>
                </button>
              ))}
            </div>
          )}

          {selectedCourseId && <CourseUnits courseId={selectedCourseId} accessToken={accessToken} />}
        </div>
      </div>
    </div>
  );
}

function CourseUnits({ courseId, accessToken }: { courseId: string; accessToken: string }) {
  const [course, setCourse] = useState<CourseDetail | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    getCourse(courseId, accessToken)
      .then((detail) => {
        if (!cancelled) setCourse(detail);
      })
      .catch((err) => {
        if (!cancelled) {
          setError(err instanceof ApiError ? err.message : "Couldn't load this course.");
        }
      });
    return () => {
      cancelled = true;
    };
  }, [courseId, accessToken]);

  if (error) return <ErrorState description={error} />;
  if (!course) return <SkeletonCard />;

  const allLessons = course.units.flatMap((unit) => unit.lessons);
  const nextLessonId = allLessons.find((lesson) => !lesson.completed)?.id ?? null;

  return (
    <>
      <div>
        <h1 className="text-2xl font-semibold text-slate-50">{course.title}</h1>
        <p className="mt-1 text-sm text-slate-400">{course.description}</p>
      </div>

      {course.units.map((unit) => (
        <div key={unit.id} className="flex flex-col gap-3">
          <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-400">
            {unit.title}
          </h2>
          <ol className="flex flex-col">
            {unit.lessons.map((lesson, i) => (
              <LessonNode
                key={lesson.id}
                lesson={lesson}
                isNext={lesson.id === nextLessonId}
                isLast={i === unit.lessons.length - 1}
              />
            ))}
          </ol>
        </div>
      ))}
    </>
  );
}

/** One step of the learning path - a real visual replacing the previous
 * flat, undifferentiated list of bordered rows. Completion is real data
 * (backend-verified per learner, see V2_PREMIUM_UI_AUDIT.md §6); there is
 * deliberately no "locked" state, since the backend doesn't enforce or
 * track lesson-unlock prerequisites - showing one would be a fabricated
 * visual. */
function LessonNode({
  lesson,
  isNext,
  isLast,
}: {
  lesson: LessonSummary;
  isNext: boolean;
  isLast: boolean;
}) {
  return (
    <li className="relative flex pb-4 last:pb-0">
      {!isLast && (
        <span
          aria-hidden="true"
          className="absolute left-[15px] top-8 h-[calc(100%-1rem)] w-0.5 bg-slate-800"
        />
      )}
      <Link
        href={`/learn/${lesson.id}`}
        className="group relative z-10 flex flex-1 items-center gap-4 rounded-xl border border-slate-800 bg-slate-900/60 px-4 py-3 transition-colors duration-standard hover:border-cyan-700"
      >
        <span
          aria-hidden="true"
          className={
            "flex h-8 w-8 shrink-0 items-center justify-center rounded-full border-2 text-sm font-semibold " +
            (lesson.completed
              ? "border-emerald-500 bg-emerald-500/20 text-emerald-300"
              : isNext
                ? "border-cyan-500 bg-cyan-500/10 text-cyan-300"
                : "border-slate-700 text-slate-400")
          }
        >
          {lesson.completed ? "✓" : lesson.position}
        </span>
        <span className="flex-1">
          <span className="block text-slate-100">
            {lesson.title}
            {lesson.completed && <span className="sr-only"> (completed)</span>}
          </span>
          <span className="text-xs text-slate-400">{lesson.exercise_count} exercises</span>
        </span>
        {isNext && (
          <span className="rounded-full bg-cyan-500/10 px-2.5 py-1 text-xs font-medium text-cyan-300">
            Start
          </span>
        )}
      </Link>
    </li>
  );
}
