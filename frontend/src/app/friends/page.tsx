"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { PrimaryButton, TextInput } from "@/components/ui/form";
import { useRequireAuth } from "@/hooks/use-require-auth";
import {
  acceptFriendRequest,
  ApiError,
  listFriends,
  listPendingRequests,
  removeFriend,
  sendFriendRequest,
} from "@/lib/social-api";
import type { Friend, PendingRequests } from "@/types/gamification";

export default function FriendsPage() {
  const { status, accessToken } = useRequireAuth();
  const [friends, setFriends] = useState<Friend[]>([]);
  const [pending, setPending] = useState<PendingRequests>({ incoming: [], outgoing: [] });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [email, setEmail] = useState("");
  const [sending, setSending] = useState(false);
  const [refreshKey, setRefreshKey] = useState(0);

  useEffect(() => {
    if (status !== "authenticated" || !accessToken) return;
    let cancelled = false;
    Promise.all([listFriends(accessToken), listPendingRequests(accessToken)])
      .then(([friendList, pendingRequests]) => {
        if (cancelled) return;
        setFriends(friendList);
        setPending(pendingRequests);
      })
      .catch((err) => {
        if (cancelled) return;
        setError(err instanceof ApiError ? err.message : "Couldn't load your friends.");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [status, accessToken, refreshKey]);

  if (status !== "authenticated") {
    return (
      <div className="flex flex-1 items-center justify-center px-6">
        <p className="text-slate-400">Loading…</p>
      </div>
    );
  }

  function refresh() {
    setRefreshKey((k) => k + 1);
  }

  async function handleSendRequest(e: React.FormEvent) {
    e.preventDefault();
    if (!accessToken || !email.trim() || sending) return;
    setSending(true);
    setError(null);
    try {
      await sendFriendRequest(email.trim(), accessToken);
      setEmail("");
      refresh();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Couldn't send that friend request.");
    } finally {
      setSending(false);
    }
  }

  async function handleAccept(friendshipId: string) {
    if (!accessToken) return;
    try {
      await acceptFriendRequest(friendshipId, accessToken);
      refresh();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Couldn't accept that request.");
    }
  }

  async function handleRemove(friendshipId: string) {
    if (!accessToken) return;
    try {
      await removeFriend(friendshipId, accessToken);
      refresh();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Couldn't remove that friend.");
    }
  }

  return (
    <div className="flex flex-1 flex-col items-center px-6 py-12">
      <div className="w-full max-w-xl">
        <div className="mb-6 flex items-center gap-4">
          <Link href="/dashboard" className="text-slate-400 hover:text-slate-300">
            ←
          </Link>
          <h1 className="text-2xl font-semibold text-slate-50">Friends</h1>
        </div>

        <form onSubmit={handleSendRequest} className="mb-8 flex gap-2">
          <TextInput
            type="email"
            required
            placeholder="Add a friend by email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className="flex-1"
          />
          <PrimaryButton type="submit" disabled={sending || !email.trim()}>
            {sending ? "Sending…" : "Add"}
          </PrimaryButton>
        </form>

        {error && <p className="mb-4 text-sm text-red-300">{error}</p>}

        {loading ? (
          <p className="text-sm text-slate-400">Loading…</p>
        ) : (
          <div className="flex flex-col gap-8">
            {pending.incoming.length > 0 && (
              <div>
                <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-slate-400">
                  Friend requests
                </h2>
                <div className="flex flex-col gap-2">
                  {pending.incoming.map((request) => (
                    <div
                      key={request.friendship_id}
                      className="flex items-center justify-between rounded-xl border border-slate-800 bg-slate-900/60 px-4 py-3"
                    >
                      <span className="text-sm text-slate-100">{request.other_user_email}</span>
                      <div className="flex gap-2">
                        <PrimaryButton onClick={() => handleAccept(request.friendship_id)}>
                          Accept
                        </PrimaryButton>
                        <PrimaryButton
                          onClick={() => handleRemove(request.friendship_id)}
                          variant="secondary"
                        >
                          Decline
                        </PrimaryButton>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {pending.outgoing.length > 0 && (
              <div>
                <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-slate-400">
                  Sent requests
                </h2>
                <div className="flex flex-col gap-2">
                  {pending.outgoing.map((request) => (
                    <div
                      key={request.friendship_id}
                      className="flex items-center justify-between rounded-xl border border-slate-800 bg-slate-900/60 px-4 py-3"
                    >
                      <span className="text-sm text-slate-300">{request.other_user_email}</span>
                      <span className="text-xs text-slate-400">Pending</span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            <div>
              <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-slate-400">
                Your friends
              </h2>
              {friends.length === 0 ? (
                <p className="text-sm text-slate-400">
                  No friends yet - add someone by email to see how you compare on the leaderboard.
                </p>
              ) : (
                <div className="flex flex-col gap-2">
                  {friends.map((friend) => (
                    <div
                      key={friend.id}
                      className="flex items-center justify-between rounded-xl border border-slate-800 bg-slate-900/60 px-4 py-3"
                    >
                      <span className="text-sm text-slate-100">{friend.email}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
