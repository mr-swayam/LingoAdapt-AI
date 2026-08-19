import { apiRequest } from "@/lib/api-client";
import type { Friend, Friendship, PendingRequests } from "@/types/gamification";

export { ApiError } from "@/lib/api-client";

export function listFriends(accessToken: string): Promise<Friend[]> {
  return apiRequest("/friends", { accessToken });
}

export function listPendingRequests(accessToken: string): Promise<PendingRequests> {
  return apiRequest("/friends/requests", { accessToken });
}

export function sendFriendRequest(email: string, accessToken: string): Promise<Friendship> {
  return apiRequest("/friends/requests", {
    method: "POST",
    accessToken,
    body: JSON.stringify({ email }),
  });
}

export function acceptFriendRequest(
  friendshipId: string,
  accessToken: string,
): Promise<Friendship> {
  return apiRequest(`/friends/requests/${friendshipId}/accept`, {
    method: "POST",
    accessToken,
  });
}

export function removeFriend(friendshipId: string, accessToken: string): Promise<void> {
  return apiRequest(`/friends/${friendshipId}`, { method: "DELETE", accessToken });
}
