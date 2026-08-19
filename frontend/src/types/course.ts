export type ExerciseType =
  | "MULTIPLE_CHOICE"
  | "FILL_BLANK"
  | "TRANSLATION"
  | "WORD_ORDER"
  | "MATCHING"
  | "SHORT_ANSWER"
  | "SPEAKING"
  | "LISTENING";

export type LessonSummary = {
  id: string;
  title: string;
  position: number;
  exercise_count: number;
};

export type Unit = {
  id: string;
  title: string;
  position: number;
  lessons: LessonSummary[];
};

export type CourseSummary = {
  id: string;
  title: string;
  description: string;
  language_code: string;
  language_name: string;
  unit_count: number;
  lesson_count: number;
};

export type CourseDetail = {
  id: string;
  title: string;
  description: string;
  language_code: string;
  language_name: string;
  units: Unit[];
};

export type ExerciseOption = {
  id: string;
  text: string;
  match_group: "left" | "right" | null;
};

export type Exercise = {
  id: string;
  type: ExerciseType;
  prompt: string;
  payload: Record<string, unknown>;
  options: ExerciseOption[];
};

export type LessonStartResponse = {
  lesson_attempt_id: string;
  lesson_id: string;
  lesson_title: string;
  status: "IN_PROGRESS" | "COMPLETED";
  total_count: number;
  correct_count: number;
  answered_exercise_ids: string[];
  exercises: Exercise[];
};

export type SubmittedAnswer =
  | { option_id: string }
  | { text: string }
  | { option_ids: string[] }
  | { pairs: { left_option_id: string; right_option_id: string }[] };

/** The subset ExerciseRenderer/FeedbackPanel actually need to render
 * feedback - both lesson AnswerResult and practice's PracticeAnswerResult
 * satisfy this structurally, so those components work for either without
 * an adapter object. */
export type ExerciseFeedback = {
  is_correct: boolean;
  correct_answer: Record<string, unknown>;
  explanation: string | null;
};

export type AnswerResult = ExerciseFeedback & {
  lesson_completed: boolean;
  correct_count: number;
  total_count: number;
  xp_earned: number;
  current_streak: number | null;
  new_achievements: string[];
};

/** Returned by the answer-audio endpoints (SPEAKING exercises) - same
 * shape as the JSON result, plus what the AI heard the learner say. */
export type AudioAnswerResult = AnswerResult & { transcript: string };
