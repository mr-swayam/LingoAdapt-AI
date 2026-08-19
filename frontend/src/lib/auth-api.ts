import { apiRequest } from "@/lib/api-client";
import type { AuthTokenResponse, UserPreferences } from "@/types/auth";

export { ApiError } from "@/lib/api-client";

export function signup(input: {
  email: string;
  password: string;
  native_language: string;
  target_language: string;
  daily_goal_xp: number;
}): Promise<AuthTokenResponse> {
  return apiRequest("/auth/signup", { method: "POST", body: JSON.stringify(input) });
}

export function login(input: { email: string; password: string }): Promise<AuthTokenResponse> {
  return apiRequest("/auth/login", { method: "POST", body: JSON.stringify(input) });
}

export function refresh(): Promise<AuthTokenResponse> {
  return apiRequest("/auth/refresh", { method: "POST" });
}

export function logout(): Promise<void> {
  return apiRequest("/auth/logout", { method: "POST" });
}

export function updatePreferences(
  accessToken: string,
  input: Partial<UserPreferences>,
): Promise<UserPreferences> {
  return apiRequest("/me/preferences", {
    method: "PATCH",
    accessToken,
    body: JSON.stringify(input),
  });
}
