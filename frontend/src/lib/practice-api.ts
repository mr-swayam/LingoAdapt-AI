import { apiRequest } from "@/lib/api-client";
import type { SubmittedAnswer } from "@/types/course";
import type {
  PracticeAnswerResult,
  PracticeAudioAnswerResult,
  PracticeStartResponse,
} from "@/types/practice";

export { ApiError } from "@/lib/api-client";

export function startPractice(accessToken: string): Promise<PracticeStartResponse> {
  return apiRequest("/practice/start", { method: "POST", accessToken });
}

export function submitPracticeAnswer(
  sessionId: string,
  exerciseId: string,
  submittedAnswer: SubmittedAnswer,
  accessToken: string,
): Promise<PracticeAnswerResult> {
  return apiRequest(`/practice/${sessionId}/answer`, {
    method: "POST",
    accessToken,
    body: JSON.stringify({ exercise_id: exerciseId, submitted_answer: submittedAnswer }),
  });
}

export function submitPracticeAnswerAudio(
  sessionId: string,
  exerciseId: string,
  audio: Blob,
  accessToken: string,
): Promise<PracticeAudioAnswerResult> {
  const form = new FormData();
  form.append("exercise_id", exerciseId);
  form.append("file", audio, "speech.webm");
  return apiRequest(`/practice/${sessionId}/answer-audio`, {
    method: "POST",
    accessToken,
    body: form,
  });
}
