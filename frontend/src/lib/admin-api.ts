import { apiRequest } from "@/lib/api-client";
import type {
  AnalyticsOverview,
  CourseAdmin,
  CourseAdminDetail,
  ExerciseAdmin,
  ExerciseOptionInput,
  ExerciseType,
  Language,
  Lesson,
  LessonAdminDetail,
  Skill,
  Unit,
  ValidationResult,
} from "@/types/admin";

export { ApiError } from "@/lib/api-client";

export function listLanguages(accessToken: string): Promise<Language[]> {
  return apiRequest("/admin/languages", { accessToken });
}

export function createLanguage(
  code: string,
  name: string,
  accessToken: string,
): Promise<Language> {
  return apiRequest("/admin/languages", {
    method: "POST",
    accessToken,
    body: JSON.stringify({ code, name }),
  });
}

export function listCourses(accessToken: string): Promise<CourseAdmin[]> {
  return apiRequest("/admin/courses", { accessToken });
}

export function createCourse(
  input: { language_id: string; title: string; description: string },
  accessToken: string,
): Promise<CourseAdmin> {
  return apiRequest("/admin/courses", {
    method: "POST",
    accessToken,
    body: JSON.stringify(input),
  });
}

export function getCourse(courseId: string, accessToken: string): Promise<CourseAdminDetail> {
  return apiRequest(`/admin/courses/${courseId}`, { accessToken });
}

export function updateCourse(
  courseId: string,
  input: { title?: string; description?: string },
  accessToken: string,
): Promise<CourseAdmin> {
  return apiRequest(`/admin/courses/${courseId}`, {
    method: "PATCH",
    accessToken,
    body: JSON.stringify(input),
  });
}

export function deleteCourse(courseId: string, accessToken: string): Promise<void> {
  return apiRequest(`/admin/courses/${courseId}`, { method: "DELETE", accessToken });
}

export function validateCourse(
  courseId: string,
  accessToken: string,
): Promise<ValidationResult> {
  return apiRequest(`/admin/courses/${courseId}/validate`, { accessToken });
}

export function publishCourse(courseId: string, accessToken: string): Promise<CourseAdmin> {
  return apiRequest(`/admin/courses/${courseId}/publish`, { method: "POST", accessToken });
}

export function unpublishCourse(courseId: string, accessToken: string): Promise<CourseAdmin> {
  return apiRequest(`/admin/courses/${courseId}/unpublish`, { method: "POST", accessToken });
}

export function listSkills(courseId: string, accessToken: string): Promise<Skill[]> {
  return apiRequest(`/admin/courses/${courseId}/skills`, { accessToken });
}

export function createSkill(
  input: { course_id: string; code: string; name: string },
  accessToken: string,
): Promise<Skill> {
  return apiRequest("/admin/skills", {
    method: "POST",
    accessToken,
    body: JSON.stringify(input),
  });
}

export function createUnit(
  input: { course_id: string; title: string },
  accessToken: string,
): Promise<Unit> {
  return apiRequest("/admin/units", {
    method: "POST",
    accessToken,
    body: JSON.stringify(input),
  });
}

export function deleteUnit(unitId: string, accessToken: string): Promise<void> {
  return apiRequest(`/admin/units/${unitId}`, { method: "DELETE", accessToken });
}

export function createLesson(
  input: { unit_id: string; title: string },
  accessToken: string,
): Promise<Lesson> {
  return apiRequest("/admin/lessons", {
    method: "POST",
    accessToken,
    body: JSON.stringify(input),
  });
}

export function getLesson(lessonId: string, accessToken: string): Promise<LessonAdminDetail> {
  return apiRequest(`/admin/lessons/${lessonId}`, { accessToken });
}

export function deleteLesson(lessonId: string, accessToken: string): Promise<void> {
  return apiRequest(`/admin/lessons/${lessonId}`, { method: "DELETE", accessToken });
}

export type ExerciseInput = {
  lesson_id: string;
  skill_id: string;
  type: ExerciseType;
  prompt: string;
  payload?: Record<string, unknown>;
  correct_answer?: Record<string, unknown>;
  explanation?: string | null;
  difficulty?: number;
  options?: ExerciseOptionInput[];
};

export function createExercise(
  input: ExerciseInput,
  accessToken: string,
): Promise<ExerciseAdmin> {
  return apiRequest("/admin/exercises", {
    method: "POST",
    accessToken,
    body: JSON.stringify(input),
  });
}

export function deleteExercise(exerciseId: string, accessToken: string): Promise<void> {
  return apiRequest(`/admin/exercises/${exerciseId}`, { method: "DELETE", accessToken });
}

export function getAnalyticsOverview(
  accessToken: string,
  days: number = 30,
): Promise<AnalyticsOverview> {
  return apiRequest(`/admin/analytics/overview?days=${days}`, { accessToken });
}
