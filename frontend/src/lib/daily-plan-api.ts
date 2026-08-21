import { apiRequest } from "@/lib/api-client";
import type { DailyPlan } from "@/types/daily-plan";

export { ApiError } from "@/lib/api-client";

/** The learner's actual browser-local calendar date (YYYY-MM-DD), computed
 * from local getters (not UTC ones) - this is the client-side half of the
 * local-day completion boundary (backend/app/services/daily_plan_service.py).
 * No timezone is ever sent or stored - just this one calendar-date string. */
export function todayLocalDate(): string {
  const now = new Date();
  const year = now.getFullYear();
  const month = String(now.getMonth() + 1).padStart(2, "0");
  const day = String(now.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

export function getDailyPlan(accessToken: string): Promise<DailyPlan> {
  const query = new URLSearchParams({ local_date: todayLocalDate() });
  return apiRequest(`/me/daily-plan?${query.toString()}`, { accessToken });
}
