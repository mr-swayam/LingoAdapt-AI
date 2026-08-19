import { afterEach, describe, expect, it, vi } from "vitest";

import { getProgress, listAchievements } from "@/lib/progress-api";

describe("progress-api", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("getProgress sends the access token and returns the parsed progress", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ total_xp: 40, current_streak: 1 }),
    });
    vi.stubGlobal("fetch", fetchMock);

    const progress = await getProgress("tok123");

    expect(progress.total_xp).toBe(40);
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toContain("/me/progress");
    expect(init.headers.Authorization).toBe("Bearer tok123");
  });

  it("listAchievements returns the parsed achievement list", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => [{ code: "FIRST_LESSON", earned: true }],
      }),
    );

    const achievements = await listAchievements("tok123");

    expect(achievements).toHaveLength(1);
    expect(achievements[0].code).toBe("FIRST_LESSON");
  });
});
