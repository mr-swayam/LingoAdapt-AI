export type SkillLevel = "strong" | "developing" | "weak";

export type SkillMastery = {
  skill_code: string;
  skill_name: string;
  mastery: number;
  confidence: number;
  level: SkillLevel;
  attempt_count: number;
  correct_count: number;
  last_practiced_at: string | null;
  next_review_at: string | null;
};

export type ReviewItem = {
  skill_code: string;
  skill_name: string;
  mastery: number;
  next_review_at: string;
};
