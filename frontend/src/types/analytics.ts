/** Real per-learner activity - see backend app/schemas/analytics.py's
 * LearnerActivityOut. Deliberately no retention or mastery-over-time
 * field: neither is backed by real per-user data (see
 * V2_PREMIUM_UI_AUDIT.md §11). */
export type CompletionStats = {
  started: number;
  completed: number;
  completion_rate: number;
};

export type WeeklyAccuracyPoint = {
  week_start: string;
  correct: number;
  total: number;
  accuracy: number;
};

export type LearnerActivity = {
  lesson_completion: CompletionStats;
  practice_completion: CompletionStats;
  accuracy_trend: WeeklyAccuracyPoint[];
};

export type ErrorType = "GRAMMAR" | "VOCABULARY" | "SPELLING" | "WORD_ORDER" | "OTHER";
export type ErrorSeverity = "LOW" | "MEDIUM" | "HIGH";

export type DetectedError = {
  id: string;
  error_type: ErrorType;
  severity: ErrorSeverity;
  description: string;
  submitted_text: string;
  created_at: string;
};
