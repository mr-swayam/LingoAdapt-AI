import { afterEach, describe, expect, it, vi } from "vitest";

import { getFriendsLeaderboard, getLeagueLeaderboard, getQuests } from "@/lib/gamification-api";

describe("gamification-api", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("getQuests sends the access token and returns the parsed list", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => [{ id: "q1", quest_type: "EARN_XP", completed: false }],
    });
    vi.stubGlobal("fetch", fetchMock);

    const quests = await getQuests("tok123");

    expect(quests).toHaveLength(1);
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toContain("/me/quests");
    expect(init.headers.Authorization).toBe("Bearer tok123");
  });

  it("getLeagueLeaderboard returns the parsed tier and entries", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ tier: "SPARK", week_start: "2026-08-17", entries: [] }),
    });
    vi.stubGlobal("fetch", fetchMock);

    const leaderboard = await getLeagueLeaderboard("tok123");

    expect(leaderboard.tier).toBe("SPARK");
    const [url] = fetchMock.mock.calls[0];
    expect(url).toContain("/leaderboard");
  });

  it("getFriendsLeaderboard requests the friends leaderboard endpoint", async () => {
    const fetchMock = vi.fn().mockResolvedValue({ ok: true, json: async () => [] });
    vi.stubGlobal("fetch", fetchMock);

    await getFriendsLeaderboard("tok123");

    const [url] = fetchMock.mock.calls[0];
    expect(url).toContain("/leaderboard/friends");
  });
});
