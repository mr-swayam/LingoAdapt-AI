import uuid
from datetime import date, datetime

from pydantic import BaseModel


class CourseProgressOut(BaseModel):
    course_id: uuid.UUID
    course_title: str
    completed_lessons: int
    total_lessons: int
    percent_complete: float


class AchievementOut(BaseModel):
    code: str
    name: str
    description: str
    earned: bool
    earned_at: datetime | None


class XPTransactionOut(BaseModel):
    amount: int
    reason: str
    created_at: datetime


class ProgressOut(BaseModel):
    total_xp: int
    xp_today: int
    daily_goal_xp: int
    current_streak: int
    longest_streak: int
    course_progress: list[CourseProgressOut]
    achievements: list[AchievementOut]
    recent_xp_transactions: list[XPTransactionOut]
    gem_balance: int
    league_tier: str


class LeaderboardEntryOut(BaseModel):
    email: str
    weekly_xp: int
    rank: int
    is_me: bool


class LeagueLeaderboardOut(BaseModel):
    tier: str
    week_start: date
    entries: list[LeaderboardEntryOut]


class QuestOut(BaseModel):
    id: uuid.UUID
    quest_type: str
    name: str
    description: str
    target: int
    progress: int
    reward_gems: int
    completed: bool
