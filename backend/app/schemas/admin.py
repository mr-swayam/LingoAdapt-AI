import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.models.course import (
    Course,
    Exercise,
    ExerciseType,
    Lesson,
    Unit,
)


class LanguageIn(BaseModel):
    code: str = Field(min_length=2, max_length=10)
    name: str = Field(min_length=1, max_length=100)


class LanguageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    code: str
    name: str


class CourseCreateIn(BaseModel):
    language_id: uuid.UUID
    title: str = Field(min_length=1, max_length=200)
    description: str = ""


class CourseUpdateIn(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = None


class LessonSummaryOut(BaseModel):
    id: uuid.UUID
    title: str
    position: int
    exercise_count: int

    @classmethod
    def from_model(cls, lesson: Lesson) -> "LessonSummaryOut":
        return cls(
            id=lesson.id,
            title=lesson.title,
            position=lesson.position,
            exercise_count=len(lesson.exercises),
        )


class UnitSummaryOut(BaseModel):
    id: uuid.UUID
    title: str
    position: int
    lessons: list[LessonSummaryOut]

    @classmethod
    def from_model(cls, unit: Unit) -> "UnitSummaryOut":
        return cls(
            id=unit.id,
            title=unit.title,
            position=unit.position,
            lessons=[LessonSummaryOut.from_model(lesson) for lesson in unit.lessons],
        )


class CourseAdminOut(BaseModel):
    id: uuid.UUID
    language_id: uuid.UUID
    language_code: str
    title: str
    description: str
    is_published: bool
    created_at: datetime
    unit_count: int
    lesson_count: int

    @classmethod
    def from_model(cls, course: Course) -> "CourseAdminOut":
        return cls(
            id=course.id,
            language_id=course.language_id,
            language_code=course.language.code,
            title=course.title,
            description=course.description,
            is_published=course.is_published,
            created_at=course.created_at,
            unit_count=len(course.units),
            lesson_count=sum(len(u.lessons) for u in course.units),
        )


class CourseAdminDetailOut(BaseModel):
    id: uuid.UUID
    language_id: uuid.UUID
    language_code: str
    title: str
    description: str
    is_published: bool
    created_at: datetime
    units: list[UnitSummaryOut]

    @classmethod
    def from_model(cls, course: Course) -> "CourseAdminDetailOut":
        return cls(
            id=course.id,
            language_id=course.language_id,
            language_code=course.language.code,
            title=course.title,
            description=course.description,
            is_published=course.is_published,
            created_at=course.created_at,
            units=[UnitSummaryOut.from_model(u) for u in course.units],
        )


class ValidationResultOut(BaseModel):
    valid: bool
    errors: list[str]


class UnitCreateIn(BaseModel):
    course_id: uuid.UUID
    title: str = Field(min_length=1, max_length=200)
    position: int | None = None


class UnitUpdateIn(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    position: int | None = None


class UnitOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    course_id: uuid.UUID
    title: str
    position: int


class LessonCreateIn(BaseModel):
    unit_id: uuid.UUID
    title: str = Field(min_length=1, max_length=200)
    position: int | None = None


class LessonUpdateIn(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    position: int | None = None


class LessonOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    unit_id: uuid.UUID
    title: str
    position: int


class SkillCreateIn(BaseModel):
    course_id: uuid.UUID
    code: str = Field(min_length=1, max_length=50)
    name: str = Field(min_length=1, max_length=100)


class SkillUpdateIn(BaseModel):
    name: str = Field(min_length=1, max_length=100)


class SkillOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    course_id: uuid.UUID
    code: str
    name: str


class ExerciseOptionIn(BaseModel):
    text: str = Field(min_length=1, max_length=300)
    is_correct: bool | None = None
    correct_position: int | None = None
    match_group: str | None = None
    match_key: str | None = None


class ExerciseOptionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    text: str
    is_correct: bool | None
    correct_position: int | None
    match_group: str | None
    match_key: str | None


class ExerciseCreateIn(BaseModel):
    lesson_id: uuid.UUID
    skill_id: uuid.UUID
    type: ExerciseType
    prompt: str = Field(min_length=1)
    payload: dict[str, Any] = Field(default_factory=dict)
    correct_answer: dict[str, Any] = Field(default_factory=dict)
    explanation: str | None = None
    difficulty: float = Field(default=0.5, ge=0.0, le=1.0)
    position: int | None = None
    options: list[ExerciseOptionIn] = Field(default_factory=list)


class ExerciseUpdateIn(BaseModel):
    skill_id: uuid.UUID | None = None
    prompt: str | None = Field(default=None, min_length=1)
    payload: dict[str, Any] | None = None
    correct_answer: dict[str, Any] | None = None
    explanation: str | None = None
    explanation_set: bool = False
    difficulty: float | None = Field(default=None, ge=0.0, le=1.0)
    position: int | None = None
    options: list[ExerciseOptionIn] | None = None


class ExerciseAdminOut(BaseModel):
    id: uuid.UUID
    lesson_id: uuid.UUID
    skill_id: uuid.UUID
    type: ExerciseType
    position: int
    prompt: str
    payload: dict[str, Any]
    correct_answer: dict[str, Any]
    explanation: str | None
    difficulty: float
    options: list[ExerciseOptionOut]

    @classmethod
    def from_model(cls, exercise: Exercise) -> "ExerciseAdminOut":
        return cls(
            id=exercise.id,
            lesson_id=exercise.lesson_id,
            skill_id=exercise.skill_id,
            type=exercise.type,
            position=exercise.position,
            prompt=exercise.prompt,
            payload=exercise.payload,
            correct_answer=exercise.correct_answer,
            explanation=exercise.explanation,
            difficulty=exercise.difficulty,
            options=[ExerciseOptionOut.model_validate(o) for o in exercise.options],
        )


class LessonAdminDetailOut(BaseModel):
    id: uuid.UUID
    unit_id: uuid.UUID
    course_id: uuid.UUID
    title: str
    position: int
    exercises: list[ExerciseAdminOut]

    @classmethod
    def from_model(cls, lesson: Lesson) -> "LessonAdminDetailOut":
        return cls(
            id=lesson.id,
            unit_id=lesson.unit_id,
            course_id=lesson.unit.course_id,
            title=lesson.title,
            position=lesson.position,
            exercises=[ExerciseAdminOut.from_model(e) for e in lesson.exercises],
        )
