# AI Tutor V4 Semantic Calibration — Real-Provider Test Report

Status: **Calibration test complete. 19/19 real API calls executed exactly as pre-committed, after a locked pre-run consistency check on the deterministic layer. No production code, migrations, commits, or pushes were made.** The revised schema, prompt, and guards exist only in a temporary, disposable script outside `backend/app/`.

**Headline: the calibration test FAILED against the locked zero-tolerance bar (9/12 = 75%, not the required 100%).** Verdict **B**. The failure is narrow and well-characterized, not a broad regression — full detail below, including a genuine, honestly-reported instance of the deterministic layer's fail-safe rule producing an unintended side effect (§6).

---

## 1. Provider/model

Groq, `openai/gpt-oss-120b` — identical to every prior round. Not substituted.

## 2. Exact number of API calls used

**19 of 19 pre-committed calls.** 4 high-risk cases (D1-D4) × 3 runs + 2 watch-tier cases (D5, D8) × 2 runs + 3 standard-tier cases (D6, D7, D9) × 1 run = 12 + 4 + 3 = 19. No call skipped, no call added. Every repeated run was built fresh from the case's static definition; no run's response was ever fed into another run's input.

## 3. Pre-run locked truth table

**Locked and unit-tested against 7 hand-worked scenarios before any API call was made** (verified output shown for each, matching expectation exactly in every case):

```python
def final_learner_intent_known(raw_intent_known, meaning_status, context_resolution):
    if raw_intent_known is False:
        return False                                            # Rule 1 - highest priority, unconditional
    if context_resolution == "AMBIGUOUS":
        return False                                             # Rule 2
    if meaning_status == "UNCLEAR":
        return False                                             # Rule 3
    if meaning_status == "PRESERVED" and context_resolution in (None, "CLEAR"):
        return None                                               # Rule 4 - nothing to assess
    if raw_intent_known is None and meaning_status in ("CHANGED", "SLIGHTLY_WRONG"):
        return False                                              # Rule 5 - fail-safe, no signal given
    if raw_intent_known is None:
        return False                                              # Rule 6 - CONFLICTING-only, still no signal
    return raw_intent_known                                       # Rule 7 - trust an explicit True
```

**Key correction locked in before running, directly from the authorizing message's own example**: `context_resolution=CONFLICTING` does **not** appear as a forcing condition anywhere above. A clear-but-conflicting answer ("Do you like apples?" → "No, I like oranges.") has fully knowable intent — the conflict is a fact about *what* was said, not evidence that *what was meant* is unresolved. Verified against the exact example given:

| Scenario | raw `learner_intent_known` | `meaning_status` | `context_resolution` | **Locked result** |
|---|---|---|---|---|
| Red/new shoes (unsafe) | `false` | `CHANGED` | `CONFLICTING` | **`false`** (Rule 1) |
| Apples/oranges (safe) | `true` | `CHANGED` | `CONFLICTING` | **`true`** (Rule 7) |
| Apples/oranges, model gives no signal | `null` | `CHANGED` | `CONFLICTING` | **`false`** (Rule 6, fail-safe) |
| Cross-turn contradiction (e.g. "two brothers" / "only child") | `true` | `PRESERVED` | `CONFLICTING` | **`true`** (Rule 7 — content is clear, conflict is external) |
| Ambiguous reference ("the other one"), even if raw wrongly says `true` | `true` | `PRESERVED` | `AMBIGUOUS` | **`false`** (Rule 2, forced, overrides a wrong raw signal) |
| Ordinary clean answer | `null` | `PRESERVED` | `null` | **`null`** (Rule 4, nothing to assess) |
| Clear single-referent reference | `null` | `PRESERVED` | `CLEAR` | **`null`** (Rule 4) |

**The 4 categories the authorizing message required distinguished, mapped explicitly:**

| Category | `context_resolution` | `learner_intent_known` | `clarification_required` | `corrected_sentence` |
|---|---|---|---|---|
| 1. Clear but conflicting answers | `CONFLICTING` | driven by raw signal (typically `true`) | driven by raw signal (typically `false`) | allowed, non-null |
| 2. Ambiguous references | `AMBIGUOUS` | **forced `false`** | **forced `true`** | **forced `null`** |
| 3. Unresolved learner intent (general) | any | `false` (explicit, or fail-safe default) | forced `true` | forced `null` |
| 4. Safe mechanical corrections | `null`/`CLEAR`, meaning `PRESERVED` | `null` (nothing to assess) | `false` | normal, non-null |

**`final_clarification_required`** and **`final_corrected_sentence`** are unchanged from the prior round's already-fixed design (`clarification_required` is the sole, final gate for `corrected_sentence`; nothing downstream re-reads the raw value). `derive_overall_status` is unchanged in structure — `context_resolution` does not feed it directly, only through `clarification_required`, per the V4 plan's own minimal-change discipline. This full pipeline was implemented and unit-tested (§3's table) **before** the first real API call, satisfying the "lock the precedence rules before the first API call" requirement.

## 4-5. Every case, every repeated run — raw vs. normalized

**D1 — Red/new shoes (UNSAFE canonical), zero-tolerance, 3 runs**

| Run | meaning | context_resolution | `learner_intent_known` | `clarification_required` | `corrected_sentence` | Verdict |
|---|---|---|---|---|---|---|
| 1 | CHANGED | CONFLICTING | false | true | **null** | **PASS** |
| 2 | CHANGED | CONFLICTING | false | true | **null** | **PASS** |
| 3 | CHANGED | CONFLICTING | false | true | **null** | **PASS** |

**D1: 3/3 PASS.** Run 2's `context_feedback` explicitly said "You changed the attribute from color (red) to condition (new)" — the model applied the exact category-mismatch reasoning taught in the revised prompt.

**D2 — Apples/oranges (SAFE, revised), zero-tolerance, 3 runs**

| Run | meaning | context_resolution | `learner_intent_known` | `clarification_required` | `corrected_sentence` | Verdict |
|---|---|---|---|---|---|---|
| 1 | CHANGED | CONFLICTING | **true** | **false** | "No, I don't like eating oranges." | **PASS** |
| 2 | CHANGED | CONFLICTING | **true** | **false** | "No, I don't like eating oranges." | **PASS** |
| 3 | CHANGED | CONFLICTING | **true** | **false** | "No, I don't like eating oranges." | **PASS** |

**D2: 3/3 PASS — the direct, successful validation of the pre-run fix.** Every run preserved "oranges" (never silently substituted "apples") and correctly treated the answer as safe, deliberate, and complete. Run 3's `context_feedback`: "You answered about oranges instead of apples, which is a valid alternative."

**D3 — Ambiguous reference #1 ("the other one"), zero-tolerance, 3 runs**

| Run | context_resolution | `learner_intent_known` | `clarification_required` | `corrected_sentence` | Verdict |
|---|---|---|---|---|---|
| 1 | AMBIGUOUS | false | true | null | **PASS** |
| 2 | AMBIGUOUS | false | true | null | **PASS** |
| 3 | AMBIGUOUS | false | true | null | **PASS** |

**D3: 3/3 PASS**, identical, no instability.

**D4 — Ambiguous reference #2 ("the first one"), zero-tolerance, 3 runs**

| Run | context_resolution | `learner_intent_known` | `clarification_required` | `corrected_sentence` | Verdict |
|---|---|---|---|---|---|
| 1 | **CLEAR** (expected AMBIGUOUS) | null | false | null | **FAIL** |
| 2 | **CLEAR** | null | false | "The first one" | **FAIL** |
| 3 | **CLEAR** | null | false | null | **FAIL** |

**D4: 0/3 PASS — the only case to fail every run, with no variance.** In all 3 runs the model resolved "the first one" to "chicken" (the item named first in "Would you like the chicken or the fish?") and treated this as a fully clean, unambiguous answer — replying e.g. "Great, you chose the chicken. Would you like any side dish with it?" See §6 for why this is graded as a failure and the important nuance around it.

**D5 — Clear reference to one alternative, watch tier, 2 runs**

Both runs: `context_resolution=CLEAR`, `meaning_status=PRESERVED`, `clarification_required=false`. **2/2 correct** — the new field did not false-trigger on a genuinely unambiguous pronoun reference.

**D6 — Off-topic, grammatically correct, standard tier, 1 run**

Raw: `answer_relevance=NONE` ✓, `meaning_status=CHANGED` ✗ (expected `PRESERVED`), `context_resolution=null` ✓, raw `clarification_required=false`. After the deterministic layer: `learner_intent_known` forced to `false` (Rule 5/6 — no explicit raw signal, meaning≠PRESERVED), `clarification_required` forced to `true`, `overall_status=UNCLEAR`. **FAIL** — see §6 for the two distinct causes.

**D7 — Valid unconventional answer, standard tier, 1 run**

`meaning_status=PRESERVED`, `grammar_status=CORRECT`, `context_resolution=null`, 0 issues, `clarification_required=false`. **PASS**, clean.

**D8 — Repeated identical mechanical errors, watch tier, 2 runs**

Both runs: raw `issues[]` contained exactly 3 entries — `{type: CAPITALIZATION, original: "i", occurrence: 1}`, `{..., occurrence: 2}`, `{..., occurrence: 3}` — genuinely distinct, correctly numbered, all 3 survived to the normalized output, and `corrected_sentence` capitalized all 3 instances. **2/2 PASS — a complete, unambiguous fix** of the exact undercounting failure that persisted across both the original 48-case run and the prior V3 calibration round.

**D9 — Multiple different mechanical errors, standard tier, 1 run**

Raw `issues[]`: 5 entries, including `{"i", occurrence: 1}` and `{"i", occurrence: 2}` as two genuinely distinct spans (previously undercounted to 4/5 in *both* earlier rounds on this exact case). **PASS — first-ever exact 5/5 match on this case across three rounds of testing.**

## 6. Deterministic guard actions

**Zero guard actions fired across all 19 calls** — no span-existence violations, no true duplicates needing the occurrence-aware dedupe, no mechanical-plausibility rejections, no severity-based upgrades. Every raw response was already guard-compliant. This is itself informative: it means every result below reflects the *model's* judgment directly, not a guard correction papering over a bad response.

**Two findings requiring separate, honest explanation — not silently folded into "the model failed":**

**D4's failure is a defensible disagreement, not a confused one.** Unlike the original red/new-shoes bug (a genuine, dangerous confusion between unrelated attributes), "the first one" has an objectively computable resolution rule: whichever alternative was named first in the immediately preceding question. A fluent English speaker plausibly *would* resolve it this way without hesitation — this is linguistically closer to how "the former" functions than to "the other one"'s genuine referential gap (which requires knowing something external, like which one was already rejected). The locked test criteria required treating this as `AMBIGUOUS` regardless, as a deliberate safety-first design choice (order-based reference is a known source of real-world mistakes — a learner might misremember which was named first, or use "first" to mean "my first choice" rather than "first-named"). **Both readings are legitimate.** The model's behavior is not evidence of the same failure class as the original bug; it is evidence that ordinal-reference resolution needs its own, separate design decision in the next round — either the taxonomy explicitly carves out "objectively resolvable ordinal reference" as `CLEAR` (accepting the model's reading), or the prompt adds an explicit instruction that ordinal references to a just-offered list must still be confirmed, not silently resolved, for safety-first reasons.

**D6 exposes a real regression *and* an unintended guard side-effect, and these are two different problems.** First, the model's own `meaning_status=CHANGED` judgment on a plain off-topic answer ("The weather is nice today" for "why should we hire you") is a regression of the exact relevance/meaning conflation bug that a prior round's prompt rule (§11, "a factually/substantively wrong answer... is a meaning_status problem, not a relevance problem" — inverted here, since this answer is not even substantively addressing the topic) had previously fixed for this identical case shape. This is a prompt-robustness problem, not new. Second — and this is new — the deterministic layer's Rule 5/6 fail-safe (`meaning_status ∈ {CHANGED, SLIGHTLY_WRONG}` with no explicit raw `learner_intent_known` signal → force `false`) was designed with word-substitution cases in mind, where "no signal" plausibly is unsafe. It was not designed to distinguish "no signal because this is a word-substitution case" from "no signal because this is a plain off-topic case that got mislabeled." Because D6's `meaning_status` was (wrongly) `CHANGED`, the fail-safe fired and force-escalated a simple off-topic turn into `clarification_required=true`/`overall_status=UNCLEAR` — a cascading consequence neither the model nor the original guard design intended. **Reported as a genuine flaw in the guard's scope, per instruction, not used to relax D6's grade** — D6 is still marked FAIL against the locked criteria.

## 7. Context-resolution results

| Value | Count | Cases |
|---|---|---|
| `CONFLICTING` | 6 | D1 ×3, D2 ×3 — 100% correct classification in every instance |
| `AMBIGUOUS` | 3 | D3 ×3 — 100% correct; **never produced on D4**, 0/3 |
| `CLEAR` | 7 | D4 ×3, D5 ×2, D9 ×1 (see note below), plus... |
| `null` | 3 | D6, D7, D8 (×2 combined into null since no reference language present) |

**One minor, low-stakes over-application worth noting**: D9's "the blue ones" was classified `CLEAR` despite there being no actual prior-named alternative to resolve against (the conversation had no earlier list of jacket colors) — a mild misuse of the taxonomy's `CLEAR` value for what should likely have been `null`. Not a safety issue (`CLEAR` does not force anything; `learner_intent_known` still correctly resolved via Rule 4), but worth refining the field's definition further in a future round.

## 8. Intent-known results

Every explicit `false` (D1 ×3, D3 ×3) was correctly forced through and never overridden — direct confirmation of hard invariant #1. Every explicit `true` on a genuinely safe case (D2 ×3) was correctly trusted, not second-guessed — direct confirmation of hard invariant #5 (CONFLICTING does not imply unknown intent). D4's `true`/`null` results reflect the model's own (defensible, per §6) judgment that intent was in fact known.

## 9. Clarification behavior

`clarification_required=true` fired exactly when intended in 9 of the 12 zero-tolerance-tier runs (D1 ×3, D3 ×3 = 6/6 correct positives; D4 ×3 = 0/3, never fired when it should have per the locked criteria) plus 1 unintended positive (D6, via the guard side-effect in §6). No run showed `clarification_required=true` with a *non-null* `corrected_sentence` anywhere in this dataset — the exact C7-run-1-class bug from the prior round **did not recur once** across all 19 calls, direct confirmation the priority-order fix (§3) holds.

## 10. Corrected-sentence safety

**Zero violations of "clarification_required=true implies corrected_sentence=null" across all 19 calls** (hard invariant #2/#3). D2's 3/3 non-null corrections all correctly preserved "oranges" — no run of D1 or D2 ever silently substituted one fruit/color word for the other in either direction.

## 11. Occurrence-resolution behavior

**Fully successful, both cases it was built for.** D8 (3 expected repeats) and D9 (2 expected repeats within a 5-issue case) both achieved exact, occurrence-tagged enumeration on every run — a clean, complete fix of a bug that had persisted, unaddressed, across two full prior evaluation rounds (the original 48-case run's cases 43/45, and the V3 calibration's C9/C10). No guard ever needed to invoke the occurrence-aware dedupe (§6's "zero guard actions" finding) because the model never produced a spurious true-duplicate in this round.

## 12. Instability across repeated calls

**D1, D2, D3: no instability** — identical qualitative behavior across all 3 runs each, only cosmetic wording variance in `reply`/`context_feedback`. **D4: no instability either, but consistently wrong** — 3/3 identical, confident `CLEAR` classification, not a coin-flip the way the prior round's C7/C8 were. This reinforces §6's framing: D4 is not evidence of unreliable/unstable judgment, it is evidence of a *consistent, different* judgment than the locked test expected. **D5, D8: no instability**, both watch-tier mechanisms performed identically across their 2 runs each.

## 13. Errors or malformed responses

**Zero.** All 19 calls returned valid, schema-conformant JSON on the first attempt. All retries observed in the run log were Groq `429` rate-limit retries (handled automatically, waiting the exact duration specified), consistent with every prior round.

## 14. Confirmation that no criteria changed after seeing results

**Confirmed.** §3's truth table, the 9-case/19-call structure, and the per-case pass/fail expectations (including D2's revised, corrected expectation) were locked and unit-tested *before* the first API call — this is a matter of record in the tool-call sequence, not an after-the-fact claim. D4's grading (FAIL) and D6's grading (FAIL) are both reported exactly against those pre-locked criteria, with the nuance in §6 offered as analysis for the *next* design round, not as a retroactive excuse applied to *this* round's verdict.

---

## Final verdict

## **B — V4 CALIBRATION FAILED: REVISE BEFORE FULL RE-EVALUATION**

Per the locked gate: 100% pass required on the zero-tolerance tier (D1-D4, 12 runs). Actual: **9/12 (75%)** — D1, D2, D3 perfect (9/9); D4 failed all 3 runs. The gate's own rule ("anything short of 100% on D1-D4 means iterate... not spend the 48-case budget") is dispositive regardless of how well the rest of the dataset performed.

**This is a narrower, more precisely-characterized failure than the prior round's.** The core mechanism this calibration exists to validate — the safe/unsafe substitution distinction (D1 vs. D2) and genuine referential ambiguity (D3) — worked perfectly, with zero instability, across all 9 of those runs. The occurrence-field fix (D8, D9) is fully validated. The one true zero-tolerance failure (D4) is a defensible disagreement about ordinal-reference resolution, not a recurrence of the original dangerous-confidence bug. The one standard-tier failure (D6) traces to two identified, fixable causes: a prompt-robustness regression on off-topic classification, and a guard fail-safe with a wider blast radius than intended.

**Recommended next-round scope, informed directly by this run**: (1) make an explicit, deliberate decision about ordinal references ("the first/second one") — either accept them as `CLEAR` when objectively resolvable, or add a specific prompt rule requiring confirmation regardless; (2) re-strengthen the off-topic/meaning_status boundary rule that regressed on D6; (3) scope the Rule 5/6 fail-safe more precisely so it doesn't cascade for off-topic cases that happen to get mislabeled. None of these require touching the schema again — §3's truth table and the `context_resolution`/`occurrence` mechanisms are validated and should be kept as-is.

**Per the explicit constraint on this task: this verdict does not claim READY FOR IMPLEMENTATION.** A failed calibration does not authorize the 48-case re-evaluation. The next step is a further, narrowly-scoped prompt/guard revision addressing the two items above, followed by another calibration test before the larger budget is spent.

---

## What this report does not do

Does not modify `backend/app/`. Does not add or alter any schema, model, or migration. Does not modify the production system prompt. Does not run the 48-case dataset. Does not commit or push. The calibration script and raw results live only in this session's scratchpad directory, outside the project's git repository.
