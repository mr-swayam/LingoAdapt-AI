"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { Field, PrimaryButton, Select, TextArea, TextInput } from "@/components/ui/form";
import { useRequireAuth } from "@/hooks/use-require-auth";
import {
  ApiError,
  createCourse,
  createLanguage,
  listCourses,
  listLanguages,
} from "@/lib/admin-api";
import type { CourseAdmin, Language } from "@/types/admin";

export default function AdminCoursesPage() {
  const { status, user, accessToken } = useRequireAuth();
  const [courses, setCourses] = useState<CourseAdmin[]>([]);
  const [languages, setLanguages] = useState<Language[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [languageId, setLanguageId] = useState("");
  const [newLangCode, setNewLangCode] = useState("");
  const [newLangName, setNewLangName] = useState("");
  const [creating, setCreating] = useState(false);
  const [refreshKey, setRefreshKey] = useState(0);

  useEffect(() => {
    if (status !== "authenticated" || !accessToken) return;
    Promise.all([listCourses(accessToken), listLanguages(accessToken)])
      .then(([courseList, languageList]) => {
        setCourses(courseList);
        setLanguages(languageList);
        if (languageList.length > 0) setLanguageId((prev) => prev || languageList[0].id);
      })
      .catch((err) => setError(err instanceof ApiError ? err.message : "Couldn't load courses."))
      .finally(() => setLoading(false));
  }, [status, accessToken, refreshKey]);

  if (status !== "authenticated" || !user) {
    return (
      <div className="flex flex-1 items-center justify-center px-6">
        <p className="text-slate-400">Loading…</p>
      </div>
    );
  }

  if (!user.is_admin) {
    return (
      <div className="flex flex-1 flex-col items-center justify-center gap-4 px-6 text-center">
        <p className="text-red-300">Admin access required.</p>
        <Link href="/dashboard" className="text-sm text-cyan-400 hover:text-cyan-300">
          ← Back to dashboard
        </Link>
      </div>
    );
  }

  async function handleCreateLanguage(e: React.FormEvent) {
    e.preventDefault();
    if (!accessToken || !newLangCode.trim() || !newLangName.trim()) return;
    setError(null);
    try {
      const language = await createLanguage(newLangCode.trim(), newLangName.trim(), accessToken);
      setLanguages((prev) => [...prev, language]);
      setLanguageId(language.id);
      setNewLangCode("");
      setNewLangName("");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Couldn't create that language.");
    }
  }

  async function handleCreateCourse(e: React.FormEvent) {
    e.preventDefault();
    if (!accessToken || !title.trim() || !languageId) return;
    setCreating(true);
    setError(null);
    try {
      await createCourse({ language_id: languageId, title: title.trim(), description }, accessToken);
      setTitle("");
      setDescription("");
      setRefreshKey((k) => k + 1);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Couldn't create that course.");
    } finally {
      setCreating(false);
    }
  }

  return (
    <div className="flex flex-1 flex-col items-center px-6 py-12">
      <div className="w-full max-w-2xl">
        <div className="mb-6 flex items-center gap-4">
          <Link href="/dashboard" className="text-slate-400 hover:text-slate-300">
            ←
          </Link>
          <h1 className="flex-1 text-2xl font-semibold text-slate-50">Course Editor</h1>
          <Link href="/admin/analytics" className="text-sm text-cyan-400 hover:text-cyan-300">
            Analytics →
          </Link>
        </div>

        {error && <p className="mb-4 text-sm text-red-300">{error}</p>}

        <div className="mb-8 rounded-2xl border border-slate-800 bg-slate-900/60 p-6">
          <h2 className="mb-4 text-sm font-semibold uppercase tracking-wide text-slate-400">
            New course
          </h2>
          <form onSubmit={handleCreateCourse} className="flex flex-col gap-4">
            <Field label="Language" htmlFor="language">
              <div className="flex gap-2">
                <Select
                  id="language"
                  value={languageId}
                  onChange={(e) => setLanguageId(e.target.value)}
                  className="flex-1"
                >
                  {languages.length === 0 && <option value="">No languages yet</option>}
                  {languages.map((lang) => (
                    <option key={lang.id} value={lang.id}>
                      {lang.name} ({lang.code})
                    </option>
                  ))}
                </Select>
              </div>
            </Field>

            <details className="text-sm text-slate-400">
              <summary className="cursor-pointer text-cyan-400 hover:text-cyan-300">
                Add a new language
              </summary>
              <div className="mt-3 flex gap-2">
                <TextInput
                  placeholder="Code (e.g. de)"
                  value={newLangCode}
                  onChange={(e) => setNewLangCode(e.target.value)}
                  className="w-28"
                />
                <TextInput
                  placeholder="Name (e.g. German)"
                  value={newLangName}
                  onChange={(e) => setNewLangName(e.target.value)}
                  className="flex-1"
                />
                <PrimaryButton type="button" onClick={handleCreateLanguage} variant="secondary">
                  Add
                </PrimaryButton>
              </div>
            </details>

            <Field label="Title" htmlFor="title">
              <TextInput
                id="title"
                required
                value={title}
                onChange={(e) => setTitle(e.target.value)}
              />
            </Field>

            <Field label="Description" htmlFor="description">
              <TextArea
                id="description"
                rows={2}
                value={description}
                onChange={(e) => setDescription(e.target.value)}
              />
            </Field>

            <PrimaryButton type="submit" disabled={creating || !title.trim() || !languageId}>
              {creating ? "Creating…" : "Create draft course"}
            </PrimaryButton>
          </form>
        </div>

        <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-slate-400">
          All courses
        </h2>
        {loading ? (
          <p className="text-sm text-slate-400">Loading…</p>
        ) : courses.length === 0 ? (
          <p className="text-sm text-slate-400">No courses yet - create one above.</p>
        ) : (
          <div className="flex flex-col gap-2">
            {courses.map((course) => (
              <Link
                key={course.id}
                href={`/admin/courses/${course.id}`}
                className="flex items-center justify-between rounded-xl border border-slate-800 bg-slate-900/60 px-4 py-3 transition-colors hover:border-cyan-700"
              >
                <div>
                  <p className="text-sm font-medium text-slate-100">{course.title}</p>
                  <p className="text-xs text-slate-400">
                    {course.language_code} · {course.unit_count} units · {course.lesson_count}{" "}
                    lessons
                  </p>
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
              </Link>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
