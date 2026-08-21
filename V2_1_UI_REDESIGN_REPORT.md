# V2.1 Audio Learning Features Report — AI Language Learning Tutor

**Scope:** two audio-centric features added on top of the already-deployed, already-validated (Phase 13/14) application: (1) polishing the existing AI Tutor voice-reply playback, and (2) a new Listening Practice exercise experience with an original animated mascot and richer, fully deterministic answer evaluation. No architecture changes, no new external dependencies beyond an already-installed one (Framer Motion), no AI involved in scoring.

Every result below was produced by actually executing the corresponding check — the real backend test suite, the real frontend test suite, or a real browser (Playwright/Chromium) driving the actual local dev servers (Postgres + Redis + a real Groq API key) end to end. Nothing in this report is inferred or assumed.

---

## 1. What already existed vs. what was built

Investigation before writing any code found that most of the backend plumbing for both features already existed from Phase 8:

| Piece | Status found |
|---|---|
| Authenticated, rate-limited, cost-metered, cached TTS pipeline (`speech_service.py`, `get_metered_ai_provider`) | Already existed, reused as-is |
| `LISTENING`/`SPEAKING` exercise types, exercise-audio endpoint | Already existed, reused as-is |
| Deterministic, non-AI word-diff grading (`pronunciation.py`, used by SPEAKING) | Already existed, generalized and extended |
| `LISTENING` answer evaluation (was: plain exact-string-match, shared with FILL_BLANK/TRANSLATION) | **Gap** — replaced with a dedicated, richer evaluator |
| Tutor voice-reply frontend (play button, `autoPlay`, silent error handling) | **Gap** — reworked for explicit states and real error visibility |
| Original mascot | **Gap** — did not exist, built from scratch |
| Listening Practice UI (instruction text, no-autoplay Listen/Replay controls, mascot integration, word-chip feedback) | **Gap** — built from scratch on top of the existing generic exercise renderer |

This distinction mattered for scope control: no changes were made to `mastery.py`, `learner_model_service.py`, `_grade_text` (still used unmodified by FILL_BLANK/TRANSLATION), or the `LearningEventType` schema — none of it needed to change.

---

## 2. AI Tutor Voice Replies

**Backend: unchanged.** `GET /tutor/conversations/{id}/messages/{id}/audio` was already authenticated, ownership-checked, routed through `get_metered_ai_provider` (30 calls/hour/user, cost-logged via `MeteredAIProvider`), and cached in-process via `speech_service.synthesize_cached`. `SPEECH_MAX_INPUT_CHARS = 200` already truncates provider-side. No backend code was touched for this feature.

**Frontend (`frontend/src/app/tutor/[conversationId]/page.tsx`, `MessageBubble`):**
- Replaced a silent `catch { /* fail silently */ }` with a real, visible error state ("Couldn't play audio - you can still read the reply.") — the reply text itself was already always rendered independently of audio state, so this is strictly additive.
- Replaced the declarative `<audio controls autoPlay>` with an imperative, ref-controlled `<audio>` element plus two explicit icon buttons: Play/Pause toggle and Replay (shown once loaded). Both are plain `<button>` elements with `aria-label`s ("Play tutor reply audio" / "Pause tutor reply audio" / "Replay tutor reply audio"), natively keyboard-focusable and activatable.
- `playbackRate` is explicitly set to `1.0` before playback (a stated default, not an implicit one).
- An `AbortController` cancels an in-flight fetch if the user clicks again while loading, and a rejected `.play()` promise (device/browser audio-policy block) now surfaces as the same visible error state instead of failing invisibly.
- Playback is still gated behind the user's own click (fetch → then `.play()`), so it remains user-initiated, not unexpected autoplay.

**Verified in a real browser** (see §5): audio does not play before an explicit click; the Play button becomes a Pause button while playing; a Replay button appears after the first play; when the audio endpoint is made to fail (network route intercepted), a visible "Couldn't play audio" message appears while the reply text remains fully readable.

---

## 3. Listening Practice

### 3a. Deterministic evaluation (new: `backend/app/services/listening_evaluation.py`)

`pronunciation.py`'s private word-normalization helper was promoted to a public `normalize_words()` (used by both modules now, no duplicated logic) and extended into a 6-category classifier:

| Category | Meaning | Counts as correct? |
|---|---|---|
| `EXACT` | Byte-for-byte match | Yes |
| `NORMALIZED` | Differs only in case/punctuation/whitespace | Yes |
| `MINOR_ERROR` | One small typo or one non-critical missing word (similarity ≥ 0.85) | Yes |
| `PARTIAL` | Meaningful chunk right, meaningful chunk wrong/missing (0.5 ≤ similarity < 0.85) | No |
| `MAJOR_ERROR` | Mostly wrong (similarity < 0.5) | No |
| `INCORRECT` | Empty/no meaningful submission | No |

The `MINOR_ERROR` leniency deliberately mirrors `SPEAKING`'s existing `CORRECT_THRESHOLD = 0.9` tolerance for input-channel noise — a keyboard typo is the typing equivalent of an STT artifact, not a real listening-comprehension failure. Word-level correct/missing/incorrect buckets come from the same `difflib.SequenceMatcher` opcode technique `pronunciation.describe_difference` already used for SPEAKING feedback.

**No AI involved in scoring, deliberately.** The spec allowed AI-assisted feedback on top of deterministic scoring; this implementation doesn't add that layer at all — the expected sentence and the learner's typed text are the only inputs, satisfying "never let an LLM redefine the expected sentence" by construction rather than by a runtime guard, and avoiding new AI cost/latency/failure surface for something string comparison already expresses well.

`grading.py`: `LISTENING` now routes to a new `_grade_listening` (was: shared `_grade_text` with FILL_BLANK/TRANSLATION, which are untouched and still use `_grade_text` exactly as before).

**No new `LearningEventType`, no new migration.** `ANSWER_SUBMITTED` already covers "exercise answered" generically — `mastery.py`'s `compute_new_mastery`/`compute_confidence` only ever look at `is_correct`/`attempt_count`, never exercise type or event content — so a correctly-computed `is_correct` from the new evaluator flows through the existing pipeline unmodified.

### 3b. Original mascot (new: `frontend/src/components/mascot/Mascot.tsx`)

An original, abstract rounded creature (not a bird/owl, not modeled on any known mascot) with six states: `idle`, `speaking`, `listening`, `happy`, `encouraging`, `thinking`. Framer Motion (an already-installed dependency, `^13.1.0`, previously used nowhere in the frontend — this is its first real usage) drives per-state animation variants; `useReducedMotion()` swaps to instant, non-looping state changes when the user has reduced-motion preferences set, with no separate code path to maintain. "Encouraging" (incorrect-answer state) is deliberately warm — a gentle tilt, not a sad/frowning affect — per the product requirement that incorrect answers get encouragement, not a punishing visual.

### 3c. Listening Practice UI

- `ListeningAudioPlayer` (`AnswerInputs.tsx`) no longer auto-plays on mount. Previously it fetched and immediately `autoPlay`ed the dictation audio the instant the exercise loaded, with zero user gesture — exactly the "unexpected autoplay" the spec prohibits, and unreliable on mobile browsers that block gesture-less audio outright. It now fetches in the background (mascot shows `thinking`) and waits for an explicit "▶ Listen" press; a "↺ Replay" button appears after the first play, reusing the same already-fetched audio (no extra network or AI cost — `synthesize_cached` already guarantees server-side caching too).
- `ExerciseRenderer.tsx`'s `LISTENING` branch adds the fixed instruction "Listen carefully and type what you hear" and renders `<Mascot>` above the player, state derived from: loading → `thinking`, ready-not-yet-played → `idle`, playing → `speaking`, typing → `listening`, submitting → `thinking`, graded correct → `happy`, graded incorrect → `encouraging`.
- `FeedbackPanel.tsx` adds a `LISTENING` branch rendering the expected sentence, a category-derived headline ("Perfect!", "Close - small slip", "Partially correct", "Not quite", "Let's try again"), and color-coded word chips (emerald = correct, dashed amber = missing, strikethrough red = incorrectly heard).

---

## 4. Tests added

**Backend** (`pytest`): 314 passed, 0 failed (up from 289 at the last release-candidate check).
- `tests/test_listening_evaluation.py` — 11 new unit tests covering all 6 categories directly (exact, normalization-only via case/punctuation/whitespace, single-word typo, one-word-missing minor error, partial, major error, empty submission, whitespace-only submission, unrelated text, and an explicit invariant test that the expected sentence is never altered by evaluation).
- `tests/test_speaking_listening.py` — 7 new endpoint-level tests: exact match, normalization-only match, minor-typo match with word-chip assertions, partial-answer rejection, major-error rejection, empty-answer rejection, and mastery-update confirmation (`8.0` EMA, same formula as every other exercise type) for a correct listening answer. All pre-existing SPEAKING/LISTENING tests (idempotency, AI-timeout state integrity, audio caching, 404s, oversized-upload 413) pass unmodified.
- Full existing suite re-run in full: **no regressions** in FILL_BLANK/TRANSLATION/SPEAKING or anywhere else.

**Frontend** (`vitest run`): 70 passed, 0 failed, across 14 test files.
- `Mascot.test.tsx` — all 6 states render with the correct accessible label; custom labels honored.
- `ListeningAudioPlayer.test.tsx` — loading state, confirms `play()` is never called before the Listen button is pressed, Replay button appears after first play, error states for both fetch failure and a browser-blocked `.play()` promise.
- `MessageBubble.test.tsx` (tutor voice replies) — text always visible regardless of audio state, no play button rendered for the learner's own messages, play → Replay transition, visible error + intact text on fetch failure, visible error on a blocked `.play()` promise.
- `ExerciseRenderer.test.tsx` — new `LISTENING` describe block: instruction text and mascot present before any audio loads, `EXACT` category shows "Perfect!" with word chips, `PARTIAL` category shows "Partially correct" with the correct missing-word chip.
- `vitest.setup.ts` gained two small, additive global stubs (`URL.createObjectURL`/`revokeObjectURL`, `HTMLMediaElement.prototype.play`/`pause`) since jsdom doesn't implement either — needed by both the new audio-driven components and any future ones; existing tests are unaffected.

---

## 5. Real-browser verification (Playwright/Chromium against the live local dev servers)

A temporary Playwright install (`npm install --no-save`, not committed to `package.json`) drove the actual running frontend (`localhost:3000`) against the actual running backend (`localhost:8000`, real Postgres, real Redis, a real Groq API key) — not mocks, not the test suite.

**Listening Practice walk** (signed up a real learner, admin-promoted a second account via `promote_admin.py` to read expected answers, walked the real "Ordering Food" lesson through the UI to its `LISTENING` exercise):

| Check | Result |
|---|---|
| Listening instruction text shown | PASS |
| Mascot shows `thinking` while audio loads | PASS |
| **Audio does not auto-play** — `play()` called 0 times before user interaction | PASS |
| Listen button is keyboard-focusable | PASS |
| Listen button activates via keyboard (Enter) | PASS |
| Replay button appears after first play | PASS |
| `play()` called exactly once after the Listen action (no double-fire) | PASS |
| Mascot shows `speaking` while audio plays | PASS |
| One-word-typo answer ("glas" for "glass") shows `MINOR_ERROR` headline "Close - small slip" | PASS |
| Incorrect word chip ("glas") shown | PASS |
| Missing word chip ("glass") shown | PASS |
| Mascot shows `happy` for a still-correct (minor-error) answer | PASS |
| Mascot still renders under `prefers-reduced-motion` (fresh context) | PASS |

**Tutor voice-reply walk** (real conversation, real Groq TTS):

| Check | Result |
|---|---|
| Learner's own message text visible | PASS |
| Replay button appears after Play | PASS |
| Audio only plays after explicit click (never before) | PASS |
| Visible error shown when the audio endpoint is made to fail (network route intercepted) | PASS |
| Reply text remains visible after an audio failure | PASS |

No uncaught console/page errors were observed during either walk. 18/18 automated real-browser assertions passed across three separate verification scripts (13 for the listening walk, 5 for the tutor voice-reply walk). Two things went wrong along the way, both in the throwaway scripts themselves, not the product, and both are recorded here rather than silently discarded:
- An early combined script's reduced-motion check reloaded the lesson page mid-attempt, which reset the *client-side* exercise-progress index back to exercise #1 (a MULTIPLE_CHOICE question with no mascot) - the resulting "mascot not found" timeout was the test incorrectly looking for a mascot on a non-LISTENING exercise, not a missing mascot. Rewritten to walk to the LISTENING exercise fresh inside a context created with `reducedMotion: "reduce"` from the start, which passed cleanly.
- A second combined script (reduced-motion + tutor voice reply together) hung indefinitely after an unrelated locator timeout - diagnosed by CPU-time sampling of the Node process (flat at 0.69s across 8+ minutes, i.e. genuinely idle, not slow) and traced to the script never reaching `browser.close()` on its error path, leaving an open Playwright handle that kept the process alive. Split into a minimal, single-purpose script with an explicit `process.exit()` on every path and a 60-second watchdog, which is what actually produced the tutor voice-reply results in the table below.

The temporary `playwright` dependency (installed via `npm install --no-save`, confirmed via `git diff --stat package.json package-lock.json` to have left no trace after `npm uninstall`) and all ad hoc verification scripts are not part of the committed codebase - they lived only in the working tree for this verification pass and were deleted afterward.

---

## 6. Known limitations

- The audio cache (`speech_service._speech_cache`) is in-process and non-persistent, same limitation already documented for Phase 8's original TTS work - a server restart or horizontal scale-out loses cached audio (harmless: it just re-synthesizes on next request, at the cost of one more provider call).
- No dependency-vulnerability scan was re-run for this change set specifically (Phase 13/14 already covers the existing dependency tree; the only new runtime dependency usage is Framer Motion, which was already an installed, audited dependency before this work).
- Listening exercise difficulty is still authored per-exercise via the existing `Exercise.difficulty` field and Phase 5's adaptive-selection engine, per the spec's explicit preference for "high-quality core exercises first" over new automatic difficulty-scoring machinery.
- No background noise or multiple-accent audio variants were added, per the spec's explicit constraint.
