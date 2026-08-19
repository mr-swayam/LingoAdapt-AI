export type UserPreferences = {
  native_language: string;
  target_language: string;
  daily_goal_xp: number;
};

export type User = {
  id: string;
  email: string;
  created_at: string;
  is_admin: boolean;
  preferences: UserPreferences;
};

export type AuthTokenResponse = {
  access_token: string;
  token_type: string;
  user: User;
};
