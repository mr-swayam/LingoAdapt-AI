from fastapi import APIRouter

from app.api.v1 import (
    achievements,
    admin,
    auth,
    courses,
    exercises,
    friends,
    leaderboard,
    lessons,
    me,
    practice,
    tutor,
)

router = APIRouter(prefix="/api/v1")
router.include_router(auth.router)
router.include_router(me.router)
router.include_router(courses.router)
router.include_router(lessons.router)
router.include_router(exercises.router)
router.include_router(achievements.router)
router.include_router(practice.router)
router.include_router(tutor.router)
router.include_router(leaderboard.router)
router.include_router(friends.router)
router.include_router(admin.router)
