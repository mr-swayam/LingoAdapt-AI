"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { useRequireAuth } from "@/hooks/use-require-auth";
import { ApiError, getCourse, listCourses } from "@/lib/course-api";
import type { CourseDetail, CourseSummary } from "@/types/course";

export default function LearnPage() {
  const { status } = useRequireAuth();
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

  if (status !== "authenticated") {
    return (
      <div className="flex flex-1 items-center justify-center px-6">
        <p className="text-slate-400">Loading…</p>
      </div>
    );
  }

  const showCoursePicker = Boolean(selectedCourseId && courses && courses.length > 1);

  return (
    <div className="flex flex-1 flex-col items-center px-6 py-16">
      <div className="w-full max-w-2xl">
        {showCoursePicker ? (
          <button
            onClick={() => setSelectedCourseId(null)}
            className="text-sm text-cyan-400 hover:text-cyan-300"
          >
            ← Back to courses
          </button>
        ) : (
          <Link href="/dashboard" className="text-sm text-cyan-400 hover:text-cyan-300">
            ← Back to dashboard
          </Link>
        )}

        <div className="mt-4 flex flex-col gap-8">
          {loading && <p className="text-slate-400">Loading courses…</p>}
          {error && <p className="text-red-300">{error}</p>}
          {!loading && !error && courses && courses.length === 0 && (
            <p className="text-slate-400">No courses are available yet.</p>
          )}

          {!loading && !error && courses && courses.length > 1 && !selectedCourseId && (
            <div className="flex flex-col gap-3">
              <h1 className="text-2xl font-semibold text-slate-50">Choose a course</h1>
              {courses.map((course) => (
                <button
                  key={course.id}
                  onClick={() => setSelectedCourseId(course.id)}
                  className="flex flex-col items-start rounded-xl border border-slate-800 bg-slate-900/60 px-4 py-3 text-left transition-colors hover:border-cyan-700"
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

          {selectedCourseId && <CourseUnits courseId={selectedCourseId} />}
        </div>
      </div>
    </div>
  );
}

function CourseUnits({ courseId }: { courseId: string }) {
  const [course, setCourse] = useState<CourseDetail | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    getCourse(courseId)
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
  }, [courseId]);

  if (error) return <p className="text-red-300">{error}</p>;
  if (!course) return <p className="text-slate-400">Loading course…</p>;

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
          <div className="flex flex-col gap-2">
            {unit.lessons.map((lesson) => (
              <Link
                key={lesson.id}
                href={`/learn/${lesson.id}`}
                className="flex items-center justify-between rounded-xl border border-slate-800 bg-slate-900/60 px-4 py-3 transition-colors hover:border-cyan-700"
              >
                <span className="text-slate-100">{lesson.title}</span>
                <span className="text-xs text-slate-400">{lesson.exercise_count} exercises</span>
              </Link>
            ))}
          </div>
        </div>
      ))}
    </>
  );
}
