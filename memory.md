# AI Language Learning Tutor — Memory System

## 1. Purpose

Memory is the mechanism through which the platform understands a learner over time.

The system should remember useful learning information without treating every conversation message as permanent memory.

---

## 2. Memory Categories

### A. Learner Profile Memory

Stable preferences:

```text
native_language
target_language
learning_goal
daily_goal
preferred_topics
preferred_difficulty
```

### B. Skill Memory

Long-term learning state:

```text
skill_id
mastery
confidence
attempt_count
correct_count
last_practiced
next_review
```

### C. Error Memory

Recurring mistakes:

```text
error_type
skill_id
example
frequency
last_seen
resolved
```

### D. Vocabulary Memory

For each vocabulary item:

```text
word
meaning
difficulty
mastery
last_seen
next_review
known_contexts
```

### E. Conversation Memory

Only retain useful information.

Store:
- Conversation ID.
- Scenario.
- Key mistakes.
- Skills practiced.
- Summary.
- Useful learner preferences if explicitly relevant.

Do not permanently store every conversational message as learner memory unless product requirements require it.

---

## 3. Memory Lifecycle

```text
Learning Interaction
        ↓
Extract useful learning signals
        ↓
Validate
        ↓
Store learning event
        ↓
Update mastery/error state
        ↓
Update review schedule
        ↓
Use in future recommendations
```

---

## 4. Memory vs History

### History
Raw records of what happened.

Example:

```text
User answered question 18 incorrectly.
```

### Memory
Useful abstraction derived from history.

Example:

```text
User frequently struggles with irregular past tense.
```

History can be large.
Memory should remain useful and compact.

---

## 5. Learner Context Builder

Before an AI tutor call, construct a limited context object.

Example:

```json
{
  "target_language": "English",
  "estimated_level": "A2",
  "current_topic": "Travel",
  "weak_skills": [
    "PAST_TENSE",
    "PREPOSITIONS"
  ],
  "recent_errors": [
    "go/went",
    "in/on"
  ],
  "strong_skills": [
    "FOOD_VOCABULARY"
  ]
}
```

Do not send the entire database history to the model.

---

## 6. Context Priority

When constructing AI context, prioritize:

1. Current conversation.
2. Current lesson/topic.
3. Current learner level.
4. Recent mistakes.
5. Weak skills.
6. Relevant vocabulary.
7. Long-term preferences.

Ignore unrelated memory.

---

## 7. Memory Update Rules

Memory should update when:
- A learner repeatedly makes a mistake.
- A learner demonstrates mastery.
- A new stable learning preference is explicitly established.
- A skill changes significantly.
- A meaningful conversation-learning event occurs.

Do not create persistent memory for:
- One-off casual conversation.
- Temporary system states.
- Unverified AI assumptions.
- Sensitive personal information unrelated to language learning.

---

## 8. Mastery Update

Initial MVP algorithm:

```text
new_mastery =
    old_mastery * historical_weight
    +
    current_result * recent_weight
```

Keep scores between 0 and 100.

Use smoothing so one question cannot radically change mastery.

Example:

```text
Old mastery: 50
Current correct answer: 1
New mastery: 54

Old mastery: 50
Current incorrect answer: 0
New mastery: 46
```

The exact algorithm should be isolated in the learning engine.

---

## 9. Spaced Repetition

Each review item should have:

```text
interval
ease
repetitions
last_reviewed
next_review
```

The initial algorithm can be simple.

Later, the system can implement a more sophisticated scheduling algorithm.

---

## 10. Error Memory

Example:

```json
{
  "user_id": "uuid",
  "skill": "PAST_TENSE",
  "error_type": "WRONG_VERB_FORM",
  "frequency": 7,
  "examples": [
    "I go yesterday"
  ],
  "mastery": 41
}
```

The recommendation engine should use frequency and recency.

---

## 11. Privacy

Memory must be:
- Minimal.
- Relevant.
- User-scoped.
- Deletable.
- Protected by authorization.

Users should eventually be able to:
- View learning memory.
- Reset progress.
- Delete conversation history.
- Delete their account.

---

## 12. Memory Architecture

```text
                ┌─────────────────┐
                │ User Activity │
                └───────┬──────────┘
                        ▼
                ┌─────────────────┐
                │ Learning Event│
                └───────┬──────────┘
                        ▼
              ┌─────────────────────┐
              │ Learning Engine   │
              └───────┬────────────┘
                      │
          ┌───────────┼───────────┐
          ▼           ▼            ▼
       Mastery      Errors      Reviews
          │           │            │
          └───────────┼───────────┘
                      ▼
               Learner Context
                      │
                      ▼
                  AI Tutor
```

---

## 13. Important Principle

> Memory should make the next learning interaction better.

If a stored memory does not improve:
- personalization,
- recommendations,
- feedback,
- difficulty,
- or conversation,

it probably does not need to be stored.
