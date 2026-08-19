import { afterEach, describe, expect, it, vi } from "vitest";

import { ApiError, login, logout, signup } from "@/lib/auth-api";

const sampleUser = {
  id: "1",
  email: "a@example.com",
  created_at: "2026-01-01T00:00:00Z",
  preferences: { native_language: "en", target_language: "es", daily_goal_xp: 50 },
};

describe("auth-api", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("signup sends credentials and returns the parsed token response", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 201,
      json: async () => ({ access_token: "tok", token_type: "bearer", user: sampleUser }),
    });
    vi.stubGlobal("fetch", fetchMock);

    const result = await signup({
      email: "a@example.com",
      password: "password123",
      native_language: "en",
      target_language: "es",
      daily_goal_xp: 50,
    });

    expect(result.access_token).toBe("tok");
    const [, init] = fetchMock.mock.calls[0];
    expect(init.credentials).toBe("include");
    expect(init.method).toBe("POST");
  });

  it("login throws ApiError with the server's detail message on failure", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: false,
        status: 401,
        json: async () => ({ detail: "Invalid email or password" }),
      }),
    );

    await expect(login({ email: "a@example.com", password: "wrong" })).rejects.toMatchObject({
      status: 401,
      message: "Invalid email or password",
    });
  });

  it("falls back to a generic message when the error body isn't JSON", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: false,
        status: 500,
        json: async () => {
          throw new Error("not json");
        },
      }),
    );

    await expect(login({ email: "a@example.com", password: "x" })).rejects.toBeInstanceOf(
      ApiError,
    );
  });

  it("logout resolves without a body on 204", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true, status: 204 }));

    await expect(logout()).resolves.toBeUndefined();
  });
});
