"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { EmptyState } from "@/components/ui/EmptyState";
import { SkeletonText } from "@/components/ui/Skeleton";
import { useRequireAuth } from "@/hooks/use-require-auth";
import { ApiError, getFriendsLeaderboard, getLeagueLeaderboard } from "@/lib/gamification-api";
import { LEAGUE_TIER_ICONS, LEAGUE_TIER_LABELS } from "@/lib/league-labels";
import type { LeaderboardEntry, LeagueLeaderboard } from "@/types/gamification";

type Tab = "league" | "friends";

export default function LeaderboardPage() {
  const { status, accessToken } = useRequireAuth();
  const [tab, setTab] = useState<Tab>("league");

  if (status !== "authenticated" || !accessToken) {
    return (
      <div className="flex flex-1 flex-col items-center px-6 py-12">
        <div className="w-full max-w-xl">
          <SkeletonText lines={3} />
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-1 flex-col items-center px-6 py-12">
      <div className="w-full max-w-xl">
        <h1 className="mb-6 text-2xl font-semibold text-slate-50">Leaderboard</h1>

        <div className="mb-6 flex gap-2">
          <button
            type="button"
            onClick={() => setTab("league")}
            className={`rounded-lg px-4 py-2 text-sm font-medium transition-colors ${
              tab === "league"
                ? "bg-cyan-500 text-slate-950"
                : "border border-slate-800 text-slate-300 hover:border-slate-700"
            }`}
          >
            League
          </button>
          <button
            type="button"
            onClick={() => setTab("friends")}
            className={`rounded-lg px-4 py-2 text-sm font-medium transition-colors ${
              tab === "friends"
                ? "bg-cyan-500 text-slate-950"
                : "border border-slate-800 text-slate-300 hover:border-slate-700"
            }`}
          >
            Friends
          </button>
        </div>

        <LeaderboardTabContent key={tab} tab={tab} accessToken={accessToken} />
      </div>
    </div>
  );
}

function LeaderboardTabContent({ tab, accessToken }: { tab: Tab; accessToken: string }) {
  const [league, setLeague] = useState<LeagueLeaderboard | null>(null);
  const [friendEntries, setFriendEntries] = useState<LeaderboardEntry[] | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    const request =
      tab === "league" ? getLeagueLeaderboard(accessToken) : getFriendsLeaderboard(accessToken);
    request
      .then((data) => {
        if (cancelled) return;
        if (tab === "league") setLeague(data as LeagueLeaderboard);
        else setFriendEntries(data as LeaderboardEntry[]);
      })
      .catch((err) => {
        if (cancelled) return;
        setError(err instanceof ApiError ? err.message : "Couldn't load the leaderboard.");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [tab, accessToken]);

  const entries = tab === "league" ? league?.entries : friendEntries;

  return (
    <>
      {tab === "league" && league && (
        <div className="mb-4 flex items-center gap-2 rounded-xl border border-slate-800 bg-slate-900/60 px-4 py-3">
          <span className="text-2xl" aria-hidden>
            {LEAGUE_TIER_ICONS[league.tier]}
          </span>
          <div>
            <p className="text-sm font-semibold text-slate-100">
              {LEAGUE_TIER_LABELS[league.tier] ?? league.tier} League
            </p>
            <p className="text-xs text-slate-400">
              Top climbers move up each week - bottom finishers move down.
            </p>
          </div>
        </div>
      )}

      {error && <p className="mb-4 text-sm text-red-300">{error}</p>}

      {loading ? (
        <SkeletonText lines={3} />
      ) : entries && entries.length > 0 ? (
        <div className="flex flex-col gap-2">
          {entries.map((entry) => (
            <div
              key={entry.email}
              className={`flex items-center justify-between rounded-xl border px-4 py-3 ${
                entry.is_me ? "border-cyan-700 bg-cyan-950/30" : "border-slate-800 bg-slate-900/60"
              }`}
            >
              <div className="flex items-center gap-3">
                <span className="w-6 text-center text-sm font-semibold text-slate-400">
                  {entry.rank}
                </span>
                <span className="text-sm text-slate-100">
                  {entry.email}
                  {entry.is_me && <span className="ml-2 text-xs text-cyan-400">(you)</span>}
                </span>
              </div>
              <span className="text-sm font-semibold text-slate-200">{entry.weekly_xp} XP</span>
            </div>
          ))}
        </div>
      ) : (
        <EmptyState
          icon="🏆"
          title={tab === "friends" ? "No friends ranked yet" : "No one here yet"}
          description={
            tab === "friends" ? "Add friends to see how you compare this week." : undefined
          }
        />
      )}

      {tab === "friends" && (
        <Link
          href="/friends"
          className="mt-4 inline-block text-sm font-medium text-cyan-400 hover:text-cyan-300"
        >
          Manage friends →
        </Link>
      )}
    </>
  );
}
