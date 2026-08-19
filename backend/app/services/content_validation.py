"""Deterministic content validation (rules.md §7: "Generated exercises must
be validated before publication"). Applies to admin-authored content the
same way it would to AI-generated content - the rule is about what gets
published, not who wrote it. No AI involved: every check here is a
structural fact about whether an exercise/course is gradeable at all,
derived from what app/services/grading.py actually reads at answer time.
"""

from app.models.course import Course, Exercise, ExerciseType


def _require_answers_list(correct_answer: dict) -> list[str]:
    answers = correct_answer.get("answers")
    if not isinstance(answers, list) or not answers:
        return ["correct_answer.answers must be a non-empty list of accepted answers"]
    if not all(isinstance(a, str) and a.strip() for a in answers):
        return ["correct_answer.answers must contain only non-empty strings"]
    return []


def validate_exercise(exercise: Exercise) -> list[str]:
    errors: list[str] = []
    if not exercise.prompt.strip():
        errors.append("prompt must not be empty")

    match exercise.type:
        case ExerciseType.MULTIPLE_CHOICE:
            if len(exercise.options) < 2:
                errors.append("MULTIPLE_CHOICE needs at least 2 options")
            correct = [o for o in exercise.options if o.is_correct]
            if len(correct) != 1:
                errors.append("MULTIPLE_CHOICE needs exactly one option marked is_correct")

        case ExerciseType.FILL_BLANK:
            errors += _require_answers_list(exercise.correct_answer)

        case ExerciseType.TRANSLATION:
            errors += _require_answers_list(exercise.correct_answer)
            if not exercise.payload.get("source_text"):
                errors.append("TRANSLATION payload.source_text is required")

        case ExerciseType.WORD_ORDER:
            if len(exercise.options) < 2:
                errors.append("WORD_ORDER needs at least 2 options")
            positions = sorted(
                o.correct_position for o in exercise.options if o.correct_position is not None
            )
            if len(positions) != len(exercise.options):
                errors.append("WORD_ORDER options must all have correct_position set")
            elif positions != list(range(len(exercise.options))):
                errors.append(
                    "WORD_ORDER correct_position values must form a 0..n-1 sequence"
                )

        case ExerciseType.MATCHING:
            left = [o for o in exercise.options if o.match_group == "left"]
            right = [o for o in exercise.options if o.match_group == "right"]
            if not left or len(left) != len(right):
                errors.append("MATCHING needs an equal, non-zero number of left/right options")
            elif {o.match_key for o in left} != {o.match_key for o in right} or any(
                o.match_key is None for o in left + right
            ):
                errors.append("MATCHING left/right options must pair up 1:1 by match_key")

        case ExerciseType.SHORT_ANSWER:
            model_answer = exercise.correct_answer.get("model_answer")
            rubric = exercise.correct_answer.get("rubric")
            if not (isinstance(model_answer, str) and model_answer.strip()):
                errors.append("SHORT_ANSWER correct_answer.model_answer is required")
            if not (isinstance(rubric, str) and rubric.strip()):
                errors.append("SHORT_ANSWER correct_answer.rubric is required")

        case ExerciseType.SPEAKING:
            errors += _require_answers_list(exercise.correct_answer)
            if not exercise.payload.get("phrase_to_say"):
                errors.append("SPEAKING payload.phrase_to_say is required")

        case ExerciseType.LISTENING:
            errors += _require_answers_list(exercise.correct_answer)
            text_to_speak = exercise.correct_answer.get("text_to_speak")
            if not (isinstance(text_to_speak, str) and text_to_speak.strip()):
                errors.append("LISTENING correct_answer.text_to_speak is required")

    if not 0.0 <= exercise.difficulty <= 1.0:
        errors.append("difficulty must be between 0 and 1")

    return errors


def validate_course_for_publish(course: Course) -> list[str]:
    """Structural readiness for the whole content tree, not just individual
    exercises - a course with no units, or a lesson with no exercises, is
    just as unpublishable as an exercise with a malformed answer key."""
    errors: list[str] = []
    if not course.units:
        errors.append("Course has no units")

    for unit in course.units:
        if not unit.lessons:
            errors.append(f'Unit "{unit.title}" has no lessons')
        for lesson in unit.lessons:
            if not lesson.exercises:
                errors.append(f'Lesson "{lesson.title}" has no exercises')
            for exercise in lesson.exercises:
                for error in validate_exercise(exercise):
                    errors.append(f'Lesson "{lesson.title}", exercise {exercise.position}: {error}')

    return errors
