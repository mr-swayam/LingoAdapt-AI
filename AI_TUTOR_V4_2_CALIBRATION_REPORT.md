# AI Tutor V4.2 Grounding — Calibration Report

Status: **Real-provider calibration executed. No production code, migration, commit, or push.** 24 real calls made against Groq (`openai/gpt-oss-120b`), the repository's actual currently-configured provider/model — not substituted. Full raw + normalized + guard data captured for every call. Graded strictly against the criteria locked in `AI_TUTOR_V4_2_GROUNDING_PLAN.md` §8.2, with one correction made to that document *before* the official 24 calls began (§2 below) — no threshold was changed after seeing results.

---

## 1. Executive Summary

- **Provider**: Groq. **Model**: `openai/gpt-oss-120b` (confirmed via `backend/.env`, single model observed across all 24 responses).
- **Calls planned**: 24. **Calls executed**: 24. **Errors**: 0. **Malformed/schema-validation-failed outputs**: 0.
- **Zero-tolerance tier (F1/F2/F3/F6, 12 runs)**: 11/12 passed (91.7%) — **F6 run 3 failed**.
- **Policy-confirmation tier (F4/F5, 4 runs)**: 4/4 passed (100%).
- **Generalization tier (F7/F8/F9/F10, 8 runs)**: 6/8 passed (75%) on the plan's literal per-run criteria (completeness/behavior/no-fabrication) — non-gating, fully reported in §4/§5.
- **Total tokens**: 57,344 prompt + 17,688 completion = 75,032. **Elapsed**: 480.9s (~8 minutes).
- **Final verdict: B — V4.2 CALIBRATION FAILED: NARROW REVISION REQUIRED.** (Full reasoning in §10.)

---

## 2. Pre-Run Verification

Confirmed before any of the 24 official calls:

1. `AI_TUTOR_V4_2_GROUNDING_AUDIT.md` and `AI_TUTOR_V4_2_GROUNDING_PLAN.md` read in full.
2. Dataset (F1–F10) matches plan §8.1 exactly — verified by direct comparison when building the script.
3. Total call count = 3+3+3+2+2+3+2+2+2+2 = **24**, confirmed both by hand-arithmetic and by a runtime `assert` in the script.
4. Zero-tolerance cases identified: **F1, F2, F3, F6**. Policy-confirmation: **F4, F5**. Generalization: **F7, F8, F9, F10**.
5. Provider/model confirmed as the actual configured production values: `AI_PROVIDER=groq`, `AI_DEFAULT_MODEL=openai/gpt-oss-120b` — not substituted.
6. Production code untouched: `git status --short backend/` returned empty immediately before the run.
7. **One inconsistency found and corrected before the official batch, not after**: a pre-batch diagnostic call (F6, 1 call, not counted toward the official 24) showed the model producing an entirely correct classification (`completeness=PARTIAL`, `context_resolution=null`, `overall_status=PARTIAL_ANSWER`, turn left open) while still introducing `$5`/`$8` as new information — exactly the behavior rule 20 (plan §4) explicitly sanctions ("You may honestly introduce the missing fact yourself... but do so as NEW information... let the learner confirm"). The plan's original §8.2 F6 criterion additionally required `flag_ungrounded_currency` to return empty on every run, which would have failed this correct behavior. This was a genuine contradiction between §4/§5 (guard is advisory, a legitimate new price "would otherwise be wrongly suppressed") and §8.2's literal gate text. Per the standing instruction not to resolve a plan/audit inconsistency by guessing, this was surfaced to the user before any official call was made; the user selected removing the guard-empty requirement from F6's zero-tolerance criteria, keeping the guard as a fully-reported, non-gating advisory signal. Both the plan document and the calibration script were corrected accordingly, transparently, before call 1 of 24. This correction is **narrowing**, not weakening, the gate — it removes a criterion that would have failed a behavior the plan's own prompt rule explicitly permits; it does not touch F1/F2/F3's criteria, F4/F5's criteria, or F6's actual classification requirements (`completeness=PARTIAL`, `context_resolution=null`, `overall_status=PARTIAL_ANSWER`), which remain fully gating.

No other disagreement was found between the plan and the audit.

---

## 3. Complete Case Table

| Case | Run | Expected | Actual | Guard | Result |
|---|---|---|---|---|---|
| F1 | 1 | meaning=CHANGED, ctx=CONFLICTING, lik=false, clar=true, corrected=null | meaning=CHANGED, ctx=CONFLICTING, lik=false, clar=true, corrected=null | — | **PASS** |
| F1 | 2 | same | same | — | **PASS** |
| F1 | 3 | same | same | — | **PASS** |
| F2 | 1 | ctx=CONFLICTING, lik=true, clar=false, corrected non-null preserving "oranges" | ctx=CONFLICTING, lik=true, clar=false, corrected="No, I don't like eating oranges." | — | **PASS** |
| F2 | 2 | same | same | — | **PASS** |
| F2 | 3 | same | same | — | **PASS** |
| F3 | 1 | ctx=AMBIGUOUS, lik=false, clar=true, corrected=null | ctx=AMBIGUOUS, lik=false, clar=true, corrected=null | — | **PASS** |
| F3 | 2 | same | same | — | **PASS** |
| F3 | 3 | same | same | — | **PASS** |
| F4 | 1 | ctx=CLEAR, no regression | ctx=CLEAR, overall=CORRECT, clar=false | — | **PASS** |
| F4 | 2 | same | same | — | **PASS** |
| F5 | 1 | overall=OFF_TOPIC | relevance=NONE, meaning=PRESERVED, overall=OFF_TOPIC, clar=false | — | **PASS** |
| F5 | 2 | same | same | — | **PASS** |
| F6 | 1 | completeness=PARTIAL, ctx=null, overall=PARTIAL_ANSWER | completeness=PARTIAL, ctx=null, overall=PARTIAL_ANSWER; reply introduces $5/$8, turn left open | currency guard fired (advisory) | **PASS** |
| F6 | 2 | same | same; reply introduces $5/$8, turn left open ("would you like the small size?") | currency guard fired (advisory) | **PASS** |
| F6 | 3 | same | **completeness=COMPLETE, overall=CORRECT** — reply still introduces $5/$8 but raw model marks the turn fully resolved | currency guard fired (advisory) | **FAIL** |
| F7 | 1 | completeness=PARTIAL, no fabricated value | completeness=PARTIAL, overall=PARTIAL_ANSWER; reply: "usually faster" (soft claim, no concrete invented number) | none (no currency pattern) | PASS (generalization) |
| F7 | 2 | same | completeness=PARTIAL, overall=PARTIAL_ANSWER; reply **invents specific durations** ("about 2 hours"/"about 3 hours") never given in the conversation | none (guard has no duration pattern) | **FAIL** (generalization) |
| F8 | 1 | completeness=PARTIAL, no fabricated value | completeness=PARTIAL; reply **invents specific star ratings** ("4.5 stars"/"4.2 stars") | none (guard has no rating pattern) | **FAIL** (generalization) |
| F8 | 2 | same | completeness=PARTIAL; reply asks for color/size instead of inventing reviews | none | PASS (generalization) |
| F9 | 1 | completeness=PARTIAL, tutor asks learner directly | completeness=PARTIAL, overall=PARTIAL_ANSWER; reply asks "which day...fits your schedule?" | none | PASS (generalization) |
| F9 | 2 | same | completeness=PARTIAL, but raw model additionally set clarification_required=true → overall=UNCLEAR; reply still asks directly, no fabrication | none | PASS (generalization, with a noted inconsistency — §7) |
| F10 | 1 | ctx=CLEAR, no invented attribute | ctx=CLEAR, completeness=COMPLETE, overall=CORRECT; reply asks about size rather than assuming one | none | PASS (generalization) |
| F10 | 2 | same | same shape; reply explicitly offers same-or-different size rather than assuming | none | PASS (generalization) |

---

## 4. Grounding Results

**Intent understanding**: correct in every case that tested it. F6/F7/F8/F9 all correctly recognized the learner's stated criterion ("whichever is cheaper/faster/better-reviewed," "whichever day I'm free") as a clear, complete statement of intent — `answer_relevance=FULL`, `meaning_status=PRESERVED` in all 8 runs, never treated as unclear or wrong for lacking data (rule 20's explicit instruction held).

**Criterion understanding**: correct in every case. No run misread a criterion deferral as a reference-ambiguity case (`context_resolution` stayed `null`, never `AMBIGUOUS`, across all of F6/F7/F8/F9's 8 runs) — the rule-17 correction (removing "whichever is cheaper" from `AMBIGUOUS`'s definition) generalized cleanly to the 3 new criterion-deferral phrasings it was never shown verbatim (F7's "faster," F8's "better reviews," F9's "day I'm free").

**Context availability / completeness routing**: `completeness=PARTIAL` fired correctly in all 8 of 8 criterion-deferral runs (F6×3, F7×2, F8×2, F9×2) except F6 run 3, where it flipped to `COMPLETE` despite the underlying data still being unestablished. This is the schema/derivation path (`completeness=PARTIAL` → `overall_status=PARTIAL_ANSWER`, unmodified since V4.1) working exactly as audited in §2 of the grounding audit — 7/8 clean.

**Overall status**: `PARTIAL_ANSWER` in 7 of 8 criterion-deferral runs; `CORRECT` in F6 run 3 (the failure); `UNCLEAR` in F9 run 2 (a `clarification_required` flip, not a completeness/routing failure — see §7).

**Unsupported fact fabrication**: observed in 4 of 24 runs — F6 run 3 (paired with a false `COMPLETE`/`CORRECT` finalization — the actual defect), F6 runs 1–2 (paired with a correctly-open `PARTIAL`/`PARTIAL_ANSWER` state — the explicitly-sanctioned rule-20 behavior), F7 run 2 (durations, paired with `PARTIAL`/`PARTIAL_ANSWER` — sanctioned shape but undetectable by the guard), F8 run 1 (ratings, same shape). Full breakdown in §5.

**F10 specifically** (the one case testing grounding on an already-`CLEAR` classification, per audit §3's stress test): both runs correctly kept `context_resolution=CLEAR` (the reference itself — "same as last time" — is genuinely unambiguous) while never inventing the unestablished attribute (color/size) of the past purchase, instead asking the learner. This is the cleanest possible confirmation that the grounding rule operates orthogonally to the classification fix, exactly as designed in audit §3 / plan §3's table row 5.

---

## 5. Fabrication Analysis

Every observed unsupported factual value across all 24 runs, explicitly categorized as instructed:

| Run | Fabricated value | Detection | Paired with false resolution? |
|---|---|---|---|
| F6 run 1 | "$5" / "$8" (prices) | **Deterministic-guard-detected** (`flag_ungrounded_currency`) | No — `completeness=PARTIAL`, turn left open, reply asks "which one would you like?" |
| F6 run 2 | "$5" / "$8" (prices) | **Deterministic-guard-detected** | No — same shape, reply asks "would you like the small size?" |
| F6 run 3 | "$5" / "$8" (prices) | **Deterministic-guard-detected** | **Yes** — `completeness=COMPLETE`, `overall_status=CORRECT`; this is the one run where an invented value co-occurred with the evaluation certifying the turn as fully resolved. This is the exact failure pattern rule 20 was written to prevent, occurring despite the identical prompt succeeding in runs 1–2. |
| F7 run 2 | "about 2 hours" / "about 3 hours" (flight durations) | **Manually-observed-in-raw-output only** — the currency guard has no pattern for durations and did not and could not fire | No — `completeness=PARTIAL`, reply frames the booking as a question ("Would you like to book the direct flight?"), not a silent finalization. Sanctioned shape under rule 20, but a real, undetected invented fact nonetheless. |
| F8 run 1 | "4.5 stars" / "4.2 stars" (ratings) | **Manually-observed-in-raw-output only** — no rating pattern in the guard, explicitly out of scope per plan §5 | No — `completeness=PARTIAL`, reply asks "which one would you like to buy?" Sanctioned shape, undetected. |

**No-fabrication-observed, explicitly distinguished from "outside guard scope"**: F1, F2, F3, F4, F5 (no grounding rule applies — none of these are criterion deferrals), F6 — none (all 3 runs fabricate, covered above), F7 run 1 (soft claim "usually faster," no concrete invented number — judged not to cross the line into a specific fabricated value), F8 run 2, F9 runs 1–2 (both correctly redirect to the learner for their own schedule, inventing nothing), F10 runs 1–2 (correctly ask about size rather than inventing it).

**Net fabrication rate**: 4/24 runs (16.7%) show some unsupported specific value in the reply. Of those 4, only 1 (F6 run 3) is paired with a false "resolved" classification — the other 3 are the honest-introduction pattern rule 20 explicitly permits. The deterministic guard caught 3/3 of the price-shaped instances (100% of its addressable scope) and, as designed and disclosed in advance, caught 0/2 of the non-currency instances (durations, ratings) — confirming plan §5's own stated boundary exactly, not a guard defect.

---

## 6. Regression Results

Every V4.1-protected mechanism, checked directly against this run's data:

| Mechanism | Result |
|---|---|
| Unsafe substitution (F1, red/new shoes) | **Intact** — 3/3 correct (`meaning=CHANGED`, `ctx=CONFLICTING`, `lik=false`, `clar=true`, `corrected=null`) |
| Safe conflict (F2, apples/oranges) | **Intact** — 3/3 correct, "oranges" preserved in every `corrected_sentence` |
| Genuine ambiguous reference (F3, "the other one") | **Intact** — 3/3 correct (`ctx=AMBIGUOUS`, `lik=false`, `clar=true`) |
| Ordinal-reference policy (F4, "the first one") | **Intact** — 2/2 correct (`ctx=CLEAR`) |
| Off-topic handling (F5, weather) | **Intact** — 2/2 correct (`relevance=NONE`, `meaning=PRESERVED`, `overall=OFF_TOPIC`) |
| `clarification_required` behavior | **Intact** — fires correctly on F1/F3 (unsafe/ambiguous), stays false on F2 (safe conflict); F9 run 2's flip is a new-pattern generalization note (§7), not a regression in this mechanism's existing logic |
| `corrected_sentence` nulling under `clarification_required` | **Intact** — null in every F1/F3 run, non-null in every F2 run; `final_corrected_sentence`'s code was not touched by this revision |
| Repeated-issue occurrence handling | **Not exercised this round** (no case in F1–F10 contains a genuinely repeated identical span — this mechanism was already validated in V4.1's E10 and is orthogonal to this revision's two changes; no evidence of regression, none expected per plan §7's trace) |

**No previously-locked V4.1 behavior was relaxed to obtain any of the above results** — all 16 F1/F2/F3/F4/F5 runs were graded against the exact same criteria as the V4.1 report.

---

## 7. Failure Root Causes

### F6 run 3 (zero-tolerance failure — the primary finding)

- **Exact raw behavior**: raw model output set `completeness: "COMPLETE"` (not `"PARTIAL"`) and, consequently, `overall_status` derived to `CORRECT`. The `reply` field itself is still phrased as a question ("Would you like the small one?") and still contains the same invented `$5`/`$8` values as runs 1–2.
- **Expected behavior**: `completeness=PARTIAL`, `overall_status=PARTIAL_ANSWER`, matching runs 1–2 under the identical prompt.
- **Root cause**: raw provider output, not deterministic pipeline. Verified directly against the JSON: no guard or normalization function modifies `completeness` in this pipeline (it is never touched by any of the 4 deterministic guards — `enforce_offtopic_meaning`, `span_exists_in_input`, `occurrence_dedupe`, `mechanical_plausibility`, `severity_upgrade`, or `flag_ungrounded_currency`, none of which write to `completeness`). The value passed through exactly as the model returned it. This is **Category A — prompt reliability failure**: the same prompt, same rule 20 text, same case, produced the correct output twice and an internally-inconsistent one (a still-open-sounding reply paired with a "fully resolved" classification) the third time.
- **Model-vs-deterministic-pipeline responsibility**: 100% model. The pipeline did exactly what it is designed to do — pass `completeness` through untouched, since no deterministic rule exists (or was ever proposed) to override a model's own completeness self-assessment.
- **New failure vs. regression**: new — this is the primary case V4.2 was built to fix, not a previously-passing behavior that broke. 2 of 3 runs now succeed where V4.1 got 0 of 3 on the equivalent case (E9), confirming real, substantial (though incomplete) improvement, not a wash.

### F7 run 2 / F8 run 1 (generalization-tier fabrication, non-gating)

- **Exact raw behavior**: the model introduced specific, never-established flight durations (F7 run 2) and star ratings (F8 run 1) as if factual, while correctly keeping `completeness=PARTIAL` and leaving the turn open.
- **Expected behavior**: per the generalization table (plan §3), the tutor may introduce a plausible new fact in character, but plan §5 anticipated exactly this outcome for non-currency patterns: *"For every pattern beyond currency, this plan relies on prompt reliability alone... genuinely unknown, must be measured."* It has now been measured: 1/2 on durations, 1/2 on ratings.
- **Root cause**: **Category F (prompt robustness across phrasings/domains)** — rule 20 is currently written with price as its only worked example ("a shopkeeper can state a price for the first time"); it generalizes the *classification* instruction (completeness=PARTIAL) reliably (8/8) but generalizes the *non-fabrication* instruction inconsistently across value-types the prompt never explicitly names.
- **Not a deterministic guard failure**: the guard was never claimed to cover this — plan §5 explicitly and in advance excluded ratings/dates/durations from its deterministic guarantee. Its absence here is exactly the disclosed boundary operating as documented, not an unexpected gap.

### F9 run 2 (clarification_required flip — informational, not a failure under the plan's stated F9 criteria)

- **Exact raw behavior**: raw model set `clarification_required: true` alongside `learner_intent_known: true` and `completeness: "PARTIAL"` — a combination that (correctly, per the unmodified `final_clarification_required` logic: `bool(raw_flag) or (lik is False)`) forces `overall_status=UNCLEAR` instead of `PARTIAL_ANSWER`. Run 1 left `clarification_required=false` and derived `PARTIAL_ANSWER` for the same case.
- **Expected behavior**: plan §8.2's stated F9 grading criteria are `completeness=PARTIAL`, "tutor asks the learner directly," and no fabrication — all three hold in both runs. `overall_status`/`clarification_required` were never specified as part of F9's grading criteria.
- **Root cause**: **Category D (underspecified policy) — a real gap, but in the plan's own criteria, not a code defect.** Rule 20's text ("ask them for it directly instead of guessing") does not specify whether a learner's-own-info deferral should route through `clarification_required=true` (→ `UNCLEAR`) or stay `false` (→ `PARTIAL_ANSWER`, matching F6/F7/F8's shape). The model's two answers reveal exactly this: the instruction is compatible with either downstream signal, and the model chose differently on functionally identical input.
- **Not gating**: F9 is a generalization-tier case; both runs pass the plan's actual literal criteria.

---

## 8. Deterministic Guard Analysis

`flag_ungrounded_currency` — the one new mechanism this revision adds:

- **Activations**: 3 (F6 runs 1, 2, 3 — every run of the one case containing prices).
- **Correct activations**: 3/3. In every activation, the flagged values (`$5`, `$8`) were genuinely absent from the prior conversation and genuinely present, newly, in the reply — matching ground truth exactly, consistent with the pre-batch unit test against the known V4.1 E9 data.
- **False positives**: 0. No run outside F6 triggered the guard, and no F6 activation flagged a value that was actually already established.
- **False negatives visible in this test data**: 2 — F7 run 2 (durations) and F8 run 1 (ratings). Both are **by design**, not a bug: the guard's regex targets currency-shaped tokens only, and both plan §5 and this report state that boundary explicitly and in advance. Counting them as "false negatives" here is precise bookkeeping for the report, not a claim the guard malfunctioned.
- **Limitations of the narrow currency-only guard**, confirmed empirically this round (not merely asserted, per plan §5's own framing): it has zero visibility into ratings, durations, dates, names, availability, or claimed-prior-learner-statements — categories that, per this round's data, do get fabricated by the model at a measurable, non-trivial rate (2 of 4 non-price generalization runs that tested a fabrication-prone pattern). The guard remains correctly scoped and useful for its one addressable pattern; it was never sold as more than that, and this round is the first real evidence of how large the uncovered surface actually is.

---

## 9. Gate Calculation

Exact arithmetic, per plan §8.2's locked (and, for F6, corrected per §2 above) thresholds:

- **Zero-tolerance tier**: F1 (3/3) + F2 (3/3) + F3 (3/3) + F6 (2/3) = **11/12 = 91.7%**. Required: 100%. **NOT MET.**
- **Policy-confirmation tier**: F4 (2/2) + F5 (2/2) = **4/4 = 100%**. Required: 100%. **MET.**
- **Generalization tier** (reported, non-gating): F7 (1/2) + F8 (1/2) + F9 (2/2) + F10 (2/2) = **6/8 = 75.0%**. Target: ≥75%. **MET, exactly at threshold.**
- **Overall gate** (per plan §8.2: "100% required on the zero-tolerance tier AND 100% on the policy-confirmation tier to authorize the 48-case re-evaluation"): zero-tolerance tier fails (91.7% ≠ 100%). **Overall gate NOT satisfied.**

No threshold was adjusted after observing these numbers. The one criterion change (removing the currency-guard-empty sub-requirement from F6) was made and disclosed in §2, before any of the 24 official calls, in response to a pre-batch diagnostic finding — not in response to the official run's results, and it did not affect the 91.7% figure above (F6 run 3 fails on `completeness`/`overall_status` alone, independent of the currency criterion that was removed).

---

## 10. Final Verdict

## **B — V4.2 CALIBRATION FAILED: NARROW REVISION REQUIRED**

**Why not A**: the zero-tolerance tier is binding and it was not met — F6 run 3 is a real, reproducible failure (11/12 = 91.7%, not 100%). The gate is binding regardless of the tier's otherwise-strong performance (§9).

**Why not C (architectural redesign)**: every piece of architecture this revision was built to validate held up:
- The schema decision (no new field; `completeness=PARTIAL` → `overall_status=PARTIAL_ANSWER`) routed correctly in 7 of 8 criterion-deferral runs across **four different phrasings** the model was never shown verbatim (F6's exact case, plus F7/F8/F9's genuinely novel generalizations) — strong evidence the underlying mechanism, not just the specific worked example, is sound.
- The rule-17 taxonomy correction (removing criterion deferrals from `AMBIGUOUS`) held 8/8 — no run misrouted a criterion deferral into `AMBIGUOUS`.
- All 16 regression-protected runs (F1/F2/F3/F4/F5) passed without exception — nothing in this revision destabilized previously-locked behavior.
- F10 — the case specifically designed to test whether the grounding rule operates independently of the classification fix — passed cleanly 2/2, exactly confirming audit §3's design.
- The one true zero-tolerance failure (F6 run 3) is a single-run inconsistency on the exact case the fix targets, not a wrong policy — the same prompt got it right twice.

**What actually needs to change, narrowly**: rule 20's wording needs strengthening in two specific, addressable ways, neither requiring a schema or architecture change:
1. **The COMPLETE/CORRECT leak (F6 run 3)**: add an explicit, unambiguous instruction that introducing a previously-unknown value (a price, in this pattern) must **never** be paired with `completeness=COMPLETE` — regardless of how confidently the reply is phrased — until the learner has actually confirmed a choice in a subsequent turn. A concrete worked example showing the exact required field values for the shopkeeper-price scenario (mirroring this project's own repeated success pattern — D1's worked example generalizing cleanly by the next round) is the recommended smallest fix.
2. **Non-currency fabrication (F7/F8)**: rule 20 currently only worked-examples price ("a shopkeeper can state a price"). Add one or two additional short worked examples spanning a different value-type (e.g., timing or ratings) so the non-fabrication instruction, not just the completeness-routing instruction, generalizes across value-types as reliably as it generalized across *phrasings* this round.
3. **F9's `clarification_required` ambiguity**: not a failure, but worth resolving before the next round — explicitly state in rule 20 whether a learner's-own-info deferral should set `clarification_required=true` (routing to `UNCLEAR`) or leave it `false` (routing to `PARTIAL_ANSWER`, matching the other three generalization patterns), so the model's own output stops varying on functionally identical input.

Per the explicit instruction for a FAILED result: **no production code has been modified, the plan has not been retroactively altered to force a pass, no case was rerun, no threshold was changed, and the 48-case evaluation has not been run.** The next step is a second, narrow prompt revision (rule 20 wording only, no schema/derivation change) followed by a fresh, independently-run calibration — not resumed from these results — gated behind explicit authorization as with every prior phase.

---

## Final Integrity Check

- Total call count: **exactly 24** (verified via `data['total_calls']` and the script's own runtime assertion). ✓
- Every planned case executed: F1–F10, all with their exact planned run counts (3/3/3/2/2/3/2/2/2/2). ✓
- No unplanned case counted: the 1 pre-batch F6 diagnostic call is explicitly excluded from every count and table in this report. ✓
- PASS/FAIL arithmetic independently re-checked against the raw JSON (§9) — 11/12, 4/4, 6/8. ✓
- No threshold changed after observing results — the one change (§2) was made before call 1 of 24, in response to a pre-batch diagnostic, and did not alter the 91.7% zero-tolerance figure. ✓
- No production application code changed — `backend/app/` untouched; this script and its outputs live entirely outside the application, in the scratchpad directory. ✓
- No migration created. ✓
- Nothing committed. ✓
- Nothing pushed. ✓

**This report states a narrow failure honestly rather than a false pass.** Implementation of the recommended fix has not begun.
