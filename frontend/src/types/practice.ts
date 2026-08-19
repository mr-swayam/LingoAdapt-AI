import type { Exercise } from "@/types/course";

export type PracticeStartResponse = {
  practice_session_id: string;
  status: "IN_PROGRESS" | "COMPLETED";
  total_count: number;
  correct_count: number;
  answered_exercise_ids: string[];
  exercises: Exercise[];
};

export type PracticeAnswerResult = {
  is_correct: boolean;
  correct_answer: Record<string, unknown>;
  explanation: string | null;
  session_completed: boolean;
  correct_count: number;
  total_count: number;
};

export type PracticeAudioAnswerResult = PracticeAnswerResult & { transcript: string };
