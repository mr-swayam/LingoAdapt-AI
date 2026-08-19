import { apiRequest } from "@/lib/api-client";
import type { ReviewItem, SkillMastery } from "@/types/mastery";

export { ApiError } from "@/lib/api-client";

export function getMastery(accessToken: string): Promise<SkillMastery[]> {
  return apiRequest("/me/mastery", { accessToken });
}

export function getReviewQueue(accessToken: string): Promise<ReviewItem[]> {
  return apiRequest("/me/review", { accessToken });
}
