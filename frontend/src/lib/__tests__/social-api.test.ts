import { afterEach, describe, expect, it, vi } from "vitest";

import {
  acceptFriendRequest,
  listFriends,
  listPendingRequests,
  removeFriend,
  sendFriendRequest,
} from "@/lib/social-api";

describe("social-api", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("listFriends returns the parsed friend list", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => [{ id: "u1", email: "b@example.com" }],
    });
    vi.stubGlobal("fetch", fetchMock);

    const friends = await listFriends("tok123");

    expect(friends).toHaveLength(1);
    const [url] = fetchMock.mock.calls[0];
    expect(url).toContain("/friends");
  });

  it("listPendingRequests returns incoming and outgoing lists", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ incoming: [], outgoing: [] }),
    });
    vi.stubGlobal("fetch", fetchMock);

    const requests = await listPendingRequests("tok123");

    expect(requests).toEqual({ incoming: [], outgoing: [] });
    const [url] = fetchMock.mock.calls[0];
    expect(url).toContain("/friends/requests");
  });

  it("sendFriendRequest posts the email in the body", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ id: "f1", status: "PENDING" }),
    });
    vi.stubGlobal("fetch", fetchMock);

    await sendFriendRequest("b@example.com", "tok123");

    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toContain("/friends/requests");
    expect(init.method).toBe("POST");
    expect(JSON.parse(init.body)).toEqual({ email: "b@example.com" });
  });

  it("acceptFriendRequest posts to the accept endpoint", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ id: "f1", status: "ACCEPTED" }),
    });
    vi.stubGlobal("fetch", fetchMock);

    const friendship = await acceptFriendRequest("f1", "tok123");

    expect(friendship.status).toBe("ACCEPTED");
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toContain("/friends/requests/f1/accept");
    expect(init.method).toBe("POST");
  });

  it("removeFriend sends a DELETE request", async () => {
    const fetchMock = vi.fn().mockResolvedValue({ ok: true, status: 204 });
    vi.stubGlobal("fetch", fetchMock);

    await removeFriend("f1", "tok123");

    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toContain("/friends/f1");
    expect(init.method).toBe("DELETE");
  });
});
