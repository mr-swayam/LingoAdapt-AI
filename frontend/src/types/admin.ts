export type ExerciseType =
  | "MULTIPLE_CHOICE"
  | "FILL_BLANK"
  | "TRANSLATION"
  | "WORD_ORDER"
  | "MATCHING"
  | "SHORT_ANSWER"
  | "SPEAKING"
  | "LISTENING";

export type Language = {
  id: string;
  code: string;
  name: string;
};

export type LessonSummary = {
  id: string;
  title: string;
  position: number;
  exercise_count: number;
};

export type UnitSummary = {
  id: string;
  title: string;
  position: number;
  lessons: LessonSummary[];
};

export type CourseAdmin = {
  id: string;
  language_id: string;
  language_code: string;
  title: string;
  description: string;
  is_published: boolean;
  created_at: string;
  unit_count: number;
  lesson_count: number;
};

export type CourseAdminDetail = {
  id: string;
  language_id: string;
  language_code: string;
  title: string;
  description: string;
  is_published: boolean;
  created_at: string;
  units: UnitSummary[];
};

export type ValidationResult = {
  valid: boolean;
  errors: string[];
};

export type Unit = {
  id: string;
  course_id: string;
  title: string;
  position: number;
};

export type Lesson = {
  id: string;
  unit_id: string;
  title: string;
  position: number;
};

export type Skill = {
  id: string;
  course_id: string;
  code: string;
  name: string;
};

export type ExerciseOption = {
  id: string;
  text: string;
  is_correct: boolean | null;
  correct_position: number | null;
  match_group: string | null;
  match_key: string | null;
};

export type ExerciseOptionInput = {
  text: string;
  is_correct?: boolean | null;
  correct_position?: number | null;
  match_group?: string | null;
  match_key?: string | null;
};

export type ExerciseAdmin = {
  id: string;
  lesson_id: string;
  skill_id: string;
  type: ExerciseType;
  position: number;
  prompt: string;
  payload: Record<string, unknown>;
  correct_answer: Record<string, unknown>;
  explanation: string | null;
  difficulty: number;
  options: ExerciseOption[];
};

export type LessonAdminDetail = {
  id: string;
  unit_id: string;
  course_id: string;
  title: string;
  position: number;
  exercises: ExerciseAdmin[];
};

export type DailyActiveUsersPoint = {
  day: string;
  count: number;
};

export type CompletionStats = {
  started: number;
  completed: number;
  completion_rate: number;
};

export type RetentionPoint = {
  cohort_size: number;
  retained: number;
  retention_rate: number;
};

export type AiCallOperation = "CHAT" | "TRANSCRIBE" | "SPEECH";

export type AiOperationStats = {
  operation: AiCallOperation;
  total_calls: number;
  failed_calls: number;
  error_rate: number;
  avg_latency_ms: number;
};

export type DetectedErrorType = "GRAMMAR" | "VOCABULARY" | "SPELLING" | "WORD_ORDER" | "OTHER";

export type MistakeTypeCount = {
  error_type: DetectedErrorType;
  count: number;
};

export type WeakestSkill = {
  skill_id: string;
  skill_name: string;
  avg_mastery: number;
  total_attempts: number;
};

export type WeeklyCorrectnessPoint = {
  week_start: string;
  correct: number;
  total: number;
  accuracy: number;
};

export type AnalyticsOverview = {
  daily_active_users: DailyActiveUsersPoint[];
  lesson_completion: CompletionStats;
  practice_completion: CompletionStats;
  day1_retention: RetentionPoint;
  day7_retention: RetentionPoint;
  ai_stats: AiOperationStats[];
  top_mistakes: MistakeTypeCount[];
  weakest_skills: WeakestSkill[];
  improvement_trend: WeeklyCorrectnessPoint[];
};
