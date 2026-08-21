import type { ExerciseType } from "@/types/course";

export type MistakeSource = "LESSON" | "PRACTICE" | "TUTOR";

export type Mistake = {
  id: string;
  source: MistakeSource;
  skill_id: string;
  skill_name: string;
  /** Null for TUTOR mistakes - they aren't tied to a specific exercise. */
  exercise_id: string | null;
  exercise_type: ExerciseType | null;
  prompt: string | null;
  submitted_text: string;
  /** Honestly null for TUTOR mistakes - the AI tutor's corrected text is
   * never persisted anywhere, so this is never fabricated for that source. */
  correct_text: string | null;
  explanation: string | null;
  /** LISTENING mistakes only (word-diff category). */
  category: string | null;
  created_at: string;
};

export type MistakeList = {
  items: Mistake[];
  limit: number;
  offset: number;
  has_more: boolean;
};

export type RepeatedMistakeType = "REPEATED_DIFFICULTY" | "REPEATED_EXACT_MISTAKE";

export type RepeatedMistakeGroup = {
  type: RepeatedMistakeType;
  skill_id: string;
  skill_name: string;
  /** Set only for REPEATED_EXACT_MISTAKE groups. */
  exercise_id: string | null;
  count: number;
  most_recent: Mistake;
};
