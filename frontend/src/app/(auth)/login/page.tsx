"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { ErrorText, Field, PrimaryButton, TextInput } from "@/components/ui/form";
import { ApiError } from "@/lib/auth-api";
import { useAuth } from "@/lib/auth-context";

export default function LoginPage() {
  const router = useRouter();
  const { login } = useAuth();

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      await login({ email, password });
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
        <h1 className="text-2xl font-semibold text-slate-50">Welcome back</h1>
        <p className="text-sm text-slate-400">Log in to continue learning.</p>
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
            autoComplete="current-password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
        </Field>

        <ErrorText>{error}</ErrorText>

        <PrimaryButton type="submit" disabled={submitting}>
          {submitting ? "Logging in…" : "Log in"}
        </PrimaryButton>
      </form>

      <p className="text-sm text-slate-400">
        New here?{" "}
        <Link href="/signup" className="font-medium text-cyan-400 hover:text-cyan-300">
          Create an account
        </Link>
      </p>
    </div>
  );
}
