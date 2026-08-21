import { afterEach, describe, expect, it, vi } from "vitest";

import { getMistakes, getRepeatedMistakes } from "@/lib/mistakes-api";

describe("mistakes-api", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("getMistakes with no params requests the endpoint with no query string", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ items: [], limit: 20, offset: 0, has_more: false }),
    });
    vi.stubGlobal("fetch", fetchMock);

    await getMistakes("tok123");

    const [url] = fetchMock.mock.calls[0];
    expect(url).toContain("/me/mistakes");
    expect(url.endsWith("/me/mistakes")).toBe(true);
  });

  it("getMistakes encodes limit/offset/skillId/source as query params", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ items: [], limit: 5, offset: 5, has_more: false }),
    });
    vi.stubGlobal("fetch", fetchMock);

    await getMistakes("tok123", { limit: 5, offset: 5, skillId: "skill-1", source: "PRACTICE" });

    const [url] = fetchMock.mock.calls[0];
    expect(url).toContain("limit=5");
    expect(url).toContain("offset=5");
    expect(url).toContain("skill_id=skill-1");
    expect(url).toContain("source=PRACTICE");
  });

  it("getRepeatedMistakes returns the parsed group list", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => [{ type: "REPEATED_EXACT_MISTAKE", skill_id: "s1", count: 2 }],
    });
    vi.stubGlobal("fetch", fetchMock);

    const groups = await getRepeatedMistakes("tok123");

    expect(groups).toHaveLength(1);
    const [url] = fetchMock.mock.calls[0];
    expect(url).toContain("/me/mistakes/repeated");
  });
});
