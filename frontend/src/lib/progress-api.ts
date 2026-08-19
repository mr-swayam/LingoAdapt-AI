import { apiRequest } from "@/lib/api-client";
import type { Achievement, Progress } from "@/types/progress";

export { ApiError } from "@/lib/api-client";

export function getProgress(accessToken: string): Promise<Progress> {
  return apiRequest("/me/progress", { accessToken });
}

export function listAchievements(accessToken: string): Promise<Achievement[]> {
  return apiRequest("/achievements", { accessToken });
}
