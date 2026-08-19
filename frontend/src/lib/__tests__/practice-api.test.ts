import { afterEach, describe, expect, it, vi } from "vitest";

import {
  startPractice,
  submitPracticeAnswer,
  submitPracticeAnswerAudio,
} from "@/lib/practice-api";

describe("practice-api", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("startPractice sends the access token and returns the parsed session", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ practice_session_id: "s1", total_count: 2, exercises: [] }),
    });
    vi.stubGlobal("fetch", fetchMock);

    const session = await startPractice("tok123");

    expect(session.practice_session_id).toBe("s1");
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toContain("/practice/start");
    expect(init.method).toBe("POST");
    expect(init.headers.Authorization).toBe("Bearer tok123");
  });

  it("submitPracticeAnswer sends exercise_id and submitted_answer in the body", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ is_correct: true, session_completed: false }),
    });
    vi.stubGlobal("fetch", fetchMock);

    await submitPracticeAnswer("session-1", "ex-1", { option_id: "opt-1" }, "tok123");

    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toContain("/practice/session-1/answer");
    const body = JSON.parse(init.body);
    expect(body).toEqual({ exercise_id: "ex-1", submitted_answer: { option_id: "opt-1" } });
  });

  it("submitPracticeAnswerAudio uploads exercise_id and the audio as multipart form data", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ is_correct: true, transcript: "Can I have the bill, please?" }),
    });
    vi.stubGlobal("fetch", fetchMock);
    const audio = new Blob(["fake-audio"], { type: "audio/webm" });

    const result = await submitPracticeAnswerAudio("session-1", "ex-1", audio, "tok123");

    expect(result.transcript).toBe("Can I have the bill, please?");
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toContain("/practice/session-1/answer-audio");
    expect(init.method).toBe("POST");
    expect(init.body).toBeInstanceOf(FormData);
  });
});
