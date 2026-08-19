import { afterEach, describe, expect, it, vi } from "vitest";

import {
  ApiError,
  getExerciseAudio,
  listCourses,
  startLesson,
  submitAnswer,
  submitAnswerAudio,
} from "@/lib/course-api";

describe("course-api", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("listCourses returns the parsed course list", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => [{ id: "1", title: "English Foundations" }],
      }),
    );

    const courses = await listCourses();
    expect(courses).toHaveLength(1);
  });

  it("startLesson sends the access token as a Bearer header", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ lesson_attempt_id: "a", exercises: [] }),
    });
    vi.stubGlobal("fetch", fetchMock);

    await startLesson("lesson-1", "tok123");

    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toContain("/lessons/lesson-1/start");
    expect(init.method).toBe("POST");
    expect(init.headers.Authorization).toBe("Bearer tok123");
  });

  it("submitAnswer sends lesson_attempt_id and submitted_answer in the body", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ is_correct: true }),
    });
    vi.stubGlobal("fetch", fetchMock);

    await submitAnswer("ex-1", "attempt-1", { option_id: "opt-1" }, "tok123");

    const [, init] = fetchMock.mock.calls[0];
    const body = JSON.parse(init.body);
    expect(body).toEqual({
      lesson_attempt_id: "attempt-1",
      submitted_answer: { option_id: "opt-1" },
    });
  });

  it("submitAnswerAudio uploads lesson_attempt_id and the audio as multipart form data", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ is_correct: true, transcript: "Can I have the bill, please?" }),
    });
    vi.stubGlobal("fetch", fetchMock);
    const audio = new Blob(["fake-audio"], { type: "audio/webm" });

    const result = await submitAnswerAudio("ex-1", "attempt-1", audio, "tok123");

    expect(result.transcript).toBe("Can I have the bill, please?");
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toContain("/exercises/ex-1/answer-audio");
    expect(init.method).toBe("POST");
    expect(init.body).toBeInstanceOf(FormData);
  });

  it("getExerciseAudio requests the exercise's audio endpoint and returns a blob", async () => {
    const fakeBlob = new Blob(["fake-wav-bytes"], { type: "audio/wav" });
    const fetchMock = vi.fn().mockResolvedValue({ ok: true, blob: async () => fakeBlob });
    vi.stubGlobal("fetch", fetchMock);

    const blob = await getExerciseAudio("ex-1", "tok123");

    expect(blob).toBe(fakeBlob);
    const [url] = fetchMock.mock.calls[0];
    expect(url).toContain("/exercises/ex-1/audio");
  });

  it("throws ApiError with the server's detail message on failure", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: false,
        status: 404,
        json: async () => ({ detail: "Course not found" }),
      }),
    );

    await expect(listCourses()).rejects.toMatchObject({
      status: 404,
      message: "Course not found",
    });
    await expect(listCourses()).rejects.toBeInstanceOf(ApiError);
  });
});
