export type CoachInsight = {
  summary: string;
  strengths: string[];
  focus_areas: string[];
  recommended_action: string;
  data_note: string | null;
  from_cache: boolean;
};

/** GET /me/coach's actual response shape - always parse this one shape and
 * branch on has_sufficient_data, rather than expecting two different
 * response bodies. */
export type CoachResponse = {
  has_sufficient_data: boolean;
  message: string | null;
  insight: CoachInsight | null;
};
