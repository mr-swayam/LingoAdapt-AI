"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { Card } from "@/components/ui/Card";
import { ErrorText, Field, PrimaryButton, Select, TextInput } from "@/components/ui/form";
import { SkeletonText } from "@/components/ui/Skeleton";
import { useRequireAuth } from "@/hooks/use-require-auth";
import { LANGUAGE_OPTIONS, languageName } from "@/lib/languages";
import { getProgress } from "@/lib/progress-api";
import type { User, UserPreferences } from "@/types/auth";
import type { Progress } from "@/types/progress";

/** Profile + Preferences, consolidated into one page - before the V2
 * redesign, identity info (email, languages, total XP) lived only in a
 * dashboard card, disconnected from the preferences form that edits those
 * same languages. Both now live under Settings, reached via the shell's
 * secondary nav (TopBar's settings icon), not a primary nav destination. */
export default function SettingsPage() {
  const router = useRouter();
  const { status, user, accessToken, updatePreferences, logout } = useRequireAuth();
  const [progress, setProgress] = useState<Progress | null>(null);
  const [loggingOut, setLoggingOut] = useState(false);

  useEffect(() => {
    if (status !== "authenticated" || !accessToken) return;
    getProgress(accessToken)
      .then(setProgress)
      .catch(() => setProgress(null));
  }, [status, accessToken]);

  if (status !== "authenticated" || !user) {
    return (
      <div className="flex flex-1 flex-col items-center px-6 py-16">
        <div className="w-full max-w-md">
          <SkeletonText lines={3} />
        </div>
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

  return (
    <div className="flex flex-1 flex-col items-center px-6 py-16">
      <div className="flex w-full max-w-md flex-col gap-6">
        <Card>
          <h1 className="mb-4 text-2xl font-semibold text-slate-50">Profile</h1>
          <dl className="grid grid-cols-2 gap-y-3 text-sm">
            <dt className="text-slate-400">Email</dt>
            <dd className="text-slate-100">{user.email}</dd>
            <dt className="text-slate-400">Native language</dt>
            <dd className="text-slate-100">{languageName(user.preferences.native_language)}</dd>
            <dt className="text-slate-400">Learning</dt>
            <dd className="text-slate-100">{languageName(user.preferences.target_language)}</dd>
            <dt className="text-slate-400">Total XP</dt>
            <dd className="text-slate-100">{progress?.total_xp ?? 0} XP</dd>
          </dl>
          <PrimaryButton
            onClick={handleLogout}
            disabled={loggingOut}
            variant="secondary"
            className="mt-5 w-full"
          >
            {loggingOut ? "Logging out…" : "Log out"}
          </PrimaryButton>
        </Card>

        <Card>
          <h2 className="mb-4 text-lg font-semibold text-slate-50">Preferences</h2>
          {/* Keyed by user.id so this only mounts (and reads initial state) once the real user is loaded. */}
          <PreferencesForm key={user.id} user={user} updatePreferences={updatePreferences} />
        </Card>
      </div>
    </div>
  );
}

function PreferencesForm({
  user,
  updatePreferences,
}: {
  user: User;
  updatePreferences: (input: Partial<UserPreferences>) => Promise<void>;
}) {
  const [nativeLanguage, setNativeLanguage] = useState(user.preferences.native_language);
  const [targetLanguage, setTargetLanguage] = useState(user.preferences.target_language);
  const [dailyGoalXp, setDailyGoalXp] = useState(user.preferences.daily_goal_xp);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setSaved(false);

    if (nativeLanguage === targetLanguage) {
      setError("Native and target language must be different.");
      return;
    }

    setSubmitting(true);
    try {
      await updatePreferences({
        native_language: nativeLanguage,
        target_language: targetLanguage,
        daily_goal_xp: dailyGoalXp,
      });
      setSaved(true);
    } catch {
      setError("Couldn't save your preferences. Try again.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="flex flex-col gap-4">
      <div className="grid grid-cols-2 gap-4">
        <Field label="I speak" htmlFor="native_language">
          <Select
            id="native_language"
            value={nativeLanguage}
            onChange={(e) => setNativeLanguage(e.target.value)}
          >
            {LANGUAGE_OPTIONS.map((lang) => (
              <option key={lang.code} value={lang.code}>
                {lang.name}
              </option>
            ))}
          </Select>
        </Field>

        <Field label="I want to learn" htmlFor="target_language">
          <Select
            id="target_language"
            value={targetLanguage}
            onChange={(e) => setTargetLanguage(e.target.value)}
          >
            {LANGUAGE_OPTIONS.map((lang) => (
              <option key={lang.code} value={lang.code}>
                {lang.name}
              </option>
            ))}
          </Select>
        </Field>
      </div>

      <Field label="Daily goal (XP)" htmlFor="daily_goal_xp">
        <TextInput
          id="daily_goal_xp"
          type="number"
          min={10}
          max={1000}
          step={10}
          value={dailyGoalXp}
          onChange={(e) => setDailyGoalXp(Number(e.target.value))}
        />
      </Field>

      <ErrorText>{error}</ErrorText>
      {saved && <p className="text-sm text-emerald-400">Preferences saved.</p>}

      <PrimaryButton type="submit" disabled={submitting}>
        {submitting ? "Saving…" : "Save changes"}
      </PrimaryButton>
    </form>
  );
}
