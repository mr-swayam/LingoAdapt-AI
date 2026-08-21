import { apiRequest } from "@/lib/api-client";
import type { MistakeList, MistakeSource, RepeatedMistakeGroup } from "@/types/mistakes";

export { ApiError } from "@/lib/api-client";

export function getMistakes(
  accessToken: string,
  params?: { limit?: number; offset?: number; skillId?: string; source?: MistakeSource },
): Promise<MistakeList> {
  const query = new URLSearchParams();
  if (params?.limit !== undefined) query.set("limit", String(params.limit));
  if (params?.offset !== undefined) query.set("offset", String(params.offset));
  if (params?.skillId) query.set("skill_id", params.skillId);
  if (params?.source) query.set("source", params.source);
  const qs = query.toString();
  return apiRequest(`/me/mistakes${qs ? `?${qs}` : ""}`, { accessToken });
}

export function getRepeatedMistakes(accessToken: string): Promise<RepeatedMistakeGroup[]> {
  return apiRequest("/me/mistakes/repeated", { accessToken });
}
