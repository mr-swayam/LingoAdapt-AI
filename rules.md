# AI Language Learning Tutor — Rules

## 1. General Engineering Rules

1. Build production-quality code, not a throwaway demo.
2. Prefer simple architecture over unnecessary complexity.
3. Keep modules loosely coupled.
4. Use TypeScript strictly.
5. Use Python type hints.
6. Validate all external input.
7. Never expose secrets in client code.
8. Never commit `.env` files.
9. Use environment variables for configuration.
10. Write reusable components and services.
11. Avoid duplicated business logic.
12. Keep business rules on the server.
13. Use database migrations.
14. Add tests for important business logic.

---

## 2. AI Rules

1. Never let an LLM directly mutate critical database state.
2. Validate structured AI output.
3. Use deterministic code for XP, streaks, mastery persistence, permissions, and rewards.
4. Use AI for language understanding, conversation, evaluation, and explanation.
5. Every AI request must have a clear purpose.
6. Avoid unnecessary AI calls.
7. Use the cheapest suitable model for simple tasks.
8. Use stronger models only when the task genuinely requires them.
9. Add timeout and failure handling.
10. Never trust AI output without validation.

---

## 3. Learner Model Rules

1. The learner model is persistent.
2. Every meaningful learning event should be recorded.
3. Mastery should be skill-specific.
4. Mastery must be bounded.
5. Recent performance should matter without completely erasing historical performance.
6. Repeated mistakes should increase practice priority.
7. Long periods without review should increase review priority.
8. A single mistake should not drastically change mastery.
9. A single correct answer should not imply mastery.
10. Keep the mastery algorithm replaceable.

---

## 4. Adaptive Difficulty Rules

Difficulty should increase when:
- Accuracy is consistently high.
- Response confidence is high.
- The learner completes similar exercises successfully.

Difficulty should decrease when:
- The learner repeatedly fails.
- The learner shows confusion.
- The current exercise is substantially above estimated ability.

Do not punish a learner excessively for one difficult question.

---

## 5. Feedback Rules

Feedback should:
- Explain the mistake.
- Show the corrected form.
- Be concise.
- Match learner level.
- Provide an example when useful.
- Avoid unnecessary technical terminology for beginners.

Bad:

```text
Incorrect.
```

Better:

```text
Almost!

✗ I go yesterday.
✓ I went yesterday.

"Yesterday" refers to the past, so use "went".
```

---

## 6. Conversation Rules

The AI tutor should:
1. Maintain conversation context.
2. Speak at the learner's approximate level.
3. Encourage the learner to produce language.
4. Avoid taking over the conversation.
5. Correct important errors without interrupting every sentence.
6. Distinguish between grammar mistakes and acceptable natural variation.
7. Adapt vocabulary and sentence complexity.
8. Remember relevant conversation mistakes through learning events.

---

## 7. Content Rules

1. Do not generate unsafe, offensive, or inappropriate learning content.
2. Avoid ambiguous questions unless ambiguity is intentional.
3. Every exercise should have a clearly defined expected skill.
4. Generated exercises must be validated before publication.
5. Do not rely on AI-generated course content without review for production courses.
6. Preserve language correctness.
7. Keep translations natural rather than mechanically literal.

---

## 8. Gamification Rules

1. Rewards should reinforce learning.
2. Do not reward meaningless button clicking.
3. XP should correspond to meaningful learning activity.
4. Streaks should encourage consistency.
5. Do not create manipulative pressure.
6. Avoid excessive notifications.
7. Users should understand why they received a reward.

---

## 9. UX Rules

1. One primary action per screen where possible.
2. Keep lessons focused.
3. Show progress.
4. Provide immediate feedback.
5. Make errors recoverable.
6. Use animation purposefully.
7. Avoid excessive visual noise.
8. Mobile-first responsive behavior.
9. Keyboard accessibility.
10. Clear loading and error states.

---

## 10. Code Rules

### Frontend
- No `any` unless explicitly justified.
- Prefer server components where appropriate.
- Use client components only when interaction requires them.
- Keep API calls out of presentational components.

### Backend
- Routers should remain thin.
- Business logic belongs in services.
- Database queries belong in repositories/data-access layers where practical.
- Use Pydantic schemas for API contracts.
- Do not place AI prompts inside route handlers.

### Database
- Never edit production schema manually.
- Use migrations.
- Add indexes based on real access patterns.
- Use foreign keys.
- Use transactions for critical state changes.

---

## 11. Testing Rules

Required:
- Unit tests for mastery calculations.
- Unit tests for recommendation logic.
- API tests for authentication and authorization.
- Exercise evaluation tests.
- AI output schema tests.
- Critical frontend interaction tests.

The application should not be considered complete merely because the UI renders.

---

## 12. Definition of Done

A feature is done only when:
- UI exists.
- API exists where required.
- Database changes are migrated.
- Validation exists.
- Error states exist.
- Loading states exist.
- Tests exist for critical logic.
- Authentication/authorization is enforced.
- Documentation is updated.
- Feature works on a clean setup.

---

## 13. Claude Code Working Rules

Claude must:
1. Read all project documentation before modifying code.
2. Follow `project_requirement_document.md`.
3. Treat `architecture.md` as the architectural source of truth.
4. Treat `rules.md` as mandatory engineering policy.
5. Follow `phases.md` and do not skip ahead unnecessarily.
6. Follow `design.md` for UI/UX.
7. Follow `memory.md` for persistent learner context.
8. Inspect the existing repository before creating files.
9. Never overwrite existing working code blindly.
10. Explain architectural conflicts before making major changes.
11. Keep changes incremental.
12. Run tests after meaningful changes.
13. Fix errors before moving to the next phase.
14. Update documentation when architecture changes.
15. Never claim a feature works without verifying it.

---

## 14. Forbidden Shortcuts

Do not:
- Hard-code user progress in frontend state.
- Fake API responses in production paths.
- Store secrets in source code.
- Use mock data as the permanent backend.
- Create duplicate APIs for the same feature.
- Put all application logic into one giant file.
- Use an LLM for deterministic calculations.
- Build microservices before the modular monolith requires them.
