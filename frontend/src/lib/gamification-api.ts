import { apiRequest } from "@/lib/api-client";
import type { LeaderboardEntry, LeagueLeaderboard, Quest } from "@/types/gamification";

export { ApiError } from "@/lib/api-client";

export function getQuests(accessToken: string): Promise<Quest[]> {
  return apiRequest("/me/quests", { accessToken });
}

export function getLeagueLeaderboard(accessToken: string): Promise<LeagueLeaderboard> {
  return apiRequest("/leaderboard", { accessToken });
}

export function getFriendsLeaderboard(accessToken: string): Promise<LeaderboardEntry[]> {
  return apiRequest("/leaderboard/friends", { accessToken });
}
