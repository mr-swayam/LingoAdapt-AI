"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { ErrorText, Field, PrimaryButton, Select, TextInput } from "@/components/ui/form";
import { ApiError } from "@/lib/auth-api";
import { useAuth } from "@/lib/auth-context";
import { LANGUAGE_OPTIONS } from "@/lib/languages";

export default function SignupPage() {
  const router = useRouter();
  const { signup } = useAuth();

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [nativeLanguage, setNativeLanguage] = useState("en");
  const [targetLanguage, setTargetLanguage] = useState("es");
  const [dailyGoalXp, setDailyGoalXp] = useState(50);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);

    if (nativeLanguage === targetLanguage) {
      setError("Native and target language must be different.");
      return;
    }

    setSubmitting(true);
    try {
      await signup({
        email,
        password,
        native_language: nativeLanguage,
        target_language: targetLanguage,
        daily_goal_xp: dailyGoalXp,
      });
      router.push("/dashboard");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Something went wrong. Try again.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="flex flex-col gap-6 rounded-2xl border border-slate-800 bg-slate-900/60 p-8">
      <div className="flex flex-col gap-1">
        <h1 className="text-2xl font-semibold text-slate-50">Create your account</h1>
        <p className="text-sm text-slate-400">Start learning in a few seconds.</p>
      </div>

      <form onSubmit={handleSubmit} className="flex flex-col gap-4">
        <Field label="Email" htmlFor="email">
          <TextInput
            id="email"
            type="email"
            required
            autoComplete="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
          />
        </Field>

        <Field label="Password" htmlFor="password">
          <TextInput
            id="password"
            type="password"
            required
            minLength={8}
            autoComplete="new-password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
        </Field>

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

        <PrimaryButton type="submit" disabled={submitting}>
          {submitting ? "Creating account…" : "Sign up"}
        </PrimaryButton>
      </form>

      <p className="text-sm text-slate-400">
        Already have an account?{" "}
        <Link href="/login" className="font-medium text-cyan-400 hover:text-cyan-300">
          Log in
        </Link>
      </p>
    </div>
  );
}
