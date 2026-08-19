export type Quest = {
  id: string;
  quest_type: "EARN_XP" | "COMPLETE_LESSON" | "PRACTICE_SESSION";
  name: string;
  description: string;
  target: number;
  progress: number;
  reward_gems: number;
  completed: boolean;
};

export type LeaderboardEntry = {
  email: string;
  weekly_xp: number;
  rank: number;
  is_me: boolean;
};

export type LeagueLeaderboard = {
  tier: string;
  week_start: string;
  entries: LeaderboardEntry[];
};

export type Friend = {
  id: string;
  email: string;
};

export type PendingRequest = {
  friendship_id: string;
  other_user_email: string;
  created_at: string;
};

export type PendingRequests = {
  incoming: PendingRequest[];
  outgoing: PendingRequest[];
};

export type Friendship = {
  id: string;
  status: "PENDING" | "ACCEPTED";
};
