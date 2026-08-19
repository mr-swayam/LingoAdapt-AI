# AI Language Learning Tutor — Project Requirement Document

## 1. Project Overview

### Project Name
AI Language Learning Tutor

### Product Vision
Build a Duolingo-inspired language-learning platform that combines gamified structured lessons with an adaptive AI tutor. The system should understand a learner's proficiency, recurring mistakes, strengths, weaknesses, learning history, and current context, then adapt lessons, explanations, conversations, and practice accordingly.

### Core Product Promise
> Learn a language through short, engaging lessons while an AI tutor continuously adapts to how you actually learn.

This is not intended to be a visual copy of Duolingo. It should borrow proven language-learning mechanics such as short lessons, XP, streaks, progress, review, and gamification while differentiating through adaptive AI tutoring and a persistent learner model.

---

## 2. Goals

### Primary Goals
1. Provide structured language courses.
2. Support vocabulary, grammar, reading, listening, writing, and speaking.
3. Track learner mastery at a skill level.
4. Detect and classify learner mistakes.
5. Adapt exercise difficulty.
6. Generate personalized practice from historical mistakes.
7. Provide AI-powered conversation practice.
8. Explain mistakes in context rather than merely marking answers wrong.
9. Use spaced repetition for vocabulary and skills.
10. Provide engaging gamification.
11. Make the application responsive and accessible.
12. Design the backend so new languages and courses can be added without rewriting the application.

### Secondary Goals
- Placement assessment.
- Daily goals.
- Streaks.
- XP and rewards.
- Achievements.
- Leaderboards.
- User progress analytics.
- Admin/course-authoring tools.
- Voice-based practice.
- Notifications.

---

## 3. Non-Goals for the Initial MVP

The first release does NOT need:
- Real-money payments.
- Marketplace functionality.
- Social feed.
- Live classes with human teachers.
- Full enterprise administration.
- Hundreds of languages.
- Complex AI model training.
- Custom foundation-model training.

These can be added after the core learning loop is stable.

---

## 4. Target Users

### Beginner Learner
Needs:
- Simple explanations.
- Vocabulary building.
- High repetition.
- Low initial difficulty.
- Encouragement.

### Intermediate Learner
Needs:
- More natural conversation.
- Grammar correction.
- Contextual vocabulary.
- More difficult exercises.

### Advanced Learner
Needs:
- Nuanced grammar.
- Fluency practice.
- Open-ended conversation.
- Idioms and natural expressions.
- Writing feedback.

### Admin / Course Author
Needs:
- Create languages.
- Create courses.
- Create units and lessons.
- Create skills.
- Create exercises.
- Review analytics.
- Manage published content.

---

## 5. Supported Learning Modes

### Lesson Mode
Short structured lessons consisting of several exercises.

### Practice Mode
Targeted practice based on weak skills and past mistakes.

### Review Mode
Spaced-repetition review of previously learned material.

### AI Conversation Mode
Open-ended or scenario-based conversation with an AI tutor.

### Speaking Mode
Voice input, speech-to-text, pronunciation/fluency evaluation where supported.

### Writing Mode
Free-form writing with grammar, vocabulary, and style feedback.

### Placement Mode
Assessment used to estimate the learner's starting level.

---

## 6. Exercise Types

The initial system should support:

1. Multiple choice.
2. Translation.
3. Fill in the blank.
4. Word ordering.
5. Matching.
6. Listening comprehension.
7. Dictation.
8. Sentence correction.
9. Vocabulary recall.
10. Short written answer.
11. Speaking response.
12. AI conversation.

Exercise types must be implemented through an extensible exercise interface rather than hard-coded page-specific logic.

---

## 7. Adaptive Learning Requirements

The system must maintain a learner model.

Each learner should have measurable mastery for:
- Vocabulary skills.
- Grammar skills.
- Reading skills.
- Listening skills.
- Speaking skills.
- Writing skills.
- Topic-specific skills.

Example:

```text
Past Tense          42%
Articles            81%
Prepositions        67%
Food Vocabulary     92%
Travel Vocabulary   54%
```

The learner model must be updated after meaningful learning events.

### Required signals
- Correctness.
- Response difficulty.
- Number of attempts.
- Recent performance.
- Historical performance.
- Time since last practice.
- Error category.
- Exercise type.
- Confidence where available.
- Optional response latency.

### Important architectural rule
The learner model should primarily be maintained through deterministic application logic and database state. Do not make an unnecessary LLM call for every mastery update.

---

## 8. AI Requirements

AI should be used where language understanding is valuable.

### AI Responsibilities
- Conversation.
- Natural-language evaluation.
- Context-aware explanations.
- Error classification.
- Open-ended answer evaluation.
- Personalized feedback.
- Generation of suitable practice content where safe and validated.
- Role-play scenarios.

### AI Should NOT Be the Source of Truth For
- XP balance.
- Streak calculation.
- User permissions.
- Course completion state.
- Currency balances.
- Mastery persistence.
- Authentication.
- Billing.
- Database integrity.

Deterministic backend logic owns these states.

---

## 9. Gamification Requirements

Implement:
- XP.
- Daily streak.
- Daily goal.
- Hearts/lives if enabled.
- Virtual currency.
- Achievements.
- Daily quests.
- Progress bars.
- Lesson completion rewards.
- Level progression.

Gamification must reinforce learning rather than encourage meaningless activity.

---

## 10. Core User Flow

```text
Sign Up
  ↓
Select Native Language
  ↓
Select Target Language
  ↓
Placement Test / Beginner Choice
  ↓
Initial Learner Model
  ↓
Home Dashboard
  ↓
Lesson
  ↓
Exercise
  ↓
Answer
  ↓
Evaluate
  ↓
Record Learning Event
  ↓
Update Mastery
  ↓
Update Review Schedule
  ↓
Award XP / Rewards
  ↓
Recommend Next Activity
```

---

## 11. AI Conversation Flow

```text
Learner
  ↓
Message / Voice
  ↓
Conversation Service
  ↓
Learner Context Builder
  ↓
AI Tutor
  ↓
Response
  ↓
Evaluation / Error Detection
  ↓
Feedback
  ↓
Learning Event
  ↓
Mastery Update
```

The AI should receive only the context required for the current interaction.

---

## 12. Functional Requirements

### Authentication
- Email/password or passwordless authentication.
- OAuth can be added.
- Secure session handling.
- Profile management.

### Course
- Browse courses.
- Select target language.
- Resume current lesson.
- Navigate units.
- Lock/unlock progression when configured.

### Lessons
- Start lesson.
- Resume lesson.
- Submit answers.
- Receive feedback.
- Complete lesson.
- Award XP.

### Progress
- Overall progress.
- Skill mastery.
- Daily activity.
- Streak.
- XP history.
- Review queue.

### AI Tutor
- Start conversation.
- Select scenario.
- Continue conversation.
- Receive corrections.
- End session.
- Record mistakes.

### Practice
- Personalized practice.
- Weak-skill practice.
- Review due items.
- Mistake-based practice.

### Notifications
Optional initially:
- Streak reminder.
- Daily goal reminder.
- Review reminder.

---

## 13. Non-Functional Requirements

### Performance
- Fast initial page load.
- Streaming AI responses where supported.
- Avoid blocking UI on non-critical analytics.
- Cache stable course content.

### Reliability
- AI failure must not corrupt learning state.
- Every learning event should be traceable.
- Database transactions for critical state changes.

### Security
- Server-side authorization.
- Input validation.
- Rate limiting.
- Secrets only on server.
- No client-side API keys.
- Protect AI endpoints from abuse.
- Audit sensitive admin operations.

### Accessibility
- Keyboard navigation.
- Semantic HTML.
- Sufficient contrast.
- Screen-reader friendly controls.
- Captions/transcripts for audio where possible.

---

## 14. Acceptance Criteria

The MVP is successful when a user can:

1. Create an account.
2. Choose a language.
3. Start a course.
4. Complete a lesson.
5. Answer multiple exercise types.
6. Receive instant feedback.
7. Earn XP.
8. Maintain a streak.
9. See progress.
10. Have mistakes stored.
11. See personalized practice.
12. Have an AI conversation.
13. Receive contextual corrections.
14. Have conversation mistakes reflected in future practice.

---

## 15. Product Principle

The product should always answer:

> "What should this learner do next to improve?"

Every major feature should support that question.
