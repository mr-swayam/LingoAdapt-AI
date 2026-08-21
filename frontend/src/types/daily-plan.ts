import type { PracticeReason } from "@/types/practice";

export type TaskType = "REVIEW" | "PRACTICE" | "LESSON";

export type DailyPlanTask = {
  task_type: TaskType;
  skill_id: string | null;
  skill_name: string | null;
  lesson_id: string | null;
  lesson_title: string | null;
  /** Same real recommendation signals as PracticeReason - null only for
   * LESSON tasks, which have no skill-priority score behind them. */
  reason: PracticeReason | null;
  completed: boolean;
};

export type DailyPlan = {
  tasks: DailyPlanTask[];
  generated_for_date: string;
};
