"""Seeds a small, realistic demo course: English Foundations.

Idempotent - safe to run multiple times; does nothing if the course already
exists. Run with: python -m app.seed
"""

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.db import SessionLocal
from app.models.course import (
    Course,
    Exercise,
    ExerciseOption,
    ExerciseType,
    Language,
    Lesson,
    Skill,
    Unit,
)
from app.models.gamification import Achievement
from app.services.gamification_service import ACHIEVEMENT_CATALOG

COURSE_TITLE = "English Foundations"


def _mc(prompt: str, choices: list[tuple[str, bool]], explanation: str) -> dict:
    return {
        "type": ExerciseType.MULTIPLE_CHOICE,
        "prompt": prompt,
        "payload": {},
        "correct_answer": {},
        "explanation": explanation,
        "options": [{"text": text, "is_correct": correct} for text, correct in choices],
    }


def _fill_blank(prompt: str, sentence: str, answers: list[str], explanation: str) -> dict:
    return {
        "type": ExerciseType.FILL_BLANK,
        "prompt": prompt,
        "payload": {"sentence": sentence},
        "correct_answer": {"answers": answers},
        "explanation": explanation,
        "options": [],
    }


def _translation(
    prompt: str, source_text: str, source_language: str, answers: list[str], explanation: str
) -> dict:
    return {
        "type": ExerciseType.TRANSLATION,
        "prompt": prompt,
        "payload": {"source_text": source_text, "source_language": source_language},
        "correct_answer": {"answers": answers},
        "explanation": explanation,
        "options": [],
    }


def _word_order(prompt: str, correct_order: list[str], explanation: str) -> dict:
    return {
        "type": ExerciseType.WORD_ORDER,
        "prompt": prompt,
        "payload": {},
        "correct_answer": {},
        "explanation": explanation,
        "options": [{"text": token} for token in correct_order],
    }


def _matching(prompt: str, pairs: list[tuple[str, str]], explanation: str) -> dict:
    options = []
    for i, (left, right) in enumerate(pairs):
        key = str(i)
        options.append({"text": left, "match_group": "left", "match_key": key})
        options.append({"text": right, "match_group": "right", "match_key": key})
    return {
        "type": ExerciseType.MATCHING,
        "prompt": prompt,
        "payload": {},
        "correct_answer": {},
        "explanation": explanation,
        "options": options,
    }


UNITS: list[dict] = [
    {
        "title": "Greetings",
        "lessons": [
            {
                "title": "Saying Hello",
                "skill": ("GREETINGS", "Greetings"),
                "exercises": [
                    _mc(
                        "Which word is a friendly greeting?",
                        [("Hello", True), ("Goodbye", False), ("Sorry", False), ("Please", False)],
                        '"Hello" is used to greet someone when you meet them.',
                    ),
                    _fill_blank(
                        "Complete the greeting.",
                        "___, how are you?",
                        ["Hello", "Hi"],
                        'Both "Hello" and "Hi" are common greetings.',
                    ),
                    _translation(
                        "Translate to English.",
                        "Hola",
                        "Spanish",
                        ["Hello", "Hi"],
                        '"Hola" means "Hello" in Spanish.',
                    ),
                    _word_order(
                        "Put the words in order.",
                        ["Good", "morning"],
                        '"Good morning" is a common greeting used earlier in the day.',
                    ),
                ],
            },
            {
                "title": "Saying Goodbye",
                "skill": ("FAREWELLS", "Farewells"),
                "exercises": [
                    _mc(
                        "Which word means you are leaving?",
                        [("Goodbye", True), ("Hello", False), ("Please", False), ("Thanks", False)],
                        '"Goodbye" is said when you leave or end a conversation.',
                    ),
                    _fill_blank(
                        "Complete the farewell.",
                        "See you ___!",
                        ["later", "soon"],
                        '"See you later" and "See you soon" are casual ways to say goodbye.',
                    ),
                    _matching(
                        "Match the English farewell to its Spanish equivalent.",
                        [
                            ("Goodbye", "Adiós"),
                            ("See you later", "Hasta luego"),
                            ("Good night", "Buenas noches"),
                        ],
                        "These are the direct Spanish equivalents of each farewell.",
                    ),
                ],
            },
        ],
    },
    {
        "title": "Introductions",
        "lessons": [
            {
                "title": "Introducing Yourself",
                "skill": ("INTRODUCTIONS", "Introductions"),
                "exercises": [
                    _mc(
                        "How do you introduce yourself?",
                        [
                            ("My name is Anna.", True),
                            ("How much is it?", False),
                            ("What time is it?", False),
                            ("Where is the bathroom?", False),
                        ],
                        '"My name is..." is the standard way to introduce yourself.',
                    ),
                    _fill_blank(
                        "Complete the sentence.",
                        "My ___ is Anna.",
                        ["name"],
                        'Use "name" to say what you are called.',
                    ),
                    _translation(
                        "Translate to English.",
                        "Me llamo Anna.",
                        "Spanish",
                        ["My name is Anna.", "I am Anna."],
                        'Literally "I call myself Anna" - in English this becomes '
                        '"My name is Anna."',
                    ),
                ],
            },
            {
                "title": "Asking Someone's Name",
                "skill": ("PERSONAL_INFO", "Personal Information"),
                "exercises": [
                    _word_order(
                        "Put the words in order to ask someone's name.",
                        ["What", "is", "your", "name"],
                        'Questions with "what" start with the question word.',
                    ),
                    _matching(
                        "Match the question to the correct answer.",
                        [
                            ("What is your name?", "My name is Tom."),
                            ("Where are you from?", "I am from Spain."),
                            ("How old are you?", "I am 25 years old."),
                        ],
                        "Each question has one natural, matching answer.",
                    ),
                    _mc(
                        "Which question asks for someone's age?",
                        [
                            ("How old are you?", True),
                            ("What is your name?", False),
                            ("Where do you live?", False),
                            ("What do you do?", False),
                        ],
                        '"How old are you?" specifically asks for age.',
                    ),
                ],
            },
        ],
    },
    {
        "title": "Daily Life",
        "lessons": [
            {
                "title": "Daily Routines",
                "skill": ("DAILY_ROUTINES", "Daily Routines"),
                "exercises": [
                    _mc(
                        "What do you usually do in the morning?",
                        [
                            ("I wake up.", True),
                            ("I go to sleep.", False),
                            ("I eat dinner.", False),
                            ("I watch the sunset.", False),
                        ],
                        "Waking up is the first thing most people do in the morning.",
                    ),
                    _fill_blank(
                        "Complete the sentence.",
                        "I usually ___ up at 7 a.m.",
                        ["wake"],
                        '"Wake up" describes the moment you stop sleeping.',
                    ),
                    _translation(
                        "Translate to English.",
                        "Me despierto a las siete.",
                        "Spanish",
                        ["I wake up at seven.", "I wake up at 7."],
                        '"Despertarse" means "to wake up."',
                    ),
                ],
            },
            {
                "title": "Talking About Time",
                "skill": ("TIME_EXPRESSIONS", "Time Expressions"),
                "exercises": [
                    _word_order(
                        "Put the words in order to ask for the time.",
                        ["What", "time", "is", "it"],
                        'This is the standard question to ask for the current time.',
                    ),
                    _fill_blank(
                        "Complete the sentence.",
                        "It is nine o'___.",
                        ["clock"],
                        '"O\'clock" is used for exact hours, e.g. "nine o\'clock."',
                    ),
                    _matching(
                        "Match the English day to its Spanish equivalent.",
                        [
                            ("Monday", "Lunes"),
                            ("Tuesday", "Martes"),
                            ("Sunday", "Domingo"),
                        ],
                        "These are the direct Spanish equivalents of each day.",
                    ),
                ],
            },
        ],
    },
    {
        "title": "Food",
        "lessons": [
            {
                "title": "Ordering Food",
                "skill": ("FOOD_VOCABULARY", "Food Vocabulary"),
                "exercises": [
                    _mc(
                        "How do you politely order food?",
                        [
                            ("I would like a coffee, please.", True),
                            ("Give me coffee now.", False),
                            ("Coffee.", False),
                            ("I hate coffee.", False),
                        ],
                        '"I would like..., please" is a polite way to order.',
                    ),
                    _fill_blank(
                        "Complete the sentence.",
                        "I would like a glass of ___, please.",
                        ["water"],
                        '"Water" is a common thing to order at a restaurant.',
                    ),
                    _translation(
                        "Translate to English.",
                        "Quiero un café, por favor.",
                        "Spanish",
                        ["I want a coffee, please.", "I would like a coffee, please."],
                        '"Quiero" means "I want," often softened to "I would like" in English.',
                    ),
                ],
            },
            {
                "title": "At the Restaurant",
                "skill": ("RESTAURANT_PHRASES", "Restaurant Phrases"),
                "exercises": [
                    _word_order(
                        "Put the words in order to politely ask for the bill.",
                        ["Can", "I", "have", "the", "bill", "please"],
                        'This is a complete, polite request for the bill.',
                    ),
                    _matching(
                        "Match the phrase to its meaning.",
                        [
                            ("The bill, please", "asking to pay"),
                            ("A table for two", "asking for seating"),
                            ("Is this seat taken?", "asking about availability"),
                        ],
                        "Each restaurant phrase serves a specific, common purpose.",
                    ),
                    _mc(
                        "What do you say when you finish your meal and want to pay?",
                        [
                            ("Can I have the bill, please?", True),
                            ("What time is it?", False),
                            ("Where is the airport?", False),
                            ("I am not hungry.", False),
                        ],
                        'Asking for "the bill" is how you request the check.',
                    ),
                ],
            },
        ],
    },
    {
        "title": "Travel",
        "lessons": [
            {
                "title": "At the Airport",
                "skill": ("TRAVEL_VOCABULARY", "Travel Vocabulary"),
                "exercises": [
                    _mc(
                        "Where do you check in for a flight?",
                        [
                            ("At the airport.", True),
                            ("At the restaurant.", False),
                            ("At the school.", False),
                            ("At the park.", False),
                        ],
                        "Flight check-in happens at the airport.",
                    ),
                    _fill_blank(
                        "Complete the sentence.",
                        "My ___ leaves at 6 p.m.",
                        ["flight"],
                        '"Flight" refers to the airplane journey you are taking.',
                    ),
                    _translation(
                        "Translate to English.",
                        "¿Dónde está la puerta de embarque?",
                        "Spanish",
                        ["Where is the boarding gate?", "Where's the boarding gate?"],
                        '"Puerta de embarque" means "boarding gate."',
                    ),
                ],
            },
            {
                "title": "Asking for Directions",
                "skill": ("DIRECTIONS", "Directions"),
                "exercises": [
                    _word_order(
                        "Put the words in order to ask for the train station.",
                        ["Where", "is", "the", "train", "station"],
                        'Questions with "where" ask about a location.',
                    ),
                    _matching(
                        "Match the English direction word to its Spanish equivalent.",
                        [
                            ("Left", "Izquierda"),
                            ("Right", "Derecha"),
                            ("Straight ahead", "Todo recto"),
                        ],
                        "These are the direct Spanish equivalents of each direction.",
                    ),
                    _mc(
                        "How do you ask for directions politely?",
                        [
                            ("Excuse me, where is the train station?", True),
                            ("Train station now.", False),
                            ("I don't care.", False),
                            ("Go away.", False),
                        ],
                        '"Excuse me" politely gets someone\'s attention before asking a question.',
                    ),
                ],
            },
        ],
    },
]


def seed_english_foundations(db: Session) -> Course | None:
    """Creates the English Foundations course if it doesn't already exist.

    Returns the course (newly created, or None if it already existed).
    """
    existing = db.query(Course).filter(Course.title == COURSE_TITLE).first()
    if existing is not None:
        return None

    language = db.query(Language).filter(Language.code == "en").first()
    if language is None:
        language = Language(code="en", name="English")
        db.add(language)
        db.flush()

    course = Course(
        language_id=language.id,
        title=COURSE_TITLE,
        description=(
            "Learn everyday English: greetings, introductions, daily life, food, and travel."
        ),
        is_published=True,
    )
    db.add(course)
    db.flush()

    skills: dict[str, Skill] = {}

    for unit_position, unit_data in enumerate(UNITS, start=1):
        unit = Unit(course_id=course.id, title=unit_data["title"], position=unit_position)
        db.add(unit)
        db.flush()

        for lesson_position, lesson_data in enumerate(unit_data["lessons"], start=1):
            lesson = Lesson(
                unit_id=unit.id, title=lesson_data["title"], position=lesson_position
            )
            db.add(lesson)
            db.flush()

            skill_code, skill_name = lesson_data["skill"]
            skill = skills.get(skill_code)
            if skill is None:
                skill = Skill(course_id=course.id, code=skill_code, name=skill_name)
                db.add(skill)
                db.flush()
                skills[skill_code] = skill

            # Difficulty rises gradually with unit position (0.2 for Greetings
            # up to 0.6 for Travel) - a static content rating, not adaptive
            # selection (that's Phase 5).
            unit_difficulty = 0.2 + (unit_position - 1) * 0.1

            for exercise_position, exercise_data in enumerate(lesson_data["exercises"], start=1):
                exercise = Exercise(
                    lesson_id=lesson.id,
                    skill_id=skill.id,
                    type=exercise_data["type"],
                    position=exercise_position,
                    prompt=exercise_data["prompt"],
                    payload=exercise_data["payload"],
                    correct_answer=exercise_data["correct_answer"],
                    explanation=exercise_data["explanation"],
                    difficulty=unit_difficulty,
                )
                db.add(exercise)
                db.flush()

                for option_position, option_data in enumerate(exercise_data["options"], start=1):
                    db.add(
                        ExerciseOption(
                            exercise_id=exercise.id,
                            position=option_position,
                            text=option_data["text"],
                            is_correct=option_data.get("is_correct"),
                            match_group=option_data.get("match_group"),
                            match_key=option_data.get("match_key"),
                            correct_position=(
                                option_position - 1
                                if exercise_data["type"] == ExerciseType.WORD_ORDER
                                else None
                            ),
                        )
                    )

    db.commit()
    return course


GRAMMAR_SKILLS: list[tuple[str, str]] = [
    ("PAST_TENSE", "Past Tense"),
    ("PREPOSITIONS", "Prepositions"),
    ("ARTICLES", "Articles"),
    ("SUBJECT_VERB_AGREEMENT", "Subject-Verb Agreement"),
    ("PLURALS", "Plurals"),
    ("WORD_CHOICE", "Word Choice"),
    ("GENERAL", "General Grammar"),
]


def seed_grammar_skills(db: Session) -> int:
    """Adds the grammar skill catalog conversation corrections resolve
    against (Phase 7) - the AI tutor's structured "skill" field is
    normalized to one of these codes, then mapped to a skill_id here so
    corrections feed the same skill_mastery table exercises do. Tied to
    the "English Foundations" course like every other skill. Idempotent -
    returns how many were newly created.
    """
    course = db.query(Course).filter(Course.title == COURSE_TITLE).first()
    if course is None:
        return 0

    existing_codes = {
        s.code for s in db.query(Skill).filter(Skill.course_id == course.id).all()
    }
    created = 0
    for code, name in GRAMMAR_SKILLS:
        if code in existing_codes:
            continue
        db.add(Skill(course_id=course.id, code=code, name=name))
        created += 1
    db.commit()
    return created


def seed_achievements(db: Session) -> int:
    """Creates any catalog achievements that don't already exist. Returns
    how many were newly created."""
    existing_codes = {a.code for a in db.query(Achievement).all()}
    created = 0
    for achievement_def in ACHIEVEMENT_CATALOG:
        if achievement_def.code in existing_codes:
            continue
        db.add(
            Achievement(
                code=achievement_def.code,
                name=achievement_def.name,
                description=achievement_def.description,
            )
        )
        created += 1
    db.commit()
    return created


def seed_short_answer_exercise(db: Session) -> bool:
    """Adds one AI-graded SHORT_ANSWER exercise to the 'Introducing Yourself'
    lesson, demonstrating Phase 6's free-form evaluation in the real seed
    course. Idempotent - a no-op if a SHORT_ANSWER exercise already exists
    there. Separate from seed_english_foundations() because that function's
    course-level idempotency check ("does the course exist yet") predates
    this exercise type and won't retroactively add it to an already-seeded
    course.
    """
    lesson = (
        db.query(Lesson)
        .join(Unit)
        .join(Course)
        .filter(Course.title == COURSE_TITLE, Lesson.title == "Introducing Yourself")
        .first()
    )
    if lesson is None:
        return False

    already_exists = (
        db.query(Exercise)
        .filter(Exercise.lesson_id == lesson.id, Exercise.type == ExerciseType.SHORT_ANSWER)
        .first()
    )
    if already_exists is not None:
        return False

    skill = db.query(Skill).filter(Skill.code == "INTRODUCTIONS").first()
    if skill is None:
        return False

    next_position = (
        db.query(func.max(Exercise.position)).filter(Exercise.lesson_id == lesson.id).scalar()
        or 0
    ) + 1

    exercise = Exercise(
        lesson_id=lesson.id,
        skill_id=skill.id,
        type=ExerciseType.SHORT_ANSWER,
        position=next_position,
        prompt=(
            "Write one or two sentences introducing yourself: your name and where "
            "you are from."
        ),
        payload={},
        correct_answer={
            "model_answer": "My name is Alex and I am from Canada.",
            "rubric": (
                "Should include a name, use 'My name is' or 'I am', and mention a "
                "place of origin with correct grammar."
            ),
        },
        explanation=None,
        difficulty=0.3,
    )
    db.add(exercise)
    db.commit()
    return True


def seed_speaking_and_listening_exercises(db: Session) -> int:
    """Adds one SPEAKING exercise ('At the Restaurant') and one LISTENING
    exercise ('Ordering Food'), demonstrating Phase 8's voice-graded and
    audio-prompted exercise types in the real seed course. Idempotent per
    lesson, same pattern as seed_short_answer_exercise(). Returns how many
    were newly created (0-2).
    """
    created = 0

    speaking_lesson = (
        db.query(Lesson)
        .join(Unit)
        .join(Course)
        .filter(Course.title == COURSE_TITLE, Lesson.title == "At the Restaurant")
        .first()
    )
    speaking_skill = db.query(Skill).filter(Skill.code == "RESTAURANT_PHRASES").first()
    if speaking_lesson is not None and speaking_skill is not None:
        already_exists = (
            db.query(Exercise)
            .filter(
                Exercise.lesson_id == speaking_lesson.id, Exercise.type == ExerciseType.SPEAKING
            )
            .first()
        )
        if already_exists is None:
            next_position = (
                db.query(func.max(Exercise.position))
                .filter(Exercise.lesson_id == speaking_lesson.id)
                .scalar()
                or 0
            ) + 1
            db.add(
                Exercise(
                    lesson_id=speaking_lesson.id,
                    skill_id=speaking_skill.id,
                    type=ExerciseType.SPEAKING,
                    position=next_position,
                    prompt="Say the following sentence aloud:",
                    payload={"phrase_to_say": "Can I have the bill, please?"},
                    correct_answer={
                        "answers": [
                            "Can I have the bill, please?",
                            "Can I have the bill please",
                        ]
                    },
                    explanation=(
                        "A complete, polite request is the clearest way to ask for the bill."
                    ),
                    difficulty=0.3,
                )
            )
            created += 1

    listening_lesson = (
        db.query(Lesson)
        .join(Unit)
        .join(Course)
        .filter(Course.title == COURSE_TITLE, Lesson.title == "Ordering Food")
        .first()
    )
    listening_skill = db.query(Skill).filter(Skill.code == "FOOD_VOCABULARY").first()
    if listening_lesson is not None and listening_skill is not None:
        already_exists = (
            db.query(Exercise)
            .filter(
                Exercise.lesson_id == listening_lesson.id, Exercise.type == ExerciseType.LISTENING
            )
            .first()
        )
        if already_exists is None:
            next_position = (
                db.query(func.max(Exercise.position))
                .filter(Exercise.lesson_id == listening_lesson.id)
                .scalar()
                or 0
            ) + 1
            db.add(
                Exercise(
                    lesson_id=listening_lesson.id,
                    skill_id=listening_skill.id,
                    type=ExerciseType.LISTENING,
                    position=next_position,
                    prompt="Listen to the audio and type what you hear.",
                    payload={},
                    correct_answer={
                        "text_to_speak": "I would like a glass of water, please.",
                        "answers": [
                            "I would like a glass of water, please.",
                            "I would like a glass of water please",
                        ],
                    },
                    explanation=None,
                    difficulty=0.3,
                )
            )
            created += 1

    db.commit()
    return created


def main() -> None:
    db = SessionLocal()
    try:
        course = seed_english_foundations(db)
        if course is None:
            print(f'Course "{COURSE_TITLE}" already exists - nothing to do.')
        else:
            print(f'Seeded course "{COURSE_TITLE}" ({course.id}).')

        created_achievements = seed_achievements(db)
        print(f"Seeded {created_achievements} new achievement(s).")

        created_grammar_skills = seed_grammar_skills(db)
        print(f"Seeded {created_grammar_skills} new grammar skill(s).")

        added_short_answer = seed_short_answer_exercise(db)
        print(
            "Seeded 1 new SHORT_ANSWER exercise."
            if added_short_answer
            else "SHORT_ANSWER exercise already present - nothing to do."
        )

        created_voice_exercises = seed_speaking_and_listening_exercises(db)
        print(f"Seeded {created_voice_exercises} new SPEAKING/LISTENING exercise(s).")
    finally:
        db.close()


if __name__ == "__main__":
    main()
