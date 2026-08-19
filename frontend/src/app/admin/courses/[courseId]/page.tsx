"use client";

import Link from "next/link";
import { use, useEffect, useState } from "react";

import { Field, PrimaryButton, TextInput } from "@/components/ui/form";
import { useRequireAuth } from "@/hooks/use-require-auth";
import {
  ApiError,
  createLesson,
  createSkill,
  createUnit,
  deleteUnit,
  getCourse,
  listSkills,
  publishCourse,
  unpublishCourse,
  validateCourse,
} from "@/lib/admin-api";
import type { CourseAdminDetail, Skill, ValidationResult } from "@/types/admin";

export default function AdminCourseDetailPage({
  params,
}: {
  params: Promise<{ courseId: string }>;
}) {
  const { courseId } = use(params);
  const { status, user, accessToken } = useRequireAuth();
  const [course, setCourse] = useState<CourseAdminDetail | null>(null);
  const [skills, setSkills] = useState<Skill[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [validation, setValidation] = useState<ValidationResult | null>(null);
  const [publishing, setPublishing] = useState(false);
  const [refreshKey, setRefreshKey] = useState(0);

  const [newUnitTitle, setNewUnitTitle] = useState("");
  const [lessonTitleByUnit, setLessonTitleByUnit] = useState<Record<string, string>>({});
  const [newSkillCode, setNewSkillCode] = useState("");
  const [newSkillName, setNewSkillName] = useState("");

  useEffect(() => {
    if (status !== "authenticated" || !accessToken) return;
    Promise.all([getCourse(courseId, accessToken), listSkills(courseId, accessToken)])
      .then(([courseData, skillList]) => {
        setCourse(courseData);
        setSkills(skillList);
      })
      .catch((err) => setError(err instanceof ApiError ? err.message : "Couldn't load course."))
      .finally(() => setLoading(false));
  }, [status, accessToken, courseId, refreshKey]);

  if (status !== "authenticated" || !user) {
    return (
      <div className="flex flex-1 items-center justify-center px-6">
        <p className="text-slate-400">Loading…</p>
      </div>
    );
  }
  if (!user.is_admin) {
    return (
      <div className="flex flex-1 items-center justify-center px-6">
        <p className="text-red-300">Admin access required.</p>
      </div>
    );
  }

  function refresh() {
    setRefreshKey((k) => k + 1);
  }

  async function handleAddUnit(e: React.FormEvent) {
    e.preventDefault();
    if (!accessToken || !newUnitTitle.trim()) return;
    setError(null);
    try {
      await createUnit({ course_id: courseId, title: newUnitTitle.trim() }, accessToken);
      setNewUnitTitle("");
      refresh();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Couldn't create that unit.");
    }
  }

  async function handleAddLesson(unitId: string) {
    const title = lessonTitleByUnit[unitId]?.trim();
    if (!accessToken || !title) return;
    setError(null);
    try {
      await createLesson({ unit_id: unitId, title }, accessToken);
      setLessonTitleByUnit((prev) => ({ ...prev, [unitId]: "" }));
      refresh();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Couldn't create that lesson.");
    }
  }

  async function handleDeleteUnit(unitId: string) {
    if (!accessToken) return;
    setError(null);
    try {
      await deleteUnit(unitId, accessToken);
      refresh();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Couldn't delete that unit.");
    }
  }

  async function handleAddSkill(e: React.FormEvent) {
    e.preventDefault();
    if (!accessToken || !newSkillCode.trim() || !newSkillName.trim()) return;
    setError(null);
    try {
      const skill = await createSkill(
        { course_id: courseId, code: newSkillCode.trim().toUpperCase(), name: newSkillName.trim() },
        accessToken,
      );
      setSkills((prev) => [...prev, skill]);
      setNewSkillCode("");
      setNewSkillName("");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Couldn't create that skill.");
    }
  }

  async function handleValidate() {
    if (!accessToken) return;
    setError(null);
    try {
      setValidation(await validateCourse(courseId, accessToken));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Couldn't validate this course.");
    }
  }

  async function handlePublishToggle() {
    if (!accessToken || !course) return;
    const wasPublished = course.is_published;
    setPublishing(true);
    setError(null);
    try {
      if (wasPublished) {
        await unpublishCourse(courseId, accessToken);
      } else {
        await publishCourse(courseId, accessToken);
      }
      refresh();
    } catch (err) {
      if (!wasPublished) {
        // A publish failure's real reason is the same validation error
        // list the Validate button already surfaces in full - this banner
        // just points the admin back to it rather than re-parsing detail.
        setError("Couldn't publish - run Validate to see what's missing.");
      } else {
        setError(err instanceof ApiError ? err.message : "Couldn't unpublish this course.");
      }
    } finally {
      setPublishing(false);
    }
  }

  if (loading || !course) {
    return (
      <div className="flex flex-1 items-center justify-center px-6">
        <p className="text-slate-400">Loading…</p>
      </div>
    );
  }

  return (
    <div className="flex flex-1 flex-col items-center px-6 py-12">
      <div className="w-full max-w-2xl">
        <div className="mb-6 flex items-center gap-4">
          <Link href="/admin" className="text-slate-400 hover:text-slate-300">
            ←
          </Link>
          <div className="flex-1">
            <h1 className="text-2xl font-semibold text-slate-50">{course.title}</h1>
            <p className="text-sm text-slate-400">{course.language_code}</p>
          </div>
          <span
            className={
              "rounded-full px-2.5 py-0.5 text-xs font-medium " +
              (course.is_published
                ? "bg-emerald-950/50 text-emerald-300"
                : "bg-slate-800 text-slate-400")
            }
          >
            {course.is_published ? "Published" : "Draft"}
          </span>
        </div>

        {error && <p className="mb-4 text-sm text-red-300">{error}</p>}

        <div className="mb-6 flex flex-wrap gap-2">
          <PrimaryButton onClick={handleValidate} variant="secondary">
            Validate
          </PrimaryButton>
          <PrimaryButton onClick={handlePublishToggle} disabled={publishing}>
            {publishing ? "Working…" : course.is_published ? "Unpublish" : "Publish"}
          </PrimaryButton>
        </div>

        {validation && (
          <div
            className={`mb-6 rounded-xl border p-4 text-sm ${
              validation.valid
                ? "border-emerald-800 bg-emerald-950/30 text-emerald-300"
                : "border-amber-800 bg-amber-950/30 text-amber-200"
            }`}
          >
            {validation.valid ? (
              "Ready to publish."
            ) : (
              <ul className="list-disc pl-5">
                {validation.errors.map((e) => (
                  <li key={e}>{e}</li>
                ))}
              </ul>
            )}
          </div>
        )}

        <div className="mb-8 rounded-2xl border border-slate-800 bg-slate-900/60 p-6">
          <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-slate-400">
            Skills
          </h2>
          <div className="mb-3 flex flex-wrap gap-2">
            {skills.map((skill) => (
              <span
                key={skill.id}
                className="rounded-full border border-slate-700 px-3 py-1 text-xs text-slate-300"
              >
                {skill.code}
              </span>
            ))}
          </div>
          <form onSubmit={handleAddSkill} className="flex gap-2">
            <TextInput
              placeholder="CODE"
              value={newSkillCode}
              onChange={(e) => setNewSkillCode(e.target.value)}
              className="w-32"
            />
            <TextInput
              placeholder="Skill name"
              value={newSkillName}
              onChange={(e) => setNewSkillName(e.target.value)}
              className="flex-1"
            />
            <PrimaryButton type="submit" variant="secondary">
              Add
            </PrimaryButton>
          </form>
        </div>

        <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-slate-400">
          Units &amp; lessons
        </h2>
        <div className="flex flex-col gap-4">
          {course.units.map((unit) => (
            <div key={unit.id} className="rounded-2xl border border-slate-800 bg-slate-900/60 p-5">
              <div className="mb-3 flex items-center justify-between">
                <p className="font-medium text-slate-100">{unit.title}</p>
                <button
                  onClick={() => handleDeleteUnit(unit.id)}
                  className="text-xs text-red-400 hover:text-red-300"
                >
                  Delete unit
                </button>
              </div>
              <div className="mb-3 flex flex-col gap-1.5">
                {unit.lessons.length === 0 && (
                  <p className="text-xs text-slate-400">No lessons yet.</p>
                )}
                {unit.lessons.map((lesson) => (
                  <Link
                    key={lesson.id}
                    href={`/admin/lessons/${lesson.id}`}
                    className="flex items-center justify-between rounded-lg border border-slate-800 bg-slate-950 px-3 py-2 text-sm transition-colors hover:border-cyan-700"
                  >
                    <span className="text-slate-200">{lesson.title}</span>
                    <span className="text-xs text-slate-400">
                      {lesson.exercise_count} exercise{lesson.exercise_count === 1 ? "" : "s"} →
                    </span>
                  </Link>
                ))}
              </div>
              <form
                onSubmit={(e) => {
                  e.preventDefault();
                  handleAddLesson(unit.id);
                }}
                className="mt-3 flex gap-2"
              >
                <TextInput
                  placeholder="New lesson title"
                  value={lessonTitleByUnit[unit.id] ?? ""}
                  onChange={(e) =>
                    setLessonTitleByUnit((prev) => ({ ...prev, [unit.id]: e.target.value }))
                  }
                  className="flex-1"
                />
                <PrimaryButton type="submit" variant="secondary">
                  Add lesson
                </PrimaryButton>
              </form>
            </div>
          ))}
        </div>

        <form onSubmit={handleAddUnit} className="mt-6 flex gap-2">
          <Field label="New unit" htmlFor="new-unit">
            <TextInput
              id="new-unit"
              placeholder="Unit title"
              value={newUnitTitle}
              onChange={(e) => setNewUnitTitle(e.target.value)}
            />
          </Field>
        </form>
        <PrimaryButton
          onClick={handleAddUnit}
          disabled={!newUnitTitle.trim()}
          variant="secondary"
          className="mt-2"
        >
          Add unit
        </PrimaryButton>
      </div>
    </div>
  );
}
