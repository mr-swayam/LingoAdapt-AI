# AI Language Learning Tutor — Architecture

## 1. Architecture Philosophy

Use a modular, API-first architecture.

The system is divided into:
- Presentation.
- Application/API.
- Learning engine.
- AI services.
- Persistence.
- Background jobs.
- Observability.

The AI is an important component, but it is not the application's source of truth.

---

## 2. Recommended Stack

### Frontend
- Next.js
- TypeScript
- Tailwind CSS
- shadcn/ui where useful
- Framer Motion
- React Query/TanStack Query where appropriate

### Backend
- FastAPI
- Python
- Pydantic
- SQLAlchemy or SQLModel
- PostgreSQL

### Authentication
- Supabase Auth or an equivalent managed auth system.

### Storage
- PostgreSQL for application state.
- Object storage for audio/images.

### Cache / Jobs
- Redis.
- Background worker for scheduled jobs and non-blocking processing.

### AI
Provider abstraction supporting:
- LLM.
- Speech-to-text.
- Text-to-speech.
- Optional pronunciation service.

Do not hard-code the application around one model provider.

---

## 3. High-Level Architecture

```text
┌──────────────────────────────────────────┐
│              Next.js Frontend            │
│                                          │
│ Home │ Lessons │ Practice │ AI Tutor     │
│ Progress │ Leaderboard │ Profile         │
└──────────────────────┬────────────────────┘
                       │ HTTPS
                       ▼
┌──────────────────────────────────────────┐
│               FastAPI API                │
│                                          │
│ Auth │ Courses │ Lessons │ Progress      │
│ Practice │ AI Tutor │ Gamification       │
└─────────────┬──────────────┬──────────────┘
             │             │
             │             ▼
             │     ┌────────────────────────┐
             │     │     AI Gateway       │
             │     │                      │
             │     │ Conversation         │
             │     │ Evaluation           │
             │     │ Explanation          │
             │     │ Generation           │
             │     └──────────┬────────────┘
             │                │
             ▼                ▼
┌────────────────────┐   ┌────────────────────┐
│ Learning Engine  │   │ External AI APIs │
│                  │   │ / Model Provider │
│ Mastery          │   └────────────────────┘
│ Difficulty       │
│ Spaced Repetition│
│ Recommendations  │
└──────────┬─────────┘
          │
          ▼
┌──────────────────────────────────────────┐
│                PostgreSQL                │
│ Users │ Courses │ Skills │ Events        │
│ Mastery │ Reviews │ Conversations        │
│ Gamification │ Analytics                 │
└──────────────────────────────────────────┘
```

---

## 4. Frontend Structure

Suggested structure:

```text
frontend/
├── app/
│   ├── (auth)/
│   ├── dashboard/
│   ├── learn/
│   ├── practice/
│   ├── tutor/
│   ├── progress/
│   ├── leaderboard/
│   └── settings/
├── components/
│   ├── ui/
│   ├── lesson/
│   ├── exercise/
│   ├── tutor/
│   ├── gamification/
│   └── progress/
├── hooks/
├── lib/
├── services/
├── types/
└── tests/
```

---

## 5. Backend Structure

```text
backend/
├── app/
│   ├── main.py
│   ├── api/
│   ├── core/
│   ├── models/
│   ├── schemas/
│   ├── services/
│   ├── repositories/
│   ├── learning/
│   ├── ai/
│   ├── gamification/
│   ├── recommendations/
│   ├── jobs/
│   └── tests/
├── alembic/
└── pyproject.toml
```

---

## 6. Domain Modules

### User Module
Owns:
- Profiles.
- Preferences.
- Language settings.

### Course Module
Owns:
- Languages.
- Courses.
- Units.
- Lessons.
- Skills.
- Exercises.

### Learning Module
Owns:
- Learning events.
- Mastery.
- Difficulty.
- Review scheduling.

### Practice Module
Owns:
- Practice sessions.
- Question selection.
- Personalized sets.

### AI Module
Owns:
- Prompt construction.
- Provider abstraction.
- Conversation.
- Evaluation.
- Error classification.
- Explanations.

### Gamification Module
Owns:
- XP.
- Streaks.
- Achievements.
- Quests.
- Currency.

---

## 7. Learning Event Architecture

Every meaningful learning action should create a learning event.

Example:

```json
{
  "user_id": "uuid",
  "exercise_id": "uuid",
  "skill_id": "uuid",
  "event_type": "ANSWER_SUBMITTED",
  "correct": false,
  "error_type": "PAST_TENSE",
  "difficulty": 0.6,
  "response_time_ms": 4300
}
```

The event is then consumed by the learner model.

---

## 8. Learner Model

The learner model should be deterministic.

Input:
- Learning events.
- Historical performance.
- Review intervals.
- Difficulty.

Output:
- Mastery score.
- Confidence.
- Next review date.
- Recommended skills.

A simple initial update can use a bounded incremental formula. Keep the algorithm isolated so it can later be replaced with a more sophisticated model.

---

## 9. Recommendation Engine

Recommendation priority should consider:

```text
Priority =
  weakness
+ review_due
+ recent_mistakes
+ lesson_progress
+ learner_goal
- excessive_repetition
```

Do not make the recommendation engine depend directly on an LLM.

---

## 10. AI Gateway

Use an abstraction such as:

```python
class AIProvider:
    async def chat(...)
    async def evaluate(...)
    async def generate(...)
```

Possible services:

```text
ConversationService
EvaluationService
ExplanationService
ExerciseGenerationService
SpeechService
```

All provider calls should:
- Have timeouts.
- Have retries where appropriate.
- Log latency.
- Track token/cost metadata where available.
- Return structured outputs.
- Fail gracefully.

---

## 11. Structured AI Output

Prefer schemas over free-form AI output.

Example:

```json
{
  "is_correct": false,
  "score": 0.72,
  "errors": [
    {
      "type": "GRAMMAR",
      "skill": "PAST_TENSE",
      "severity": "MEDIUM"
    }
  ],
  "explanation": "Use the past-tense form because the event happened yesterday.",
  "corrected_answer": "I went to the market yesterday."
}
```

Validate the response before using it.

---

## 12. Database Domains

Recommended tables:

```text
users
user_preferences
languages

courses
units
lessons
skills
exercises
exercise_options

learning_events
skill_mastery
vocabulary_items
vocabulary_mastery
review_items

practice_sessions
practice_questions

conversations
conversation_messages
detected_errors

xp_transactions
streaks
achievements
user_achievements
daily_quests

notifications
analytics_events
```

---

## 13. API Design

Example endpoints:

```text
GET    /api/v1/courses
GET    /api/v1/courses/{id}
GET    /api/v1/lessons/{id}
POST   /api/v1/lessons/{id}/start
POST   /api/v1/exercises/{id}/answer

GET    /api/v1/me/progress
GET    /api/v1/me/mastery
GET    /api/v1/me/review

POST   /api/v1/practice/start
POST   /api/v1/practice/{id}/answer

POST   /api/v1/tutor/conversations
POST   /api/v1/tutor/conversations/{id}/messages

GET    /api/v1/leaderboard
GET    /api/v1/achievements
```

---

## 14. Security Boundaries

Client:
- Never receives private AI provider keys.
- Never directly changes mastery.
- Never directly changes XP.
- Never determines authorization.

Server:
- Validates all requests.
- Authenticates users.
- Authorizes resources.
- Owns critical state transitions.

---

## 15. Scalability Principles

Start as a modular monolith.

Do NOT begin with microservices.

Use clear module boundaries so individual services can later be extracted if necessary.

Potential future extraction:
- AI service.
- Speech service.
- Recommendation service.
- Notification worker.

---

## 16. Observability

Track:
- API latency.
- AI latency.
- AI failure rate.
- Exercise completion rate.
- Lesson completion rate.
- Error classification rate.
- Recommendation acceptance.
- Daily active learners.
- Retention.
- Learning improvement.

Never log sensitive conversation content unnecessarily.
