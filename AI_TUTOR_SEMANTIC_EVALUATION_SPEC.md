# AI Tutor Semantic Evaluation — Real-Provider Test Dataset

Status: **Specification only. No code exists yet to run this dataset, and it has not been run.** This document defines the dataset and the pass/fail criteria; running it against the real configured provider is part of implementation, gated by `AI_TUTOR_CONVERSATION_INTELLIGENCE_PLAN.md` §15 as a precondition, not something this document itself executes.

This is a sibling to `AI_TUTOR_CONVERSATION_INTELLIGENCE_AUDIT.md` and `AI_TUTOR_CONVERSATION_INTELLIGENCE_PLAN.md`. Field names (`answer_relevance`, `completeness`, `meaning_status`, `grammar_status`, `naturalness`, `semantic_confidence`, `requires_clarification`) match the plan's §3.3/§5 schema exactly, as revised in that document's Revision 2.

---

## 1. Purpose

The plan's schema and derivation logic (`derive_overall_status`, the confidence-forcing rules) are proven deterministically - they're pure code, exhaustively unit-tested (plan §12.1). What is **not** proven is whether the actual configured Groq model, given the actual proposed prompt (plan §5.4), reliably produces the *inputs* those deterministic functions depend on. This dataset exists to answer that question honestly, with real calls against the real provider, before implementation is trusted - not to be assumed correct because the schema design is sound on paper.

## 2. Dataset composition

**48 cases, 16 categories, 3 cases per category** (the exact categories named in the review request). Each case specifies:
- **Scenario**: the real `ConversationScenario` value it's set in (for prompt realism - varied deliberately across the app's actual 7 scenarios rather than reusing one).
- **Prior context**: the tutor's preceding question (and, for the 3 contradiction cases, an earlier learner statement establishing what's being contradicted).
- **Learner answer**: the exact text sent, deliberately including realistic lowercase/missing-punctuation learner typing patterns where relevant, matching the reported issue's own examples.
- **Expected values** for `answer_relevance`, `completeness`, `meaning_status`, `grammar_status`, and (where applicable) `semantic_confidence`/`requires_clarification`/`naturalness`.
- **Expected tutor behavior**: a short, qualitative description of what a good `reply`/`context_feedback` should do - graded by a human reviewer, never by scripted string-matching free text (§4).

### 2.0 Ground rules (apply to every case below, without exception)

**Issue-granularity rule.** Each concrete incorrect text span is its own `issues[]` entry - even when two spans share the same type (e.g. two separate missing-capitalization spans in one sentence are 2 entries, not 1). This matches the schema itself: `RawTutorIssue.original` is "the exact phrase" - a single span - so a multi-span mistake structurally cannot be reported as one entry without losing which correction applies where. **"Expected issue count" in this document always means mechanical issues only** - GRAMMAR, SPELLING, CAPITALIZATION, PUNCTUATION, TENSE, WORD_CHOICE, VOCABULARY (the types with a real skill mapping, per plan §4). Semantic/contextual signals (relevance, completeness, meaning) are carried entirely by the turn-level fields (`answer_relevance`, `completeness`, `meaning_status`, `context_feedback`) and are never counted as an additional `issues[]` entry on top of that - this avoids the double-counting ambiguity of treating one conceptual meaning problem as also being "1 more issue."

**`semantic_confidence` normalization rules** (mirrors plan §5.3 exactly, restated here so this document is machine-runnable on its own):
- `meaning_status ∈ {CHANGED, SLIGHTLY_WRONG}` → `semantic_confidence ∈ {CONFIDENT, PROBABLE, UNCERTAIN}` (exactly one, never null).
- `meaning_status = PRESERVED` → `semantic_confidence = null` (nothing to be confident about).
- `meaning_status = UNCLEAR` → `semantic_confidence = null` (UNCLEAR already *is* the "don't know" state; confidence about an unclear meaning is not a coherent question).
- `semantic_confidence = UNCERTAIN` → final `requires_clarification` MUST be `true`, regardless of the raw AI flag (forced deterministically).
- `semantic_confidence = UNCERTAIN` → final `corrected_sentence` MUST be `null`, regardless of what the raw AI returned (forced deterministically).

**Default-expectation rule.** Unless a case explicitly states otherwise: expected `requires_clarification = false` and expected `semantic_confidence = null`. This keeps the 37 cases where neither is the point of the test from repeating the same "false / null" pair 37 times, while still giving the runner a definite value for every field on every case.

**No case in this document expresses an expected value as "A or B."** Every field below is a single definite value (or an explicit, closed allowed-set spelled out as such, never bare prose). Sections 2.10 and 2.11 (cases 30, 32, 33) originally contained "or"-style prose in an earlier draft of this document; all three were resolved to single definite values during the pre-implementation consistency audit (see `AI_TUTOR_PREIMPLEMENTATION_CONSISTENCY_REPORT.md`) and the fix is already applied below - there is nothing left to resolve at read time.

### 2.1 Grammar only

1. **RESTAURANT.** Prior: "Would you like something to drink?" Answer: `"yes i want a coffee"`. Expected: relevance=FULL, completeness=COMPLETE, meaning=PRESERVED, grammar=MINOR_ERRORS (2 issues: capitalization "yes"→"Yes", capitalization "i"→"I"). Tutor behavior: brief, friendly correction, conversation continues naturally (e.g. asks about the order).
2. **AIRPORT.** Prior: "Where are you traveling to today?" Answer: `"i are going to paris"`. Expected: relevance=FULL, completeness=COMPLETE, meaning=PRESERVED, grammar=MAJOR_ERRORS (subject-verb agreement "are"→"am", capitalization ×2). Tutor behavior: corrects, still answers/continues about Paris.
3. **CASUAL.** Prior: "What did you do this weekend?" Answer: `"I go to the park and I seen my friend"`. Expected: relevance=FULL, completeness=COMPLETE, meaning=PRESERVED, grammar=MAJOR_ERRORS (past tense "go"→"went", irregular participle "seen"→"saw"). Tutor behavior: corrects both, asks a natural follow-up about the weekend.

### 2.2 Spelling

4. **SHOPPING.** Prior: "What are you looking for today?" Answer: `"I need a new jaket"`. Expected: relevance=FULL, completeness=COMPLETE, meaning=PRESERVED, grammar=MINOR_ERRORS (spelling "jaket"→"jacket").
5. **TRAVEL.** Prior: "How do you usually travel?" Answer: `"I prefer traveling by trian"`. Expected: same shape, spelling "trian"→"train".
6. **COLLEGE.** Prior: "What's your major?" Answer: `"I'm studying computer scince"`. Expected: same shape, spelling "scince"→"science".

### 2.3 Punctuation

7. **RESTAURANT.** Prior: "Anything else you'd like to order?" Answer: `"no thats all thank you"`. Expected: relevance=FULL, completeness=COMPLETE, meaning=PRESERVED, grammar=MINOR_ERRORS (missing apostrophe "thats"→"that's", capitalization).
8. **JOB_INTERVIEW.** Prior: "Why do you want this position?" Answer: `"I think Im a good fit for this role"`. Expected: same shape, missing apostrophe "Im"→"I'm".
9. **SHOPPING.** Prior: "Would you like a receipt?" Answer: `"yes please Ill take one"`. Expected: same shape (2 issues: capitalization "yes"→"Yes", punctuation "Ill"→"I'll").

### 2.4 Capitalization

10. **CASUAL.** Prior: "What's your name?" Answer: `"my name is maria"`. Expected: relevance=FULL, completeness=COMPLETE, meaning=PRESERVED, grammar=MINOR_ERRORS (capitalize "My", "Maria").
11. **TRAVEL.** Prior: "Have you been to any other countries?" Answer: `"yes i visited japan last year"`. Expected: same shape (3 issues: capitalization "yes"→"Yes", capitalization "i"→"I", capitalization "japan"→"Japan").
12. **COLLEGE.** Prior: "What day does your class start?" Answer: `"it starts on monday"`. Expected: same shape, capitalize "It", "Monday".

### 2.5 Tense/context mismatch

13. **SHOPPING (the exact reported example, tense half).** Prior: "Do you like wearing red shoes?" Answer: `"No, I didn't like wearing red shoes."` Expected: relevance=FULL, completeness=COMPLETE, meaning=SLIGHTLY_WRONG, grammar=CORRECT (the sentence *is* grammatically valid - this must not be conflated with a mechanical error), semantic_confidence=CONFIDENT (this is an unambiguous tense mismatch, not a word-meaning question), requires_clarification=false. Tutor behavior: explains the tense doesn't match a present-preference question (rule 10), suggests "don't like" - does **not** just note an apostrophe/capitalization issue (this is the core original complaint - a hard behavioral check, not just a field check).
14. **RESTAURANT.** Prior: "Do you enjoy spicy food?" Answer: `"I didn't like spicy food"`. Expected: same shape as #13.
15. **CASUAL.** Prior: "Are you free this weekend?" Answer: `"I was free"`. Expected: relevance=FULL, completeness=PARTIAL (doesn't actually confirm current availability), meaning=SLIGHTLY_WRONG, grammar=CORRECT, semantic_confidence=CONFIDENT (same reasoning as #13 - an unambiguous tense mismatch, not a word-meaning question), requires_clarification=false. Tutor behavior: notes the tense doesn't confirm current availability, asks directly.

### 2.6 Semantic mismatch

16. **SHOPPING (the exact reported example, full).** Prior: "Do you like wearing red shoes?" Answer: `"no i didnt like wearing new shoes"`. Expected: relevance=FULL, completeness=COMPLETE, meaning=CHANGED, grammar=MINOR_ERRORS (3 issues, present *alongside* the semantic issue and both must be reported: capitalization "no"→"No", capitalization "i"→"I", punctuation "didnt"→"didn't"), **semantic_confidence=UNCERTAIN** (this is the zero-tolerance case - "new" is not a plausible mishearing/typo of "red"; a genuinely different word was used and intent cannot be assumed), **requires_clarification=true**. Tutor behavior: asks "did you mean red shoes or new shoes?" - must **not** silently rewrite to "red shoes" and must **not** treat this as merely a mechanical correction.
17. **JOB_INTERVIEW.** Prior: "What are your strengths?" Answer: `"My biggest weakness is communication"`. Expected: relevance=FULL, completeness=MINIMAL (never states an actual strength), meaning=CHANGED, grammar=CORRECT, semantic_confidence=CONFIDENT (unambiguous - "weakness" directly inverts "strengths", not a plausible mishearing), requires_clarification=false. Tutor behavior: notes this describes a weakness, asks for an actual strength.
18. **COLLEGE.** Prior: "Which season do you like best?" Answer: `"I like winter clothes best"`. Expected: relevance=FULL, completeness=PARTIAL, meaning=SLIGHTLY_WRONG, grammar=CORRECT, semantic_confidence=PROBABLE (plausibly means "winter" the season but drifted to "clothes" - a real but not certain reading), requires_clarification=false (probable, not uncertain - a soft note is enough). Tutor behavior: notes the drift without asserting a fixed interpretation, asks to confirm the season.

### 2.7 Vocabulary substitution

19. **RESTAURANT.** Prior: "How was your meal?" Answer: `"It was very delicious and I enjoyed much"`. Expected: relevance=FULL, completeness=COMPLETE, meaning=PRESERVED, grammar=MINOR_ERRORS (issue type WORD_CHOICE: "enjoyed much"→"enjoyed it a lot"), naturalness=UNDERSTANDABLE_BUT_UNNATURAL.
20. **SHOPPING.** Prior: "How do you feel about the price?" Answer: `"I think it's too much expensive"`. Expected: same shape, WORD_CHOICE "too much expensive"→"too expensive".
21. **TRAVEL.** Prior: "What's your favorite way to explore a new city?" Answer: `"I like to walk by foot around the city"`. Expected: same shape, WORD_CHOICE "walk by foot"→"walk around"/"explore on foot" (redundancy).

### 2.8 Valid alternative answers

22. **RESTAURANT.** Prior: "Do you like tea?" Answer: `"I prefer coffee"`. Expected: relevance=FULL, completeness=COMPLETE, meaning=PRESERVED, grammar=CORRECT, **zero issues, zero corrected_sentence** - must not force a yes/no rewrite.
23. **CASUAL.** Prior: "What's your favorite color?" Answer: `"I don't really have one"`. Expected: relevance=FULL, completeness=COMPLETE (this genuinely is a complete answer), meaning=PRESERVED, grammar=CORRECT, zero issues.
24. **JOB_INTERVIEW.** Prior: "Do you have experience with Python?" Answer: `"Not much, but I've worked a lot with JavaScript"`. Expected: relevance=FULL, completeness=COMPLETE, meaning=PRESERVED, grammar=CORRECT, zero issues.

### 2.9 Partial answers

25. **SHOPPING (the exact reported example).** Prior: "What kind of shoes do you prefer to wear?" Answer: `"i dont like wearing red shoes"`. Expected: relevance=FULL, completeness=PARTIAL, meaning=PRESERVED, grammar=MINOR_ERRORS (2 issues: capitalization "i"→"I", punctuation "dont"→"don't"). Tutor behavior: acknowledges the stated dislike, asks what kind they *do* prefer - not a disconnected new question (rule 16).
26. **COLLEGE.** Prior: "What subjects are you studying this semester?" Answer: `"I'm not studying math this semester"`. Expected: relevance=FULL, completeness=MINIMAL (states an exclusion, never the actual subjects), meaning=PRESERVED, grammar=CORRECT.
27. **TRAVEL.** Prior: "Where would you like to travel next?" Answer: `"I don't want to go somewhere cold"`. Expected: relevance=FULL, completeness=PARTIAL, meaning=PRESERVED, grammar=CORRECT.

### 2.10 Off-topic answers

28. **CASUAL.** Prior: "What color do you like?" Answer: `"My brother is a doctor."` Expected: **relevance=NONE** (zero-tolerance boundary - must not be scored FULL or PARTIAL), completeness=MINIMAL, meaning=PRESERVED, grammar=CORRECT.
29. **JOB_INTERVIEW.** Prior: "Why should we hire you?" Answer: `"The weather is nice today"`. Expected: relevance=NONE, same shape.
30. **AIRPORT.** Prior: "Do you have your boarding pass ready?" Answer: `"I really like this airport's architecture"`. Expected: relevance=LOW (tangentially airport-related - mentions the setting but does not answer the question; deliberately distinct from the hard NONE cases 28-29, giving this dataset real coverage of the LOW value that §4's adjacent-tolerance tier references), completeness=MINIMAL, meaning=PRESERVED, grammar=CORRECT.

### 2.11 Ambiguous answers

31. **SHOPPING.** Prior: "Would you like the blue one or the green one?" Answer: `"the other one"`. Expected: relevance=FULL, completeness=PARTIAL, meaning=UNCLEAR, grammar=MINOR_ERRORS (1 issue: capitalization "the"→"The"), requires_clarification=true, semantic_confidence=null (not applicable when meaning=UNCLEAR, per the plan's §3.2 nullability rule). Tutor behavior: asks which one specifically.
32. **RESTAURANT.** Prior: "Table for how many?" Answer: `"just us"`. Expected: relevance=FULL, completeness=PARTIAL (headcount not actually given as a number, but it is a genuine attempt to answer, not a non-answer), meaning=PRESERVED, grammar=MINOR_ERRORS (1 issue: capitalization "just"→"Just"), requires_clarification=true. Tutor behavior: asks for the specific number.
33. **CASUAL.** Prior: "How was your trip?" Answer: `"It was something"`. Expected: relevance=FULL, completeness=MINIMAL, meaning=UNCLEAR, grammar=CORRECT, requires_clarification=true. Tutor behavior: asks for more detail, doesn't assume positive or negative.

### 2.12 Natural unconventional answers

34. **CASUAL.** Prior: "How's it going?" Answer: `"Can't complain!"` Expected: relevance=FULL, completeness=COMPLETE, meaning=PRESERVED, grammar=CORRECT (an idiomatic fragment is not a grammar error), **naturalness=NATURAL**, zero issues - must not be rewritten into a full formal sentence.
35. **SHOPPING.** Prior: "Did you find everything okay?" Answer: `"Yep, all good!"` Expected: same shape.
36. **RESTAURANT.** Prior: "How is everything?" Answer: `"Great, thanks!"` Expected: same shape.

### 2.13 Opinions/preferences

37. **CASUAL.** Prior: "What's the best season?" Answer: `"I think winter is the best season"`. Expected: relevance=FULL, completeness=COMPLETE, meaning=PRESERVED, grammar=CORRECT, **zero issues disputing the opinion itself** - an opinion must never be marked factually wrong.
38. **TRAVEL.** Prior: "Which is better, mountains or beaches?" Answer: `"Mountains are much better than beaches"`. Expected: same shape.
39. **COLLEGE.** Prior: "Is online or in-person learning better?" Answer: `"In my opinion, in-person is more effective"`. Expected: same shape.

### 2.14 Contradictions within conversation context

**Graded qualitatively only (§4) - the audit found this is only partially, unreliably supported by the current design (full history is sent, but no dedicated schema field exists for it), and this plan does not add one. These 3 cases measure how often the model notices anyway, as information for a future decision - they are not part of the hard pass/fail gate.**

40. **CASUAL.** Earlier learner turn: `"I have two brothers."` Later prior: "Do you have any siblings?" Answer: `"No, I'm an only child."` Informational expectation: ideally `reply`/`context_feedback` gently notes the inconsistency ("earlier you mentioned two brothers - did I misunderstand?"); acceptable if it doesn't, since nothing in the schema formally requires it.
41. **JOB_INTERVIEW.** Earlier: `"I have 5 years of experience."` Later prior: "How long have you been working in this field?" Answer: `"About 2 years"`. Same informational treatment.
42. **TRAVEL.** Earlier: `"I've never been to Europe."` Later prior: "What was your favorite city in Europe?" Answer: `"I loved Rome"`. Same informational treatment.

### 2.15 Multiple simultaneous errors

43. **SHOPPING.** Prior: "What kind of jacket are you looking for?" Answer: `"i want a jaket thats waterproof and i dont like the blue ones"`. Expected: relevance=FULL, completeness=PARTIAL, meaning=PRESERVED, grammar=MINOR_ERRORS, **`issues[]` must contain 5 distinct entries** (capitalization "i"→"I" [1st occurrence], spelling "jaket"→"jacket", punctuation "thats"→"that's", capitalization "i"→"I" [2nd occurrence], punctuation "dont"→"don't") - none merged or dropped, per the issue-granularity rule in §2.0.
44. **RESTAURANT.** Prior: "Do you have any food allergies?" Answer: `"no i dont have alergies but my friend have"`. Expected: relevance=FULL, completeness=COMPLETE, meaning=PRESERVED, grammar=MAJOR_ERRORS, **`issues[]` must contain 5 distinct entries** (capitalization "no"→"No", capitalization "i"→"I", punctuation "dont"→"don't", spelling "alergies"→"allergies", subject-verb agreement "friend have"→"friend has") - none merged or dropped, per the issue-granularity rule in §2.0.
45. **COLLEGE.** Prior: "What's your schedule like this semester?" Answer: `"i has three class on monday and i dont like it"`. Expected: relevance=FULL, completeness=PARTIAL (names one class, not the full schedule), meaning=PRESERVED ("it" refers naturally to "class" within the same sentence - ordinary anaphora, not an unclear reference), grammar=MAJOR_ERRORS, **`issues[]` must contain 6 distinct entries** (capitalization "i"→"I" [1st occurrence], subject-verb agreement "has"→"have", plural "class"→"classes", capitalization "monday"→"Monday", capitalization "i"→"I" [2nd occurrence], punctuation "dont"→"don't") - none merged or dropped, per the issue-granularity rule in §2.0.

### 2.16 Fully correct answers

**Zero-tolerance category (§4) - a fabricated issue/correction on any of these 3 is an automatic dataset-level fail regardless of every other score.**

46. **RESTAURANT.** Prior: "Would you like anything else?" Answer: `"No, thank you. That's all for now."` Expected: overall inputs are fully clean (relevance=FULL, completeness=COMPLETE, meaning=PRESERVED, grammar=CORRECT, naturalness=NATURAL) → derives to `overall_status=CORRECT` → **zero `issues`, `corrected_sentence=null`, `context_feedback=null`, no `ConversationTurnEvaluation` row written** (plan §4).
47. **JOB_INTERVIEW.** Prior: "What are your salary expectations?" Answer: `"I'm flexible, but I was hoping for something in the range we discussed."` Expected: same shape - fully clean.
48. **TRAVEL.** Prior: "How long are you planning to stay?" Answer: `"We're planning to stay for about two weeks."` Expected: same shape - fully clean.

---

## 3. Procedure

Not part of the automated backend test suite (`pytest`) - this is a one-time (or occasional, e.g. after a prompt revision) validation run against the real, metered, billed provider, not a repeatable CI check. A small, temporary script:

1. For each case, constructs the exact system prompt from `AI_TUTOR_CONVERSATION_INTELLIGENCE_PLAN.md` §5.4, with a synthetic message history: the "prior" tutor question as the one preceding TUTOR turn (two prior turns - an earlier learner statement, then the tutor's later question - for the 3 contradiction cases in §2.14), and the case's learner answer as the new user message.
2. Calls the real configured provider via `get_ai_provider()` (not `FakeAIProvider`) with `json_mode=True`, exactly as `conversation_ai.generate_turn` would.
3. Records the raw response verbatim per case, before any grading.
4. Grades each case per §4 below and produces a findings report: per-case pass/fail, per-category pass rate, whether any zero-tolerance item failed, and the overall gate decision from `AI_TUTOR_CONVERSATION_INTELLIGENCE_PLAN.md` §15.

This is 48 real AI calls, made once (or once per prompt-revision cycle) - small, bounded, and disclosed honestly as real cost, not hidden.

## 4. Grading and pass criteria

**Automated, exact-match required (any mismatch is a fail, no tolerance):**
- `answer_relevance`: FULL vs NONE boundary (§2.8-§2.9, cases 22-27, must never read as NONE; §2.10, cases 28-30, must never read as FULL).
- `meaning_status`: PRESERVED vs not-PRESERVED boundary (a real meaning change - cases 16-18 - must never be reported as PRESERVED; a genuinely preserved meaning - cases 1-4, 22-24, 34-39 - must never be reported as CHANGED).
- `semantic_confidence` on cases 16, 31 specifically: **must not be CONFIDENT.** This is the single highest-priority automated check in this entire dataset - it is the literal failure mode the whole review process started from.
- Category 2.16 (cases 46-48): zero issues, zero `corrected_sentence`, zero `context_feedback` - any non-null value here is an automatic fail.

**Automated, adjacent tolerance allowed (one severity step off is a pass, two or more is a fail):**
- `grammar_status` (CORRECT/MINOR_ERRORS/MAJOR_ERRORS boundaries elsewhere).
- `completeness` (COMPLETE/PARTIAL/MINIMAL boundaries).
- `answer_relevance` (FULL/PARTIAL/LOW boundaries, excluding the hard NONE checks above).

**Human-graded, qualitative (no scripted string-matching against exact wording - grading the *behavior*, not the *phrasing*):**
- `issues[]` content quality: does each entry name the right kind of problem, even if worded differently than this document's expectation?
- `reply`/`context_feedback` quality: does it do what "expected tutor behavior" describes (e.g., asks the right clarifying question, acknowledges what was actually said, doesn't silently substitute a word)?
- `naturalness` (§2.12, cases 34-36): inherently subjective even for a human grader - advisory only, not part of the pass-rate calculation.
- Category 2.14 (contradictions): informational only, reported as an observed rate, not scored pass/fail (§2.14's own note).

**Category-level pass thresholds** (percentage of cases in that category meeting the automated + human criteria above):

| Categories | Cases | Threshold |
|---|---|---|
| Grammar / spelling / punctuation / capitalization (§2.1-2.4) | 12 | ≥ 83% (10/12) |
| Tense / semantic mismatch / vocabulary substitution (§2.5-2.7) | 9 | ≥ 78% (7/9) - the core "does it do the new job" bar |
| Valid alternative / partial / off-topic / ambiguous (§2.8-2.11) | 12 | ≥ 75% (9/12) |
| Natural unconventional / opinions (§2.12-2.13) | 6 | ≥ 83% (5/6) - directly tests the anti-overcorrection rules |
| Contradictions (§2.14) | 3 | not scored - informational |
| Multiple simultaneous errors (§2.15) | 3 | ≥ 67% (2/3), all expected issues enumerated per passing case |
| Fully correct (§2.16) | 3 | **100% (3/3) required, zero tolerance** |

**Overall gate** (feeds `AI_TUTOR_CONVERSATION_INTELLIGENCE_PLAN.md` §15 directly):
- **Any zero-tolerance failure (semantic_confidence=CONFIDENT on cases 16/31, or any fabricated issue on cases 46-48) blocks implementation outright**, regardless of the aggregate score elsewhere. This is non-negotiable - it is the exact failure this entire review process exists to prevent.
- With zero zero-tolerance failures: all category thresholds above met → design is validated, implementation may proceed.
- One or two category thresholds missed (zero-tolerance items still passing): targeted prompt revision on the specific failing categories, re-test only those categories, do not block the categories that already passed.
- Three or more category thresholds missed: reconsider the prompt approach broadly, and revisit whether the currently-configured model (chosen for the simpler pre-existing grammar-only task) is still the right choice for this harder task (`AI_TUTOR_CONVERSATION_INTELLIGENCE_PLAN.md` §13 risk 1) - not assumed, decided from these actual results.

## 5. What this document does not do

Does not run the dataset. Does not claim a result. Does not implement the script described in §3. All of that is implementation work, explicitly not part of this planning phase, gated behind the same "do not implement" instruction the two sibling documents are already governed by.
