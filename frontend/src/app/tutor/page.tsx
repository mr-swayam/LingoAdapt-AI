"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { useRequireAuth } from "@/hooks/use-require-auth";
import { ApiError, listConversations, startConversation } from "@/lib/tutor-api";
import { SCENARIO_ICONS, SCENARIO_LABELS } from "@/lib/scenario-labels";
import { CONVERSATION_SCENARIOS, type Conversation, type ConversationScenario } from "@/types/conversation";

export default function TutorPage() {
  const router = useRouter();
  const { status, accessToken } = useRequireAuth();

  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [loadingHistory, setLoadingHistory] = useState(true);
  const [startingScenario, setStartingScenario] = useState<ConversationScenario | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (status !== "authenticated" || !accessToken) return;
    listConversations(accessToken)
      .then(setConversations)
      .catch(() => setConversations([]))
      .finally(() => setLoadingHistory(false));
  }, [status, accessToken]);

  if (status !== "authenticated") {
    return (
      <div className="flex flex-1 items-center justify-center px-6">
        <p className="text-slate-400">Loading…</p>
      </div>
    );
  }

  async function handleStart(scenario: ConversationScenario) {
    if (!accessToken) return;
    setStartingScenario(scenario);
    setError(null);
    try {
      const conversation = await startConversation(scenario, accessToken);
      router.push(`/tutor/${conversation.id}`);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Couldn't start a conversation.");
      setStartingScenario(null);
    }
  }

  return (
    <div className="flex flex-1 flex-col items-center px-6 py-12">
      <div className="w-full max-w-2xl">
        <div className="mb-8 flex items-center gap-4">
          <Link href="/dashboard" className="text-slate-400 hover:text-slate-300">
            ←
          </Link>
          <h1 className="text-2xl font-semibold text-slate-50">AI Tutor</h1>
        </div>

        {error && <p className="mb-4 text-sm text-red-300">{error}</p>}

        <div className="mb-10">
          <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-slate-400">
            Start a new conversation
          </h2>
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
            {CONVERSATION_SCENARIOS.map((scenario) => (
              <button
                key={scenario}
                onClick={() => handleStart(scenario)}
                disabled={startingScenario !== null}
                className="flex flex-col items-center gap-2 rounded-2xl border border-slate-800 bg-slate-900/60 px-4 py-5 text-center transition-colors hover:border-cyan-700 hover:bg-slate-900 disabled:cursor-not-allowed disabled:opacity-60"
              >
                <span className="text-2xl">{SCENARIO_ICONS[scenario]}</span>
                <span className="text-sm font-medium text-slate-200">
                  {SCENARIO_LABELS[scenario]}
                </span>
                {startingScenario === scenario && (
                  <span className="text-xs text-cyan-400">Starting…</span>
                )}
              </button>
            ))}
          </div>
        </div>

        <div>
          <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-slate-400">
            Conversation history
          </h2>
          {loadingHistory ? (
            <p className="text-sm text-slate-400">Loading…</p>
          ) : conversations.length === 0 ? (
            <p className="text-sm text-slate-400">
              No conversations yet - pick a scenario above to start practicing.
            </p>
          ) : (
            <div className="flex flex-col gap-2">
              {conversations.map((conversation) => (
                <Link
                  key={conversation.id}
                  href={`/tutor/${conversation.id}`}
                  className="flex items-center justify-between rounded-xl border border-slate-800 bg-slate-900/60 px-4 py-3 transition-colors hover:border-cyan-700"
                >
                  <div className="flex items-center gap-3">
                    <span className="text-lg">{SCENARIO_ICONS[conversation.scenario]}</span>
                    <div>
                      <p className="text-sm font-medium text-slate-200">
                        {SCENARIO_LABELS[conversation.scenario]}
                      </p>
                      {conversation.summary && (
                        <p className="text-xs text-slate-400">{conversation.summary}</p>
                      )}
                    </div>
                  </div>
                  <span
                    className={
                      "rounded-full px-2.5 py-0.5 text-xs font-medium " +
                      (conversation.status === "ACTIVE"
                        ? "bg-emerald-950/50 text-emerald-300"
                        : "bg-slate-800 text-slate-400")
                    }
                  >
                    {conversation.status === "ACTIVE" ? "Active" : "Ended"}
                  </span>
                </Link>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
