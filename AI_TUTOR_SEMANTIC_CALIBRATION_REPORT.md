# AI Tutor Semantic Calibration — Real-Provider Test Report

Status: **Calibration test complete. 21/21 real API calls executed exactly as pre-committed in `AI_TUTOR_SEMANTIC_CALIBRATION_PLAN.md` §7. No production code, migrations, commits, or pushes were made.** The revised schema, prompt, and deterministic guards from that plan were implemented only in a temporary, disposable script outside `backend/app/`, never in the application.

**Headline: the calibration test FAILED.** Verdict **B**. Full detail below, including a real, honestly-reported flaw the test run itself exposed in one of the deterministic guards (§7) — reported separately, per instruction, not used to relax the pre-committed criteria.

---

## 1. Exact provider/model

Groq, `openai/gpt-oss-120b` — identical to the real-provider evaluation and the original 48-case run. Not substituted.

## 2. Exact number of API calls used

**21 of 21 pre-committed calls**, exactly matching the budget authorized: 4 high-risk cases (C1, C7, C8, C12) × 3 independent runs each = 12, plus 9 standard-risk cases × 1 run each = 9. `12 + 9 = 21`. No call was skipped, no call was added.

**Run independence, confirmed by construction**: every run — including all 3 repeats of each high-risk case — was built fresh from that case's static definition (system prompt + original conversation history + the case's learner answer) and sent as an independent request. No run's response was fed into another run's input at any point; the script that produced these calls never accumulates state between iterations. Run numbers were recorded and are reported separately for every repeated case (§4).

## 3-4. Every calibration case and every repeated run, separately

| Case | Run | Risk | Answer | Expected (key fields) |
|---|---|---|---|---|
| C1 | 1/2/3 | HIGH | "no i didnt like wearing new shoes" | meaning=CHANGED, `learner_intent_known=false`, `clarification_required=true`, `corrected_sentence=null` |
| C2 | 1/1 | standard | "I need a new jaket" | meaning=PRESERVED, grammar=MINOR (1 issue) |
| C3 | 1/1 | standard | "yes i want a coffee" | meaning=PRESERVED, grammar=MINOR (2 issues) |
| C4 | 1/1 | standard | "i dont like wearing red shoes" | meaning=PRESERVED, completeness=PARTIAL |
| C5 | 1/1 | standard | "My brother is a doctor." | relevance=NONE, meaning=PRESERVED |
| C6 | 1/1 | standard | "Can't complain!" | grammar=CORRECT, naturalness=NATURAL, 0 issues |
| C7 | 1/2/3 | HIGH | "the other one" | meaning=UNCLEAR, `learner_intent_known=false`, `clarification_required=true`, `corrected_sentence=null` |
| C8 | 1/2/3 | HIGH | "no i dont like eating oranges" | meaning=CHANGED, `learner_intent_known=false`, `clarification_required=true`, `corrected_sentence=null` |
| C9 | 1/1 | standard | "i think i want the soup and i will get water too" | meaning=PRESERVED, 3 issues (3× capitalization) |
| C10 | 1/1 | standard | "i want a jaket thats waterproof and i dont like the blue ones" | meaning=PRESERVED, 5 issues |
| C11 | 1/1 | standard | "No, I'm an only child." | informational (contradiction), not scored |
| C12 | 1/2/3 | HIGH | "the first one" | meaning=UNCLEAR, `learner_intent_known=false`, `clarification_required=true`, `corrected_sentence=null` |
| C13 | 1/1 | standard | "The weather is nice today" | relevance=NONE, meaning=PRESERVED |

## 5-6. Raw and normalized results — the 4 high-risk cases, every run

**C1 — Red/new shoes (canonical, the mandatory worked example embedded in the prompt)**

| Run | meaning | `learner_intent_known` (raw→final) | `clarification_required` | `corrected_sentence` | Issues (count) | Zero-tolerance verdict |
|---|---|---|---|---|---|---|
| 1 | CHANGED | false → false | true | **null** | 3 (no→No, i→I, didnt→didn't) | **PASS** |
| 2 | CHANGED | false → false | true | **null** | 3 (same 3, minor wording variance) | **PASS** |
| 3 | CHANGED | false → false | true | **null** | 4 (same 3 + a period-punctuation issue) | **PASS** |

**C1: 3/3 PASS.** Every run correctly declined to guess between "red" and "new," asked a clarifying question, and produced no `corrected_sentence`.

**C7 — Ambiguous intent ("the other one," non-canonical wording of the same category as C1)**

| Run | meaning | `learner_intent_known` (raw→final) | `clarification_required` | `corrected_sentence` | Zero-tolerance verdict |
|---|---|---|---|---|---|
| 1 | **PRESERVED** (raw) | false → **null** (§7 guard gap, see below) | true | **"The other one."** — NOT null | **FAIL** (2 violations) |
| 2 | **PRESERVED** | true → null | **false** | "The other one" — NOT null | **FAIL** (all 3 fields wrong) |
| 3 | **UNCLEAR** | false → **false** | **true** | **null** | **PASS** |

**C7: 1/3 PASS, 2/3 FAIL.**

**C8 — Meaningful word substitution, non-canonical ("apples" → "oranges")**

| Run | meaning | `learner_intent_known` (raw→final) | `clarification_required` | `corrected_sentence` | Zero-tolerance verdict |
|---|---|---|---|---|---|
| 1 | **PRESERVED** | true → null | **false** | "No, I don't like eating oranges." — NOT null | **FAIL** |
| 2 | **PRESERVED** | true → null | **false** | "No, I don't like eating oranges." — NOT null | **FAIL** |
| 3 | CHANGED | false → false | true | **null** | **PASS** |

**C8: 1/3 PASS, 2/3 FAIL.**

**C12 — Clarification definitely required ("the first one," referring to "chicken or fish")**

| Run | meaning | `learner_intent_known` (raw→final) | `clarification_required` | `corrected_sentence` | Zero-tolerance verdict | `overall_status` |
|---|---|---|---|---|---|---|
| 1 | PRESERVED | true → null | **false** | null (coincidental) | **FAIL** | **CORRECT** — treated as a fully clean, unambiguous answer |
| 2 | PRESERVED | true → null | **false** | "The first one." — NOT null | **FAIL** | MINOR_ISSUES |
| 3 | PRESERVED | true → null | **false** | "The first one" — NOT null | **FAIL** | MINOR_ISSUES |

**C12: 0/3 PASS, 3/3 FAIL — the only case to fail every single run, with no variance.**

## 7. Deterministic guard actions — and a genuine flaw this run exposed

Across all 21 calls, exactly **one** guard fired: C9's dedupe guard dropped a second, identical `(CAPITALIZATION, "i")` entry. No span-existence violations, no mechanical-plausibility rejections, no severity-based `grammar_status` upgrades occurred in this run.

**A real flaw in the guard implementation, found by this test, reported separately per instruction — not used to relax any pass criterion:**

C7's run 1 raw model output was internally self-contradictory: `meaning_status: PRESERVED`, `learner_intent_known: false`, `clarification_required: true`, `corrected_sentence: "The other one."` — the model flagged low confidence and requested clarification via two of the three signals, while its `meaning_status` field (unrelated to those two) still read `PRESERVED`, and it still produced a `corrected_sentence`.

The deterministic guard, exactly as specified in `AI_TUTOR_SEMANTIC_CALIBRATION_PLAN.md` §4, resolves `learner_intent_known` from `meaning_status` **first** (`if meaning_status == "PRESERVED": return None`), before ever looking at the raw model's own `learner_intent_known` flag. Because `meaning_status` read `PRESERVED` here, the guard forced `learner_intent_known` to `null` — **silently discarding the model's own explicit `false` signal** — and `final_corrected_sentence` (which only nulls when `learner_intent_known is False`, not more broadly when `clarification_required is True`) then let `"The other one."` pass straight through, even though `clarification_required` was independently `true`.

**This is exactly the gap the plan's §4 forcing rules were supposed to close, and it did not close it in this specific case.** Two design mistakes are exposed, not one:
1. `final_learner_intent_known`'s priority order lets a `meaning_status=PRESERVED` report override an explicit raw `learner_intent_known=false` signal, rather than treating an explicit `false` as authoritative regardless of what `meaning_status` separately says.
2. `final_corrected_sentence` is keyed only off `learner_intent_known is False`, not off the broader `clarification_required is True` condition that the authorization for this test explicitly named as the required invariant ("`corrected_sentence` is null whenever clarification is required").

**This is reported as a genuine flaw in the test specification (the deterministic guard design), not a relaxation of the pass criteria.** The pass criteria were applied exactly as written against the actual, flawed behavior that actually occurred — C7 run 1 is graded **FAIL** on the letter of the criteria, and this paragraph explains *why* the guard didn't catch it, for the next design iteration.

## 8. Results by failure mode

Of the 7 failing high-risk runs (C7 runs 1-2, C8 runs 1-2, C12 runs 1-3), **all 7 are Mode 2 failures (ambiguity not detected at all) — zero are pure Mode 1 failures (detected but mis-handled).** Every failing run reported `meaning_status=PRESERVED`, the same field value used for a genuinely unambiguous answer — the model did not register that anything was uncertain in its headline judgment, in any of the 7 failing runs.

This is a materially different (and more concerning) shape than the original 48-case run's flagship failure, where `meaning_status=CHANGED` was correctly detected and only the confidence rating was wrong (Mode 1). **The semantic non-invention rule and its mandatory worked example fixed the exact case it was written against (C1: 3/3) but did not generalize to any of the three deliberately non-canonical high-risk variants (C7, C8, C12), which together failed 7 of 9 runs — a strong, direct signal of overfitting to the literal embedded example rather than the underlying principle.**

Notably: in both C8 failing runs, the free-text `context_feedback` field *did* correctly notice the substitution ("you mentioned oranges instead of apples," "You answered about oranges instead of the asked apples") even though the structured `meaning_status` field did not reflect it. The model's prose reasoning caught what its structured output did not propagate — a gap between what the model "knows" in free text and what it commits to in the schema.

## 9. One-span-one-issue results

**Real, partial improvement, with one specific sub-problem unresolved.** C1 and C3 (and the standard-tier cases generally) now correctly separate multiple *different* error spans into distinct `issues[]` entries — a direct, measurable improvement over the original 48-case run's frequent bundling (e.g. C3's "yes i want a coffee" produced 2 clean, separate entries here, versus the original run's 1 bundled entry for the identical input).

**But repeated occurrences of the *same* word are still under-caught**, exactly as in the original run:
- C9 ("i think i want the soup and i will get water too," 3 lowercase "i" occurrences expected): the model's raw output contained only 2 `(CAPITALIZATION, "i")` entries — 2 of 3 occurrences, and both were *identical* (no positional distinction), so the deterministic dedupe guard collapsed them to 1, since the schema gives no way to tell "the same span independently caught twice" from "an accidental duplicate." **Final: 1 of 3 expected spans represented.**
- C10 (2 lowercase "i" occurrences expected, matching the original run's case 43): only 1 `(CAPITALIZATION, "i")` entry, same as the original run's identical undercount.

Rule 18 (added for this test) measurably fixed cross-type bundling but did not fix same-word-repeated-occurrence undercounting, and exposed a real schema limitation: `issues[].original` alone cannot represent "this is a second, distinct occurrence of the same mistake," so even a future prompt fix that gets the model to correctly count repeats would need a schema change (e.g. an occurrence index) to be verifiable, not just a prompt change.

## 10. The red/new shoes case, in full detail

Already presented in full in §5-6 above (C1). Restated as the single positive headline result of this test: **3 of 3 independent real calls to the exact canonical case correctly set `learner_intent_known=false`, `clarification_required=true`, and `corrected_sentence=null`, and none silently substituted "new" for "red" anywhere.** This is a genuine, reproducible fix for the literal case that started this entire review process. It is also, per §8, the *only* case in this test that reliably worked — every structurally-similar-but-differently-worded case failed most of the time.

## 11. Instability across repeated calls

Two distinct shapes of instability were observed, and they are not the same finding:

- **C7 and C8: genuinely unstable (mixed results across identical-input runs).** C7 produced 3 different `overall_status` values across 3 runs (`UNCLEAR`, `PARTIAL_ANSWER`, `UNCLEAR`); C8 also produced 3 different values (`MINOR_ISSUES`, `PARTIAL_ANSWER`, `UNCLEAR`). A single sample of either case, taken at random, has roughly a 1-in-3 chance of looking safe and a 2-in-3 chance of looking unsafe, based on this small sample — exactly the coin-flip-like unreliability the plan's repeated-run requirement (audit §4) was designed to surface, and did.
- **C12: not unstable — consistently, unanimously wrong.** All 3 runs failed the same way (`meaning_status=PRESERVED`, no clarification flagged). This is a more concerning finding than C7/C8's variance: it suggests "the first one," referring to two named alternatives, is a reliable blind spot for this prompt, not a sampling artifact that might resolve favorably on a lucky call.

## 12. Malformed or invalid responses

**Zero.** All 21 calls returned valid JSON that validated against the revised `RawTutorTurn` schema on the first attempt. No retries were needed for malformed content; all retries encountered (visible in the run log) were Groq rate-limit (`429`) retries, handled automatically by waiting the exact duration Groq specified, consistent with the original 48-case run's infrastructure behavior.

## 13. Latency/cost observations

| Metric | Value |
|---|---|
| Total real API calls | 21 / 21 successful |
| Malformed/schema-invalid responses | 0 |
| Prompt tokens | sum 42,249, avg 2012/call (higher than the original 48-case run's ~1447 avg — the revised prompt, with rules 17-18 and the embedded worked example, is measurably longer) |
| Completion tokens | sum 15,222, avg 725/call, min 236, max 1174 |
| Total tokens (21 calls) | 57,471 |
| Latency (model only) | avg 4226ms, min 2063ms, max 12530ms — noticeably higher and more variable than the original 48-case run's avg 1963ms, consistent with the longer prompt and, on the slowest calls, more internal reasoning before the final JSON |
| Wall-clock time | 424.6s (~7 minutes), mostly rate-limit wait time as before |
| Dollar cost | Not stated, same discipline as the prior reports — exact token counts given, no fabricated dollar figure |

## 14. Confirmation that pass criteria were not changed

**Confirmed.** The zero-tolerance tier (100% pass required on C1/C7/C8/C12, every run, no partial credit), the standard tier (adjacent-tolerance grading, full-enumeration requirement for C9/C10), and the overall gate (both tiers must pass to authorize the 48-case re-run) are graded here exactly as written in `AI_TUTOR_SEMANTIC_CALIBRATION_PLAN.md` §7.3, decided *before* this run was executed. The one flaw this run exposed (§7) is reported as a design finding, not applied as a retroactive excuse for any specific run's grade — C7 run 1 and every other failing run above is marked **FAIL** on the actual criteria as originally written, without adjustment.

**Standard tier, for completeness (not dispositive given §15's zero-tolerance result):** C2, C3, C4, C5, C13 passed cleanly; C6 showed a mild, tolerance-passing regression (an idiomatic fragment that passed cleanly in the original 48-case run now receives a spurious "missing subject" issue); C9 and C10 both fail the full-issue-enumeration requirement (§9). 6 of 8 scored standard cases pass cleanly (75%), below the plan's ≥80% bar — itself enough to fail the standard tier independent of the zero-tolerance result.

**One genuinely positive, unscored, single-sample finding worth noting honestly**: C11 (the contradiction case) was *noticed* this run — the reply explicitly asked the learner to reconcile "two brothers" with "only child." This is 1-for-1 versus the original 48-case run's 0-for-3, but it is a single sample and is not treated as a trend.

## 15. Final verdict

## **B. CALIBRATION FAILED — revise design before full evaluation.**

The zero-tolerance tier is the dispositive result, exactly as the plan's own pre-committed gate requires: **5 of 12 high-risk runs passed (41.7%)**, far below the required 100%. Three of the four high-risk cases (C7, C8, C12) each failed at least one run; C12 failed all three. Every failure was Mode 2 (the ambiguity was never registered in the model's headline `meaning_status` judgment at all), concentrated specifically in the three cases deliberately built to be *structurally* similar to the canonical red/new-shoes case but *worded* differently — exactly the generalization test this calibration set was designed to run, and it found that generalization did not happen.

**This is not a reason to abandon the underlying schema redesign.** C1 — the literal case the entire review process started from — passed 3 for 3, cleanly, with no instability. The `learner_intent_known`/`clarification_required` boolean primitive worked exactly as designed whenever the model's own `meaning_status` judgment correctly flagged something as off. The problem this run surfaces is narrower and more specific than "the schema doesn't work": **the model's ambiguity-*detection* step (not the confidence/handling step downstream of it) does not reliably fire outside the one worked example given to it**, and a real, now-understood implementation gap in the deterministic guard (§7) needs a design fix (make an explicit raw `learner_intent_known=false` signal authoritative regardless of `meaning_status`, and key `corrected_sentence` nullification off `clarification_required` directly, not only off `learner_intent_known`) before the guard can be trusted to catch what the prompt still occasionally misses.

**Per the explicit constraint on this task: this verdict does not claim READY FOR IMPLEMENTATION, even partially.** A failed calibration test does not authorize the full 48-case re-run. The next step is a further design iteration — informed directly by §7's guard-logic finding and §8's overfitting finding — followed by another calibration test (not necessarily the full 48-case dataset) before that larger, more expensive run is spent again.

---

## What this report does not do

Does not modify `backend/app/` in any way. Does not add or alter any schema, model, or migration. Does not modify the production system prompt in `conversation_ai.py`. Does not commit or push. Does not run the full 48-case dataset — that remains gated behind a passing calibration result, which this run did not produce. The calibration script and raw results live only in this session's scratchpad directory, outside the project's git repository.
