"use client";

import Link from "next/link";
import { useState } from "react";

import { ErrorText, Field, PrimaryButton, Select, TextInput } from "@/components/ui/form";
import { useRequireAuth } from "@/hooks/use-require-auth";
import { LANGUAGE_OPTIONS } from "@/lib/languages";
import type { User, UserPreferences } from "@/types/auth";

export default function SettingsPage() {
  const { status, user, updatePreferences } = useRequireAuth();

  if (status !== "authenticated" || !user) {
    return (
      <div className="flex flex-1 items-center justify-center px-6">
        <p className="text-slate-400">Loading…</p>
      </div>
    );
  }

  return (
    <div className="flex flex-1 flex-col items-center px-6 py-16">
      <div className="w-full max-w-md">
        <Link href="/dashboard" className="text-sm text-cyan-400 hover:text-cyan-300">
          ← Back to dashboard
        </Link>

        <div className="mt-4 flex flex-col gap-6 rounded-2xl border border-slate-800 bg-slate-900/60 p-8">
          <h1 className="text-2xl font-semibold text-slate-50">Preferences</h1>
          {/* Keyed by user.id so this only mounts (and reads initial state) once the real user is loaded. */}
          <PreferencesForm
            key={user.id}
            user={user}
            updatePreferences={updatePreferences}
          />
        </div>
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
