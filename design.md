# AI Language Learning Tutor — Design System

## 1. Design Direction

The application should feel:
- Modern.
- Friendly.
- Educational.
- Gamified.
- Premium.
- Fast.
- AI-native.

Do not make it look like a direct clone of Duolingo.

Use the concept of gamified learning but create an original visual identity.

---

## 2. Visual Concept

### Primary Style
Dark-first AI learning interface with optional light mode.

Suggested visual language:
- Deep navy/near-black backgrounds.
- Cyan/teal accent.
- Warm gold for important achievement/progress highlights.
- Soft white typography.
- Rounded cards.
- Subtle borders.
- Minimal glow.
- Controlled gradients.

The supplied concept slide uses a dark background with cyan borders/accent and gold heading. Use this as visual inspiration, not as a literal UI copy.

---

## 3. Typography

Use a modern sans-serif font.

Recommended hierarchy:

```text
Hero title
32–48px

Page title
28–36px

Section heading
20–24px

Body
15–17px

Supporting text
13–14px
```

Typography should prioritize readability over decoration.

---

## 4. Navigation

Desktop:

```text
┌─────────────────────────────────────────────────────┐
│ Logo     Learn   Practice   Tutor   Progress  👤    │
└─────────────────────────────────────────────────────┘
```

Mobile:
- Bottom navigation.
- 4–5 primary destinations.
- Persistent primary learning action.

---

## 5. Home Dashboard

The home page should immediately answer:

1. What am I learning?
2. What should I do next?
3. How am I progressing?
4. What needs review?

Example:

```text
Good morning 👋

Continue learning
┌──────────────────────────────────┐
│ Spanish                         │
│ Unit 4 · Food & Restaurants     │
│ ████████████████ 78%            │
│                                │
│ [ Continue Lesson ]             │
└──────────────────────────────────┘

Recommended for you
┌──────────────┐ ┌──────────────┐
│ Review     │ │ AI Tutor   │
│ Past tense │ │ Restaurant │
└──────────────┘ └──────────────┘

Daily Goal
██████████████ 70 XP / 100 XP

🔥 12 day streak
```

---

## 6. Lesson UI

A lesson should minimize distractions.

Top:

```text
✕                    3 / 10
███████████████████
```

Center:
- Question.
- Audio/image if required.
- Answer controls.

Bottom:
- Main action.
- Feedback after submission.

---

## 7. Correct Answer State

Use a positive but restrained success state.

Show:
- Correct indicator.
- Short explanation.
- XP earned where relevant.
- Continue action.

Do not cover the screen with excessive animation.

---

## 8. Incorrect Answer State

Show:

```text
Almost!

Your answer:
"I go yesterday."

Correct:
"I went yesterday."

Why?
"Yesterday" indicates the past, so use "went".
```

Then:

```text
[ Continue ]
```

---

## 9. AI Tutor UI

The AI Tutor should feel like a real conversation.

```text
┌────────────────────────────────────┐
│ 🤖 AI Tutor             ● Online    │
├────────────────────────────────────┤
│                                    │
│ AI: Hi! Let's practice ordering    │
│     food at a restaurant.           │
│                                    │
│              You:                  │
│     I'd like pizza please.         │
│                                    │
│ AI: Great! A more natural phrase   │
│     is "I'd like a pizza, please." │
│                                    │
├────────────────────────────────────┤
│ Type a response...        🎤  ➤    │
└────────────────────────────────────┘
```

Include:
- Streaming response.
- Typing indicator.
- Voice button.
- Scenario indicator.
- Difficulty indicator where useful.

---

## 10. Progress Page

Show:
- Overall level.
- XP.
- Streak.
- Skill mastery.
- Recent activity.
- Weak areas.
- Improvement.

Example:

```text
Your Progress

Overall
Level 14

Grammar
█████████████ 78%

Vocabulary
███████████████ 91%

Listening
█████████ 58%

Speaking
████████ 49%

Recommended:
Practice Listening + Speaking
```

---

## 11. Gamification Components

Use:
- XP counters.
- Streak badge.
- Progress rings.
- Achievement cards.
- Quest cards.
- Leaderboard rows.

Avoid:
- Excessive popups.
- Constant rewards.
- Distracting animations.
- Childish visual treatment if the target audience is general learners.

---

## 12. Motion

Use Framer Motion for:
- Page transitions.
- Exercise transitions.
- Progress animation.
- Small success animations.
- Modal transitions.

Avoid:
- Long animations.
- Animation before important content.
- Excessive bouncing.

Animation duration:
- Micro interaction: ~150–250ms.
- Standard transition: ~250–400ms.
- Larger transition: ~400–600ms.

---

## 13. Responsive Design

### Mobile
Primary target.

### Tablet
Two-column layouts where appropriate.

### Desktop
Use centered content with comfortable max widths.

Do not simply stretch the mobile layout across a desktop screen.

---

## 14. Accessibility

Required:
- Keyboard support.
- Visible focus state.
- Semantic buttons.
- ARIA labels where necessary.
- Color must not be the only indicator.
- Reduced-motion support.
- Readable contrast.
- Accessible audio controls.

---

## 15. Design Components

Create reusable components:

```text
Button
Card
ProgressBar
ProgressRing
XPBadge
StreakBadge
LessonCard
ExerciseCard
AnswerOption
FeedbackPanel
SkillCard
AchievementCard
QuestCard
ChatBubble
TutorComposer
AudioButton
MicButton
```

---

## 16. Design Principle

The interface should always make the next learning action obvious.

The learner should never wonder:

> "What should I click now?"
