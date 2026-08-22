# AI Tutor Real-Provider Semantic Evaluation — Report

Status: **Evaluation complete. 48/48 real API calls executed against the actual configured provider. No production code, migrations, commits, or pushes were made.** This report is the entire output of this pass, alongside a temporary, disposable evaluation script and its raw-results JSON, both kept outside `backend/app/` (in the session scratchpad, never part of the application or the git repo).

This is the real-provider gate defined in `AI_TUTOR_CONVERSATION_INTELLIGENCE_PLAN.md` §15 and `AI_TUTOR_SEMANTIC_EVALUATION_SPEC.md` §3-4, run for the first time. **Passing deterministic schema/derivation tests (already proven in the plan's own §12.1) does not prove model quality — this report is the first and only evidence in this entire process about what the actual model actually does.**

---

## 1. Exact provider/model tested

- **Provider**: Groq (`backend/app/ai/groq_provider.py::GroqAIProvider`), invoked via the actual production factory `app.ai.factory.get_ai_provider()` — the exact object `conversation_ai.generate_turn` would receive in production. Not mocked, not stubbed, not a `FakeAIProvider`.
- **Model**: `openai/gpt-oss-120b` — read directly from `backend/.env`'s `AI_DEFAULT_MODEL`, the actual currently-configured production value. **Not substituted with a stronger model.**
- **Call parameters**: `json_mode=True`, `temperature=0.4` (matches production's `conversation_ai.generate_turn` exactly). `max_tokens=2000` — **not** the plan §10 estimate of "roughly 900-1000" (see §12 below for why that estimate proved insufficient in practice).
- **API key**: read from `backend/.env` at runtime via the real `Settings`/`get_ai_provider()` path; never printed, logged, or written to any file by this evaluation. Confirmed present and non-empty before running.

## 2. Exact number of cases executed

**48 of 48 cases** from `AI_TUTOR_SEMANTIC_EVALUATION_SPEC.md`, transcribed verbatim (learner answer text, prior context, scenario) into the evaluation script and cross-checked against the spec document immediately before running. Each case = one real, independent chat-completion call (system prompt + reconstructed history + the case's learner answer as the final user turn).

## 3. Overall PASS/FAIL/ERROR counts

| Outcome | Count | Definition |
|---|---|---|
| **ERROR** (schema-invalid / malformed JSON / provider failure) | **0 / 48** | Every case returned a JSON object that validated against `RawTutorTurn` on the first content-generating attempt. |
| **Informational (not scored)** | 3 / 48 | Cases 40-42 (contradiction category) — exempt from pass/fail per the spec's own §2.14 note. |
| **PASS** (spec §4's own exact-match + adjacent-tolerance tiers) | **38 / 45 scored** | See methodology below. |
| **FAIL** | **7 / 45 scored** | Cases 3, 16, 17, 28, 29, 31, 33. |

**Grading methodology, disclosed explicitly** (the spec defines per-field tiers and category thresholds, not a single formula for "does this case pass" — this is the one place this report makes an explicit, disclosed judgment call, exactly as instructed when no explicit rule exists): a case is marked **FAIL** if it violates (a) the `meaning_status` PRESERVED-vs-not-PRESERVED exact boundary, (b) a zero-tolerance rule (`semantic_confidence≠CONFIDENT` on cases 16/31; zero fabrication on 46-48), or (c) the `answer_relevance` adjacent-tolerance boundary by more than one ordinal step. Everything else — including `grammar_status`/`completeness`/`answer_relevance` misses that stay within the spec's own explicit one-step tolerance — counts as PASS, per the spec's own stated design. `requires_clarification` and issue-count accuracy are tracked and reported throughout (they surfaced real, meaningful failures — see §7, §9) but are **not** formally part of any pass/fail tier in `AI_TUTOR_SEMANTIC_EVALUATION_SPEC.md` §4 as written; this gap in the spec's own grading design is itself a finding, reported in §13.

## 4. Results by evaluation category

| Category | Cases | Threshold (spec §4) | Result | Verdict |
|---|---|---|---|---|
| Grammar/spelling/punctuation/capitalization (§2.1-2.4) | 12 | ≥83% (10/12) | 11/12 (91.7%) — only case 3 fails | **MET** |
| Tense/semantic mismatch/vocabulary substitution (§2.5-2.7) | 9 | ≥78% (7/9) | 7/9 (77.8%) — fails on 16, 17 | **MET** (exactly at the spec's own stated ratio) |
| Valid alternative/partial/off-topic/ambiguous (§2.8-2.11) | 12 | ≥75% (9/12) | 8/12 (66.7%) — fails on 28, 29, 31, 33 | **MISSED** |
| Natural unconventional/opinions (§2.12-2.13) | 6 | ≥83% (5/6) | 6/6 (100%) | **MET**, clean |
| Contradictions (§2.14) | 3 | not scored | 0/3 noticed (informational) | n/a |
| Multiple simultaneous errors (§2.15) | 3 | ≥67% (2/3), **all expected issues enumerated per passing case** | 3/3 pass on relevance/meaning/grammar tolerance, but **0/3 achieve full issue enumeration** (4 of 5 expected, 4 of 5, 4 of 6 — see §7) — the category's own defining criterion is "enumerated," so by its own literal wording this category scores **0/3** | **MISSED** |
| Fully correct / zero-fabrication (§2.16) | 3 | **100% (3/3), zero tolerance** | 3/3, zero fabricated issues/corrections/feedback on any case | **MET**, perfect |

**Additional, separately-tracked findings not covered by any category threshold**: `answer_relevance` FULL/NONE zero-tolerance boundary (§2.8-§2.10) — **held** (cases 22-30 never misfired across that hard line). `semantic_confidence` zero-tolerance on cases 16/31 — **case 16 violated** (see §6). Category-2.16 zero-fabrication — **held perfectly**.

## 5. Results for all 48 cases

Legend: **R**elevance (F=FULL P=PARTIAL L=LOW N=NONE), **C**ompleteness (C=COMPLETE P=PARTIAL M=MINIMAL), **M**eaning (PR=PRESERVED SW=SLIGHTLY_WRONG CH=CHANGED UN=UNCLEAR), **G**rammar (CO=CORRECT MI=MINOR_ERRORS MA=MAJOR_ERRORS), **SC**=semantic_confidence (∅=null CF=CONFIDENT PB=PROBABLE UC=UNCERTAIN), **RC**=requires_clarification, **Iss**=mechanical issue count. Format per cell: `expected→actual`; `=` means exact match.

| # | Category | R | C | M | G | SC | RC | Iss | Verdict |
|---|---|---|---|---|---|---|---|---|---|
| 1 | Grammar only | F= | C= | PR= | MI= | ∅= | F= | 2→1 | PASS (issues bundled, see §7) |
| 2 | Grammar only | F= | C= | PR= | MA→MI | ∅= | F= | 3→2 | PASS (tolerant; internal severity/status inconsistency, see §7) |
| 3 | Grammar only | F= | C= | **PR→SW** | MA= | ∅→CF | F= | 2= | **FAIL** (meaning boundary) |
| 4 | Spelling | F= | C= | PR= | MI= | ∅= | F= | 1= | PASS, clean |
| 5 | Spelling | F= | C= | PR= | MI= | ∅= | F= | 1= | PASS, clean |
| 6 | Spelling | F= | C= | PR= | MI= | ∅= | F= | 1= | PASS, clean |
| 7 | Punctuation | F= | C= | PR= | MI= | ∅= | F= | 2→1 | PASS (bundled) |
| 8 | Punctuation | F→P | C→P | PR= | MI= | ∅= | F= | 1= | PASS (tolerant, debatable — see §7) |
| 9 | Punctuation | F= | C= | PR= | MI= | ∅= | F= | 2→1 | PASS (one span missed, not just bundled) |
| 10 | Capitalization | F= | C= | PR= | MI= | ∅= | F= | 2→1 | PASS (bundled) |
| 11 | Capitalization | F= | C= | PR= | MI= | ∅= | F= | 3→1 | PASS (fully bundled) |
| 12 | Capitalization | F= | C= | PR= | MI= | ∅= | F= | 2→1 | PASS (bundled) |
| 13 | Tense mismatch | F= | C= | SW= | CO= | CF= | F= | 1(tense)= | PASS, clean — **core original bug, tense half** |
| 14 | Tense mismatch | F= | C= | SW= | CO= | CF= | F= | 1= | PASS, clean |
| 15 | Tense mismatch | F= | C→P | SW= | CO= | CF= | F= | 1= | PASS, clean |
| 16 | Semantic mismatch | F→P | C= | CH= | MI= | **UC→CF** | **T→F** | 3= | **FAIL — zero-tolerance violation. Flagship case.** See §6. |
| 17 | Semantic mismatch | **F→N** | M= | CH= | CO= | CF= | F= | 0= | **FAIL** (relevance 3 steps off, cascades overall_status) |
| 18 | Semantic mismatch | F→P | P= | SW= | CO= | PB→CF | F= | 0= | PASS (tolerant; confidence-tier miss reinforces overconfidence pattern) |
| 19 | Vocabulary substitution | F= | C= | PR= | MI= | ∅= | F= | 1= | PASS, clean (naturalness= also exact) |
| 20 | Vocabulary substitution | F= | C= | PR= | MI= | ∅= | F= | 1= | PASS, clean |
| 21 | Vocabulary substitution | F= | C= | PR= | MI= | ∅= | F= | 1= | PASS, clean |
| 22 | Valid alternative | F= | C→P | PR= | CO= | ∅= | F= | 0= | PASS (tolerant — misses rule 12's anti-overcorrection intent, see §7) |
| 23 | Valid alternative | F= | C= | PR= | CO= | ∅= | F= | 0= | PASS, clean |
| 24 | Valid alternative | F= | C= | PR= | CO= | ∅= | F= | 0= | PASS, clean |
| 25 | Partial answers | F= | P= | PR= | MI= | ∅= | F= | 2= | **PASS, perfect — core original bug, partial-answer half.** See §6. |
| 26 | Partial answers | F= | M→P | PR= | CO= | ∅= | F= | 0= | PASS (tolerant) |
| 27 | Partial answers | F= | P= | PR= | CO= | ∅= | F= | 0= | PASS, clean |
| 28 | Off-topic | N= | M= | **PR→CH** | CO= | ∅→CF | F= | 0= | **FAIL** (meaning boundary) |
| 29 | Off-topic | N= | M= | **PR→CH** | CO= | ∅→CF | F= | 0= | **FAIL** (meaning boundary) |
| 30 | Off-topic | L→P | M= | PR= | CO= | ∅= | F= | 0= | PASS (tolerant) |
| 31 | Ambiguous | F= | P= | **UN→PR** | MI→CO | ∅= | **T→F** | 1→0 | **FAIL** (meaning boundary; misses real capitalization issue too) |
| 32 | Ambiguous | F= | P→C | PR= | MI→CO | ∅= | **T→F** | 1→0 | PASS on formal tiers, but **never asks for the missing headcount — see §9** |
| 33 | Ambiguous | F= | M= | **UN→PR** | CO= | ∅= | **T→F** | n/a | **FAIL** (meaning boundary) |
| 34 | Natural unconventional | F= | C= | PR= | CO= | ∅= | F= | 0= | PASS, clean (naturalness= exact) |
| 35 | Natural unconventional | F= | C= | PR= | CO= | ∅= | F= | 0= | PASS, clean |
| 36 | Natural unconventional | F= | C= | PR= | CO= | ∅= | F= | 0= | PASS, clean |
| 37 | Opinions | F= | C= | PR= | CO= | ∅= | F= | 0= | PASS, clean |
| 38 | Opinions | F= | C= | PR= | CO= | ∅= | F= | 0= | PASS, clean |
| 39 | Opinions | F= | C= | PR= | CO= | ∅= | F= | 0= | PASS, clean |
| 40 | Contradiction (informational) | — | — | — | — | — | — | — | not scored; contradiction **not noticed** |
| 41 | Contradiction (informational) | — | — | — | — | — | — | — | not scored; contradiction **not noticed** |
| 42 | Contradiction (informational) | — | — | — | — | — | — | — | not scored; contradiction **not noticed** |
| 43 | Multiple errors | F= | P→C | PR= | MI= | ∅= | F= | 5→4 | PASS on tolerance; **fails §2.15's enumeration criterion** |
| 44 | Multiple errors | F= | C= | PR= | MA→MI | ∅= | F= | 5→4 | PASS on tolerance; **fails §2.15's enumeration criterion**; missed "no"→"No" entirely |
| 45 | Multiple errors | F= | P= | PR= | MA= | ∅= | F= | 6→4 | PASS, clean on fields; **fails §2.15's enumeration criterion** |
| 46 | Fully correct | F= | C= | PR= | CO= | ∅= | F= | 0= | PASS, perfect — zero fabrication |
| 47 | Fully correct | F= | C= | PR= | CO= | ∅= | F= | 0= | PASS, perfect — zero fabrication |
| 48 | Fully correct | F= | C= | PR= | CO= | ∅= | F= | 0= | PASS, perfect — zero fabrication |

## 6. The two original shoe failure cases, in detail

### Case 16 — "no i didnt like wearing new shoes" (the flagship semantic-mismatch case)

This case exists specifically because the zero-tolerance bar in `AI_TUTOR_SEMANTIC_EVALUATION_SPEC.md` §4 was written for exactly this failure mode. **It failed.**

**Official 48-case run's result:**
```
answer_relevance:    expected FULL      → actual PARTIAL
meaning_status:      expected CHANGED   → actual CHANGED        ✓ (model DID detect the substitution)
grammar_status:      expected MINOR     → actual MINOR_ERRORS   ✓ (correctly caught all 3 mechanical spans this run)
semantic_confidence: expected UNCERTAIN → actual CONFIDENT      ✗ ZERO-TOLERANCE VIOLATION
requires_clarification: expected true   → actual false          ✗
corrected_sentence:   "No, I didn't like wearing new shoes."   (preserved "new" — did NOT silently substitute this run)
context_feedback:     "You answered about new shoes, but the question asked about red shoes."  (honestly flags the mismatch)
reply:                "Got it, you don't like new shoes. Do you prefer a different color, like red?"
```

The model **did** notice the word substitution (`meaning_status=CHANGED` is correct) and, in this specific sampled run, did **not** literally rewrite "new shoes" to "red shoes" in `corrected_sentence`. But it labeled its own judgment `CONFIDENT` rather than `UNCERTAIN` — asserting certainty about a case the dataset was deliberately built to be genuinely ambiguous — which is the exact failure the zero-tolerance rule exists to catch regardless of how the surrounding text happens to read.

**A second, independent real call to the identical case** (made during pre-run tuning, before the official 48 — disclosed here rather than discarded, since it is real, relevant evidence about this exact case's reliability) produced a **worse** outcome on the same inputs:
```
semantic_confidence: CONFIDENT (same violation)
corrected_sentence:  "No, I don't like wearing red shoes."   ← silently substituted "new" → "red"
requires_clarification: false
```
This is the **literal original bug report** recurring verbatim: the model confidently invented the learner's intent and silently rewrote their answer to match the question's word instead of their own, with no clarification requested. Two independent real calls to the same ambiguous case, at `temperature=0.4`: both asserted `CONFIDENT`; one of the two additionally performed the exact silent substitution the whole review process exists to prevent. `semantic_confidence` was never `UNCERTAIN` in either attempt.

### Case 25 — "i dont like wearing red shoes" (the partial-answer half)

```
answer_relevance:    FULL     = FULL       ✓
completeness:        PARTIAL  = PARTIAL    ✓
meaning_status:       PRESERVED = PRESERVED ✓
grammar_status:       MINOR    = MINOR_ERRORS, 2/2 issues correctly separated (i→I, dont→don't) ✓
reply: "I see, you don't like red shoes. What color or style do you prefer?"
```
**This one passed perfectly, on every field, with an excellent, exactly-on-spec reply** ("acknowledges the stated dislike, asks what kind they *do* prefer" — matches the spec's expected tutor behavior verbatim). The grammar-correction, partial-answer-recognition, and natural-follow-up behavior that motivated this half of the original bug report all worked correctly on the real model, on the real provider, first try.

**Together, these two flagship cases show an asymmetric result**: the *grammar/partial-answer* half of the original complaint is fixed by this design and the real model executes it well. The *semantic-ambiguity/confident-guessing* half — the harder, more safety-critical half — is **not** reliably fixed. The model can detect that a word was substituted, but does not reliably down-grade its own confidence when it should, which is precisely the gap concern 3's `semantic_confidence` field was designed to close and precisely where it did not hold up under real testing.

## 7. Every failure and its root-cause classification

| Case(s) | Failure | Root cause |
|---|---|---|
| 16 | `semantic_confidence=CONFIDENT` on the flagship ambiguous case (zero-tolerance) | **Model semantic misunderstanding** — see §11 for the dataset-wide pattern this belongs to |
| 31, 33 | `meaning_status=PRESERVED` when the answer is genuinely ambiguous (expected `UNCLEAR`); `requires_clarification` stayed `false` in both | **Model semantic misunderstanding** — the model does not recognize the ambiguity exists at all in these two cases, a different (arguably worse) failure mode than case 16's "recognizes but over-asserts confidence" |
| 3 | `meaning_status=SLIGHTLY_WRONG` on a pure grammar/verb-form mistake ("I go...I seen" answering a past-tense-appropriate question) | **Prompt ambiguity** — rule 10's tense-mismatch guidance plausibly over-triggers on any past-tense-adjacent error, not just genuine tense/context mismatches |
| 17 | `answer_relevance=NONE` on an on-topic-but-wrong-content answer (interview weakness vs. strength) | **Prompt ambiguity** — rules 9/11/13 do not clearly separate "unrelated topic" from "related topic, wrong content," so the model collapses `answer_relevance` and `meaning_status` at exactly the boundary concern 2 of the plan was designed to separate |
| 28, 29 | `meaning_status=CHANGED` on genuinely off-topic-but-literally-true statements | Same relevance/meaning conflation as case 17, opposite direction — **Prompt ambiguity** |
| 18 | `semantic_confidence=CONFIDENT` where the case was designed to elicit `PROBABLE` (not zero-tolerance, but reinforcing) | **Model semantic misunderstanding / overconfidence pattern** — see §11 |
| 22 | `completeness=PARTIAL` on a valid alternative answer ("I prefer coffee"), against rule 12's explicit anti-overcorrection instruction | **Model semantic misunderstanding** — rule 12 exists and is followed correctly elsewhere (cases 23, 24, 34-39 all pass this exact test cleanly), so this looks like an inconsistent application rather than a missing rule |
| 32 | Never resolves "just us" into an actual headcount; `requires_clarification` stayed `false`; moves the conversation forward with a real practical gap unaddressed | **Model semantic misunderstanding**, compounded by **Evaluation dataset ambiguity** — `requires_clarification` accuracy is not formally covered by any §4 tier, so this real, meaningful failure would be invisible to the spec's own literal grading criteria without this report's supplemental tracking |
| 1, 2, 7, 9, 10, 11, 12, 43, 44, 45 | `issues[]` entries bundle multiple distinct error spans into one entry, or drop a repeated span entirely (most often a second lowercase "i", or a sentence-initial "no"/"yes") — the exact same undercounting shape this session's own consistency audit found and fixed *in the dataset itself* two turns ago | **Prompt ambiguity** — the system prompt never states "one issue entry per distinct error span, never bundle, never skip a repeat," even though the dataset's own issue-granularity rule (§2.0) assumes exactly that. **This is the single most fixable finding in this report**: it plausibly explains all of §2.15's category-threshold failure and several smaller misses elsewhere, and a one-sentence prompt addition is a small, targeted, testable fix |
| 2 | An issue with `severity="major"` reported alongside `grammar_status="MINOR_ERRORS"` for the same turn | **Schema design problem** — nothing in the prompt or schema ties per-issue severity to the aggregate `grammar_status`, so the two can silently disagree |
| 40, 41, 42 | Cross-turn contradictions never noticed (0/3) | Not a failure — informational only per the spec's own §2.14 note, consistent with the audit's original prediction that this is unsupported. **Provider/model structured-output failure**: none — every case returned valid, schema-conformant JSON on the first attempt (see §8) |

## 8. Malformed or invalid AI responses

**Zero, within the official 48-case run.** Every one of the 48 calls returned JSON that parsed and validated against `RawTutorTurn` on the first content-generating attempt — `max_tokens=2000` (see §12) was sufficient in every case.

**One malformed response occurred during pre-run tuning** (not part of the official 48, disclosed for completeness): an initial test of case 16 at `max_tokens=1000` (the plan §10 estimate) failed with Groq's `json_validate_failed` / *"max completion tokens reached before generating a valid document"* — the model's internal reasoning-token usage consumed the budget before the visible JSON completed. This is not a schema-design failure or a model-comprehension failure; it is a token-budget-sizing issue, fully resolved by raising the ceiling, and is reported here as a real, concrete data point about this specific model's completion-token variability (see §12) rather than swept aside as a script bug.

## 9. Whether ambiguity handling worked safely

**No, not reliably.** This is the central question the entire review process exists to answer, and the honest answer from real data is negative:

- Case 16 (the flagship, deliberately-ambiguous case): failed zero-tolerance on both real attempts made against it.
- Cases 31, 33 (the "Ambiguous answers" category): both failed to recognize the ambiguity existed at all — `meaning_status` was reported as `PRESERVED`, not `UNCLEAR`, and `requires_clarification` never fired.
- Case 32: recognized as related but never actually obtained the missing information (headcount) before moving the conversation forward.
- **Across all 48 real calls, `semantic_confidence` was `CONFIDENT` 9 times, `null` 39 times, and `PROBABLE` or `UNCERTAIN` **zero** times** — see §11. The three-way hedging scale the schema and prompt rule 17 explicitly define was functionally never used as a three-way scale in practice.

The one case where ambiguity handling worked as designed — case 25's "partial answer, ask for the missing piece" pattern — is a *completeness* case, not a *meaning-ambiguity* case; the genuinely hard half of the ambiguity problem (cases 16, 31, 32, 33 — meaning-level and referential ambiguity) did not hold up.

## 10. Whether the model invented learner intent

**Yes, at least once, directly observed.** The pre-official-run repeat call on case 16 silently rewrote the learner's actual words ("new shoes") into the question's words ("red shoes") inside `corrected_sentence`, while reporting `semantic_confidence=CONFIDENT` and `requires_clarification=false` — asserting a specific interpretation of a genuinely ambiguous input as if it were settled fact. The official run's own sampled outcome for the same case, while not repeating the literal word-substitution, still asserted `CONFIDENT` on the same case — a milder but structurally identical instance of the same failure (confidently treating an ambiguous case as resolved). Neither of the two real, independent attempts at this specific case ever produced the `UNCERTAIN` classification the dataset was built to require.

## 11. Whether one AI call was sufficient in practice

**Structurally, yes — at the right token budget.** Every one of the 48 official calls produced a complete, valid, schema-conformant response from a single request; no case required a retry due to malformed content, and the rate-limit retries encountered (see §12) were an infrastructure/quota concern, not a model-comprehension one. `conversation_ai.generate_turn`'s "one AI call per learner message" architecture (plan §2, §10) holds up mechanically.

**But "one call is sufficient" does not mean "one call is reliably correct."** The bigger finding from this evaluation is not about call *count* — it's that within that single call, the model's `semantic_confidence` field behaved almost binarily rather than as the intended three-way hedge: **9 `CONFIDENT`, 0 `PROBABLE`, 0 `UNCERTAIN`, 39 `null`**, across 48 real calls including two cases (16, 18) specifically constructed to elicit `PROBABLE`/`UNCERTAIN`. This is very likely the single mechanism behind most of this report's failures: rule 17 offers three confidence tiers, but in practice the model appears to treat the field as "state it plainly" or "don't mention it," never "hedge." This is the most important, most reportable, single finding of this entire evaluation, and it directly explains why the zero-tolerance case failed twice.

## 12. Latency/cost observations

| Metric | Value |
|---|---|
| Total real API calls (official run) | 48 (plus 2 pre-run tuning calls, disclosed above, not counted here) |
| Successful responses | 48 / 48 |
| Malformed responses (official run) | 0 |
| Schema validation failures (official run) | 0 |
| Retries due to malformed output | 0 |
| Retries due to provider rate-limiting | 44 of 48 calls hit a `429 rate_limit_exceeded` at least once (Groq org-level cap: **8000 tokens/minute** on this model, at the account's current tier — a real, discovered-live constraint, not anticipated by the plan or spec) — each was retried automatically after waiting exactly the duration Groq's own error response specified, never skipped |
| Total wall-clock time | 671.0s (~11.2 minutes) — almost entirely rate-limit wait time, not model latency |
| Per-call latency (model only) | avg 1963ms, p50 1818ms, min 1154ms, max 3461ms |
| Prompt tokens | sum 69,455, avg 1447/call (near-constant — the system prompt dominates, as expected) |
| Completion tokens | sum 29,512, avg 615/call, **min 224, max 1298** — over 5x variance call-to-call, consistent with this model's internal reasoning-token usage varying independently of visible output length (see §8's `max_tokens=1000` failure) |
| Total tokens (48 calls) | 98,967 |
| Dollar cost | **Not stated** — this report gives exact token counts rather than a fabricated dollar figure; converting to cost requires Groq's current published per-model rate for `openai/gpt-oss-120b`, which was not looked up as part of this evaluation and is not guessed here |

**A real, concrete infrastructure finding for implementation planning**: the current Groq account tier's 8000 TPM cap on this model means **48 sequential real calls take on the order of 10+ minutes purely from rate-limit waiting**, not model latency. This has no effect on the *production* single-message-at-a-time usage pattern (each real user sends one message at a time, well under 8000 tokens/minute even at worst-case concurrency the app's existing `AI_RATE_LIMIT_PER_HOUR=30` per-user budget implies), but it is directly relevant to any *future* batch re-evaluation run (e.g., after a prompt revision) — budget real wall-clock time for it, or request a higher Groq tier before the next run.

## 13. Recommended changes

Ranked by leverage, all targeted at the prompt (§5.4) — nothing here implies a schema/architecture problem:

1. **Add an explicit issue-granularity instruction to the system prompt.** The dataset's own §2.0 ground rule ("each concrete incorrect span is its own `issues[]` entry") was never communicated to the model — the prompt only says "only include an issue for something genuinely worth teaching." This plausibly explains the bundling/undercounting pattern seen in 10 of 48 cases, including all 3 failures of §2.15's category threshold. Recommended addition to rule set: *"Each distinct incorrect span gets its own entry in `issues[]`, even if two spans are the same type or appear close together in the sentence (e.g., two separate missing-capitalization words are two entries, not one) — never merge multiple corrections into a single entry's `suggestion`, and never skip a repeated instance of the same kind of mistake."*
2. **Strengthen rule 17's confidence-calibration instruction** with a concrete worked example of when `PROBABLE`/`UNCERTAIN` apply, since the real model never produced either value across 48 calls despite two cases designed to elicit them. The current rule states the three tiers abstractly; this evaluation suggests the model needs a concrete anchor (e.g., explicitly walk through the red/new-shoes-style example inline in the prompt, the way this project has walked through it in every planning document) rather than an abstract definition alone.
3. **Clarify the boundary between `answer_relevance` and `meaning_status`** for the specific case of "on-topic but substantively wrong content" (cases 17, 28, 29 all conflated these in one direction or the other). A one-line clarification — *"`answer_relevance` measures topic-relatedness only; a factually/substantively wrong answer to the right question is a `meaning_status` problem, not a relevance problem, even if the wrongness is severe"* — directly targets the observed failure.
4. **Do not touch `derive_overall_status`, the schema, or persistence design** based on this run — every failure traced back to an AI-reported field being wrong, not to the deterministic derivation logic misusing a correct field. The derivation logic worked exactly as designed on every case (e.g., case 17's wrong `overall_status=OFF_TOPIC` is a correct *derivation* from a wrong *input*, not a derivation bug).
5. **Re-run this exact 48-case dataset after the prompt changes above**, before revisiting the implementation question, per the plan's own §15 gate.

## 14. Final verdict

**B. PROMPT/SCHEMA NEEDS REVISION — revise and re-evaluate.**

Per `AI_TUTOR_SEMANTIC_EVALUATION_SPEC.md` §4's own overall-gate rule, written and committed *before* this evaluation ran: **"Any zero-tolerance failure... blocks implementation outright, regardless of the aggregate score elsewhere. This is non-negotiable."** Case 16 violated the `semantic_confidence≠CONFIDENT` zero-tolerance rule on two independent real attempts. That alone is dispositive, by the gate's own pre-committed design — not a judgment call made after seeing the results.

This is **not** verdict C ("model not suitable"). The majority of the dataset performed well on the real model: 4 of 7 scored categories met or exceeded threshold, including a perfect 6/6 on the anti-overcorrection tests (§2.12-2.13) and a perfect 3/3 zero-fabrication result (§2.16) — the model never once hallucinated a correction on genuinely clean input, across 3 tries. The tense-mismatch half of the original bug report (cases 13-15) and the partial-answer half (case 25) both passed cleanly on real data. The failures cluster tightly around one specific, identifiable, well-evidenced mechanism (§11's confidence-calibration binariness) rather than being spread evenly across the whole dataset, which is exactly the shape of problem a targeted prompt revision is suited to fix — not a reason to abandon the currently-configured model.

**Do not claim READY FOR IMPLEMENTATION.** Per this report's own findings and the plan's pre-committed gate: revise the prompt per §13 above, then re-run this same 48-case dataset (or, if scope allows, at minimum cases 3, 16, 17, 18, 22, 28, 29, 31, 32, 33, 43, 44, 45) against the real provider again before the implementation question is revisited.

---

## What this report does not do

Does not modify `backend/app/` in any way. Does not add or alter any schema, model, or migration. Does not modify the system prompt in `conversation_ai.py` — the evaluation used a temporary, disposable copy of the *proposed* prompt (plan §5.4), never the production one. Does not commit or push. The evaluation script and raw per-case results live only in this session's scratchpad directory, outside the project's git repository.
