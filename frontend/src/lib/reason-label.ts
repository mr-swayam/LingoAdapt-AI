import type { PracticeReason } from "@/types/practice";

/** Real "why was this recommended" reasoning, built entirely from
 * PracticeReason's fields (backend: recommendation.SkillCandidate,
 * previously computed then discarded before reaching the API - see
 * V2_PREMIUM_UI_AUDIT.md §8). Never a hardcoded or invented string. Shared
 * by the Practice page and the Dashboard's Daily Plan section (V3.2) -
 * both render the same PracticeReasonOut shape. */
export function reasonLabel(reason: PracticeReason): string {
  if (reason.is_review_due) return `${reason.skill_name} is due for review`;
  if (reason.recent_incorrect_count > 0) {
    return `You've missed ${reason.skill_name} ${reason.recent_incorrect_count} time${
      reason.recent_incorrect_count === 1 ? "" : "s"
    } recently`;
  }
  return `${reason.skill_name} is your weakest skill (${Math.round(reason.mastery)}% mastery)`;
}
