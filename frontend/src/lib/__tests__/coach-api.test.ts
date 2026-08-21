import { afterEach, describe, expect, it, vi } from "vitest";

import { getCoachInsight, refreshCoachInsight } from "@/lib/coach-api";

describe("coach-api", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("getCoachInsight sends the access token and returns the parsed response", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ has_sufficient_data: false, message: "Not enough data yet", insight: null }),
    });
    vi.stubGlobal("fetch", fetchMock);

    const result = await getCoachInsight("tok123");

    expect(result.has_sufficient_data).toBe(false);
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toContain("/me/coach");
    expect(init.headers.Authorization).toBe("Bearer tok123");
  });

  it("refreshCoachInsight POSTs to the refresh endpoint", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ has_sufficient_data: true, message: null, insight: { summary: "s" } }),
    });
    vi.stubGlobal("fetch", fetchMock);

    await refreshCoachInsight("tok123");

    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toContain("/me/coach/refresh");
    expect(init.method).toBe("POST");
  });
});
