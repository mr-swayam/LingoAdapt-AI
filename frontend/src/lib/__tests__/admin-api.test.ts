import { afterEach, describe, expect, it, vi } from "vitest";

import {
  createCourse,
  createExercise,
  createLanguage,
  deleteCourse,
  getAnalyticsOverview,
  getCourse,
  getLesson,
  listCourses,
  publishCourse,
  validateCourse,
} from "@/lib/admin-api";

describe("admin-api", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("listCourses sends the access token and returns the parsed list", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => [{ id: "c1", title: "Course", is_published: false }],
    });
    vi.stubGlobal("fetch", fetchMock);

    const courses = await listCourses("tok123");

    expect(courses).toHaveLength(1);
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toContain("/admin/courses");
    expect(init.headers.Authorization).toBe("Bearer tok123");
  });

  it("createLanguage posts code and name", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ id: "l1", code: "de", name: "German" }),
    });
    vi.stubGlobal("fetch", fetchMock);

    await createLanguage("de", "German", "tok123");

    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toContain("/admin/languages");
    expect(init.method).toBe("POST");
    expect(JSON.parse(init.body)).toEqual({ code: "de", name: "German" });
  });

  it("createCourse posts the course fields", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ id: "c1", is_published: false }),
    });
    vi.stubGlobal("fetch", fetchMock);

    await createCourse({ language_id: "l1", title: "T", description: "d" }, "tok123");

    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toContain("/admin/courses");
    expect(init.method).toBe("POST");
    expect(JSON.parse(init.body)).toEqual({ language_id: "l1", title: "T", description: "d" });
  });

  it("getCourse requests the specific course id", async () => {
    const fetchMock = vi.fn().mockResolvedValue({ ok: true, json: async () => ({ id: "c1" }) });
    vi.stubGlobal("fetch", fetchMock);

    await getCourse("c1", "tok123");

    const [url] = fetchMock.mock.calls[0];
    expect(url).toContain("/admin/courses/c1");
  });

  it("deleteCourse sends a DELETE request", async () => {
    const fetchMock = vi.fn().mockResolvedValue({ ok: true, status: 204 });
    vi.stubGlobal("fetch", fetchMock);

    await deleteCourse("c1", "tok123");

    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toContain("/admin/courses/c1");
    expect(init.method).toBe("DELETE");
  });

  it("validateCourse returns the validation result", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ valid: false, errors: ["Course has no units"] }),
    });
    vi.stubGlobal("fetch", fetchMock);

    const result = await validateCourse("c1", "tok123");

    expect(result.valid).toBe(false);
    expect(result.errors).toEqual(["Course has no units"]);
    const [url] = fetchMock.mock.calls[0];
    expect(url).toContain("/admin/courses/c1/validate");
  });

  it("publishCourse posts to the publish endpoint", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ id: "c1", is_published: true }),
    });
    vi.stubGlobal("fetch", fetchMock);

    const course = await publishCourse("c1", "tok123");

    expect(course.is_published).toBe(true);
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toContain("/admin/courses/c1/publish");
    expect(init.method).toBe("POST");
  });

  it("getLesson requests the specific lesson id", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ id: "l1", exercises: [] }),
    });
    vi.stubGlobal("fetch", fetchMock);

    await getLesson("l1", "tok123");

    const [url] = fetchMock.mock.calls[0];
    expect(url).toContain("/admin/lessons/l1");
  });

  it("createExercise posts the full exercise payload including options", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ id: "e1", options: [] }),
    });
    vi.stubGlobal("fetch", fetchMock);

    await createExercise(
      {
        lesson_id: "l1",
        skill_id: "s1",
        type: "MULTIPLE_CHOICE",
        prompt: "Pick one",
        options: [{ text: "A", is_correct: true }],
      },
      "tok123",
    );

    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toContain("/admin/exercises");
    const body = JSON.parse(init.body);
    expect(body.type).toBe("MULTIPLE_CHOICE");
    expect(body.options).toEqual([{ text: "A", is_correct: true }]);
  });

  it("getAnalyticsOverview requests the overview endpoint with a days param", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        daily_active_users: [],
        lesson_completion: { started: 0, completed: 0, completion_rate: 0 },
        practice_completion: { started: 0, completed: 0, completion_rate: 0 },
        day1_retention: { cohort_size: 0, retained: 0, retention_rate: 0 },
        day7_retention: { cohort_size: 0, retained: 0, retention_rate: 0 },
        ai_stats: [],
        top_mistakes: [],
        weakest_skills: [],
        improvement_trend: [],
      }),
    });
    vi.stubGlobal("fetch", fetchMock);

    const overview = await getAnalyticsOverview("tok123", 7);

    expect(overview.ai_stats).toEqual([]);
    const [url] = fetchMock.mock.calls[0];
    expect(url).toContain("/admin/analytics/overview?days=7");
  });
});
