import { afterEach, describe, expect, it, vi } from "vitest";

import { getMastery, getReviewQueue } from "@/lib/mastery-api";

describe("mastery-api", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("getMastery sends the access token and returns the parsed skill list", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => [{ skill_code: "GREETINGS", mastery: 54, level: "developing" }],
    });
    vi.stubGlobal("fetch", fetchMock);

    const skills = await getMastery("tok123");

    expect(skills).toHaveLength(1);
    expect(skills[0].skill_code).toBe("GREETINGS");
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toContain("/me/mastery");
    expect(init.headers.Authorization).toBe("Bearer tok123");
  });

  it("getReviewQueue returns the parsed review items", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => [{ skill_code: "GREETINGS", next_review_at: "2026-01-01T00:00:00Z" }],
      }),
    );

    const items = await getReviewQueue("tok123");

    expect(items).toHaveLength(1);
    expect(items[0].skill_code).toBe("GREETINGS");
  });
});
