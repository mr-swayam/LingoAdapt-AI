import { apiRequest, apiRequestBlob } from "@/lib/api-client";
import type {
  AnswerResult,
  AudioAnswerResult,
  CourseDetail,
  CourseSummary,
  LessonStartResponse,
  SubmittedAnswer,
} from "@/types/course";

export { ApiError } from "@/lib/api-client";

export function listCourses(): Promise<CourseSummary[]> {
  return apiRequest("/courses");
}

export function getCourse(courseId: string): Promise<CourseDetail> {
  return apiRequest(`/courses/${courseId}`);
}

export function startLesson(lessonId: string, accessToken: string): Promise<LessonStartResponse> {
  return apiRequest(`/lessons/${lessonId}/start`, { method: "POST", accessToken });
}

export function submitAnswer(
  exerciseId: string,
  lessonAttemptId: string,
  submittedAnswer: SubmittedAnswer,
  accessToken: string,
): Promise<AnswerResult> {
  return apiRequest(`/exercises/${exerciseId}/answer`, {
    method: "POST",
    accessToken,
    body: JSON.stringify({
      lesson_attempt_id: lessonAttemptId,
      submitted_answer: submittedAnswer,
    }),
  });
}

export function submitAnswerAudio(
  exerciseId: string,
  lessonAttemptId: string,
  audio: Blob,
  accessToken: string,
): Promise<AudioAnswerResult> {
  const form = new FormData();
  form.append("lesson_attempt_id", lessonAttemptId);
  form.append("file", audio, "speech.webm");
  return apiRequest(`/exercises/${exerciseId}/answer-audio`, {
    method: "POST",
    accessToken,
    body: form,
  });
}

export function getExerciseAudio(exerciseId: string, accessToken: string): Promise<Blob> {
  return apiRequestBlob(`/exercises/${exerciseId}/audio`, { accessToken });
}
