export type CourseProgress = {
  course_id: string;
  course_title: string;
  completed_lessons: number;
  total_lessons: number;
  percent_complete: number;
};

export type Achievement = {
  code: string;
  name: string;
  description: string;
  earned: boolean;
  earned_at: string | null;
};

export type XPTransaction = {
  amount: number;
  reason: string;
  created_at: string;
};

export type Progress = {
  total_xp: number;
  xp_today: number;
  daily_goal_xp: number;
  current_streak: number;
  longest_streak: number;
  course_progress: CourseProgress[];
  achievements: Achievement[];
  recent_xp_transactions: XPTransaction[];
  gem_balance: number;
  league_tier: string;
};
