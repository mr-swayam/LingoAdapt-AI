import { apiRequest } from "@/lib/api-client";
import type { CoachResponse } from "@/types/coach";

export { ApiError } from "@/lib/api-client";

export function getCoachInsight(accessToken: string): Promise<CoachResponse> {
  return apiRequest("/me/coach", { accessToken });
}

/** Explicitly bypasses the cache - subject to its own 5-minute cooldown on
 * top of the shared AI budget (a 429 means "wait a bit", not a real error). */
export function refreshCoachInsight(accessToken: string): Promise<CoachResponse> {
  return apiRequest("/me/coach/refresh", { method: "POST", accessToken });
}
