import { afterEach, describe, expect, it, vi } from "vitest";

import { getDailyPlan, todayLocalDate } from "@/lib/daily-plan-api";

describe("daily-plan-api", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("todayLocalDate returns the browser-local calendar date as YYYY-MM-DD", () => {
    const result = todayLocalDate();
    expect(result).toMatch(/^\d{4}-\d{2}-\d{2}$/);

    const now = new Date();
    const expected = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}-${String(
      now.getDate(),
    ).padStart(2, "0")}`;
    expect(result).toBe(expected);
  });

  it("getDailyPlan sends local_date as a query parameter", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ tasks: [], generated_for_date: "2026-01-01" }),
    });
    vi.stubGlobal("fetch", fetchMock);

    const plan = await getDailyPlan("tok123");

    expect(plan.generated_for_date).toBe("2026-01-01");
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toContain("/me/daily-plan?local_date=");
    expect(init.headers.Authorization).toBe("Bearer tok123");
  });
});
