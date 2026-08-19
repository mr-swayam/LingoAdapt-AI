"""Pure unit tests against transient (never-persisted) model instances -
content_validation only reads attributes, so no DB session is needed."""

from app.models.course import Course, Exercise, ExerciseOption, ExerciseType, Lesson, Unit
from app.services.content_validation import validate_course_for_publish, validate_exercise


def _exercise(type: ExerciseType, **kwargs) -> Exercise:
    defaults = {
        "prompt": "Do the thing",
        "payload": {},
        "correct_answer": {},
        "difficulty": 0.5,
        "position": 1,
    }
    defaults.update(kwargs)
    options = defaults.pop("options", [])
    ex = Exercise(type=type, **defaults)
    ex.options = options
    return ex


def test_multiple_choice_needs_two_options_and_one_correct() -> None:
    errors = validate_exercise(_exercise(ExerciseType.MULTIPLE_CHOICE, options=[]))
    assert any("at least 2 options" in e for e in errors)

    errors = validate_exercise(
        _exercise(
            ExerciseType.MULTIPLE_CHOICE,
            options=[
                ExerciseOption(text="a", is_correct=True, position=1),
                ExerciseOption(text="b", is_correct=True, position=2),
            ],
        )
    )
    assert any("exactly one option" in e for e in errors)


def test_multiple_choice_valid() -> None:
    errors = validate_exercise(
        _exercise(
            ExerciseType.MULTIPLE_CHOICE,
            options=[
                ExerciseOption(text="a", is_correct=True, position=1),
                ExerciseOption(text="b", is_correct=False, position=2),
            ],
        )
    )
    assert errors == []


def test_fill_blank_needs_answers() -> None:
    errors = validate_exercise(_exercise(ExerciseType.FILL_BLANK, correct_answer={}))
    assert any("answers" in e for e in errors)

    errors = validate_exercise(
        _exercise(ExerciseType.FILL_BLANK, correct_answer={"answers": ["hello"]})
    )
    assert errors == []


def test_translation_needs_source_text() -> None:
    errors = validate_exercise(
        _exercise(
            ExerciseType.TRANSLATION, correct_answer={"answers": ["hello"]}, payload={}
        )
    )
    assert any("source_text" in e for e in errors)


def test_word_order_needs_full_position_sequence() -> None:
    errors = validate_exercise(
        _exercise(
            ExerciseType.WORD_ORDER,
            options=[
                ExerciseOption(text="a", correct_position=0, position=1),
                ExerciseOption(text="b", correct_position=0, position=2),  # duplicate
            ],
        )
    )
    assert any("0..n-1 sequence" in e for e in errors)

    errors = validate_exercise(
        _exercise(
            ExerciseType.WORD_ORDER,
            options=[
                ExerciseOption(text="a", correct_position=0, position=1),
                ExerciseOption(text="b", correct_position=1, position=2),
            ],
        )
    )
    assert errors == []


def test_matching_needs_paired_left_right() -> None:
    errors = validate_exercise(
        _exercise(
            ExerciseType.MATCHING,
            options=[
                ExerciseOption(text="a", match_group="left", match_key="0", position=1),
                ExerciseOption(text="b", match_group="right", match_key="1", position=2),
            ],
        )
    )
    assert any("pair up 1:1" in e for e in errors)

    errors = validate_exercise(
        _exercise(
            ExerciseType.MATCHING,
            options=[
                ExerciseOption(text="a", match_group="left", match_key="0", position=1),
                ExerciseOption(text="b", match_group="right", match_key="0", position=2),
            ],
        )
    )
    assert errors == []


def test_short_answer_needs_model_answer_and_rubric() -> None:
    errors = validate_exercise(_exercise(ExerciseType.SHORT_ANSWER))
    assert any("model_answer" in e for e in errors)
    assert any("rubric" in e for e in errors)

    errors = validate_exercise(
        _exercise(
            ExerciseType.SHORT_ANSWER,
            correct_answer={"model_answer": "Hi, I'm Sam.", "rubric": "Has a name."},
        )
    )
    assert errors == []


def test_speaking_needs_phrase_to_say_and_answers() -> None:
    errors = validate_exercise(_exercise(ExerciseType.SPEAKING))
    assert any("phrase_to_say" in e for e in errors)
    assert any("answers" in e for e in errors)

    errors = validate_exercise(
        _exercise(
            ExerciseType.SPEAKING,
            payload={"phrase_to_say": "Hello"},
            correct_answer={"answers": ["Hello"]},
        )
    )
    assert errors == []


def test_listening_needs_text_to_speak_and_answers() -> None:
    errors = validate_exercise(_exercise(ExerciseType.LISTENING))
    assert any("text_to_speak" in e for e in errors)

    errors = validate_exercise(
        _exercise(
            ExerciseType.LISTENING,
            correct_answer={"text_to_speak": "Hello", "answers": ["Hello"]},
        )
    )
    assert errors == []


def test_difficulty_must_be_bounded() -> None:
    errors = validate_exercise(
        _exercise(
            ExerciseType.FILL_BLANK, correct_answer={"answers": ["x"]}, difficulty=1.5
        )
    )
    assert any("difficulty" in e for e in errors)


def test_empty_prompt_is_invalid() -> None:
    errors = validate_exercise(
        _exercise(ExerciseType.FILL_BLANK, prompt="  ", correct_answer={"answers": ["x"]})
    )
    assert any("prompt" in e for e in errors)


def _valid_fill_blank(position: int = 1) -> Exercise:
    return _exercise(
        ExerciseType.FILL_BLANK, correct_answer={"answers": ["x"]}, position=position
    )


def test_course_with_no_units_is_invalid() -> None:
    course = Course(title="Empty", description="")
    course.units = []
    errors = validate_course_for_publish(course)
    assert any("no units" in e for e in errors)


def test_unit_with_no_lessons_is_invalid() -> None:
    course = Course(title="C", description="")
    unit = Unit(title="Unit 1", position=1)
    unit.lessons = []
    course.units = [unit]
    errors = validate_course_for_publish(course)
    assert any("no lessons" in e for e in errors)


def test_lesson_with_no_exercises_is_invalid() -> None:
    course = Course(title="C", description="")
    unit = Unit(title="Unit 1", position=1)
    lesson = Lesson(title="Lesson 1", position=1)
    lesson.exercises = []
    unit.lessons = [lesson]
    course.units = [unit]
    errors = validate_course_for_publish(course)
    assert any("no exercises" in e for e in errors)


def test_fully_valid_course_has_no_errors() -> None:
    course = Course(title="C", description="")
    unit = Unit(title="Unit 1", position=1)
    lesson = Lesson(title="Lesson 1", position=1)
    lesson.exercises = [_valid_fill_blank()]
    unit.lessons = [lesson]
    course.units = [unit]
    errors = validate_course_for_publish(course)
    assert errors == []


def test_invalid_exercise_error_mentions_lesson_and_position() -> None:
    course = Course(title="C", description="")
    unit = Unit(title="Unit 1", position=1)
    lesson = Lesson(title="Greetings", position=1)
    bad_exercise = _exercise(ExerciseType.FILL_BLANK, correct_answer={}, position=3)
    lesson.exercises = [bad_exercise]
    unit.lessons = [lesson]
    course.units = [unit]
    errors = validate_course_for_publish(course)
    assert any("Greetings" in e and "exercise 3" in e for e in errors)
