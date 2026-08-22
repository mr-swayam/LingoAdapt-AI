# AI Tutor V4.1 Policy — Audit

Status: **Audit only. No production code, migrations, commits, or pushes. No new real-provider API calls.** Every claim below is a re-derivation from `AI_TUTOR_V4_CALIBRATION_REPORT.md`'s actual data (already collected), examined against the two specific, narrow questions this review raised: is D4's ordinal-reference resolution a policy question or a safety bug, and is D6's off-topic regression a prompt problem, a schema problem, or both.

This is a narrow, targeted audit — not a re-audit of the whole V4 architecture, which `AI_TUTOR_V4_SEMANTIC_ARCHITECTURE_AUDIT.md` already covered and which D1/D2/D3/D8/D9's clean results confirm is sound.

---

## 1. Is D4 a safety bug or a policy question?

Re-examining the calibration report's §6 discussion with fresh scrutiny, specifically asking: does "the first one" share the actual *mechanism of danger* that made red/new-shoes and "the other one" genuine failures?

**What made the original red/new-shoes case dangerous**: the substituted word ("new") had **no self-resolving anchor in the utterance itself** — nothing in "red" vs. "new" tells you which the learner meant; the only way to guess is to assume one was a slip, which is exactly the fabrication the whole review process exists to prevent.

**What makes "the other one" genuinely ambiguous**: "other" is defined *relative to* an already-established reference point ("other than X") — but in "Would you like the blue one or the green one?" → "the other one", no such reference point has been established yet (this is the learner's *first* response to the offer, nothing has been picked or excluded). "Other" has **no anchor to resolve against**, by construction, regardless of how the sentence is read.

**What is different about "the first one"**: an ordinal (first/second/last) resolves against a *different*, and *always-available*, anchor — the **utterance order of the immediately preceding offer itself**. "Would you like the chicken or the fish?" places chicken first as a plain fact of how the sentence was constructed; "the first one" is not asking the tutor to guess anything external — it is asking the tutor to recall its own immediately-preceding sentence, which is always fully available. This is mechanically closer to how "the former"/"the latter" function in English than to "the other one"'s genuine gap.

**Verified against the actual data (3/3 identical, confident, non-contradictory resolutions across independent real calls, §12 of the calibration report)**: the model did not produce 3 different guesses or hedge inconsistently — it applied the same rule every time, correctly reading "chicken" from its own prior turn. This is the behavioral signature of applying a real linguistic rule, not the behavioral signature of confident guessing (which, on the original red/new-shoes bug, produced *inconsistent* outcomes across repeated real calls — recall the original evaluation's finding that repeated calls to the same ambiguous case produced *different* results).

**Conclusion**: D4 is a **policy question, not a safety bug**. The calibration test's own locked expectation (`AMBIGUOUS`) encoded an assumption — that any reference to a just-offered list needs confirmation regardless of how it's phrased — that turns out not to hold for ordinal references specifically. This section recommends accepting the ordinal-resolution policy proposed for review, with the exact boundary conditions worked out in §2, and updating the calibration expectation accordingly — not weakening any property that was actually protecting against a real risk.

## 2. Exact boundary: when is an ordinal reference safe to resolve?

Stress-tested against scenarios not present in the original 48-case or V3/V4 calibration data, to check the proposed 3-condition policy doesn't quietly admit a real risk:

| Scenario | Safe to resolve? | Why |
|---|---|---|
| "Would you like the chicken or the fish?" → "the first one" | **Yes** | Single, immediately-preceding, explicit two-way offer; ordinal maps to exactly one item |
| "Would you like chicken, fish, or pasta?" → "the second one" | **Yes** | Same shape, 3-way; ordinal still maps to exactly one item |
| "Would you like coffee or tea? And would you like a muffin or a croissant?" → "the first one" | **No — must ask** | Two competing ordered lists in the immediately relevant context; "first" could mean coffee or muffin. This is exactly condition 3 of the proposed policy ("no competing ordered list... that makes the reference ambiguous") |
| "We have chicken, though the fish is more popular. What would you like?" → "the first one" | **No — must ask** | Not an explicit ordered offer (no "X or Y" list structure) — a mention embedded in a sentence is not "a clearly ordered list of alternatives" per condition 1; treat as `AMBIGUOUS`, same as an unanchored "the other one" |
| "Would you like the blue one or the green one?" → "the other one" | **No — must ask (unchanged)** | No ordinal is used at all; "other" requires an *exclusion* anchor that does not exist on a first response. This case is explicitly out of scope for the ordinal policy and remains `AMBIGUOUS` — see §5's regression requirement |

**The precise, locked test for condition 1** ("clearly ordered list of alternatives"): the immediately preceding tutor turn must contain an explicit enumerated offer in "X or Y" / "X, Y, or Z" form. A list of items merely *mentioned* in a sentence, without being posed as the actual alternatives being offered, does not qualify.

## 3. Root cause of D6, re-derived precisely

The calibration report's §6 already identified two contributing causes (a `meaning_status` misclassification, and a fail-safe guard with a wider blast radius than intended). This audit adds the missing piece: **why** the misclassification kept recurring across three separate rounds (original 48-case cases 28/29, an early V3 calibration pass, and now D6), despite each round adding a new prompt clarification aimed at it.

**The recurring bug is a definitional gap, not a wording gap.** Every prior fix (rule 11's "answer_relevance measures topic-relatedness... a factually wrong answer to the right question is a meaning_status problem, not a relevance problem") addressed only *one direction* of the boundary — distinguishing "wrong content, right topic" from "off-topic." It never stated what `meaning_status` should default to *when the topic is simply absent*. Re-reading the field's implicit definition: `meaning_status` asks "does this answer's content diverge from what was expected" — but divergence is only a coherent question when there is a **shared slot** being compared (the same attribute/topic, different value, per the `CONFLICTING` definition already locked in V4). When `answer_relevance` is `NONE`/`LOW`, there is no shared slot at all — nothing for `meaning_status` to have "changed" *relative to*. The prompt has repeatedly told the model what `meaning_status=CHANGED` requires in the positive case, but never explicitly told it that the field collapses to `PRESERVED` by construction once there is no shared slot to compare against. **This is exactly the kind of gap a deterministic guard, not another round of prompt wording, is suited to close permanently** — see the sibling plan document §2.

## 4. Does the current schema already support Clarification vs. Redirect?

Traced the full derivation path for both example behaviors named in the review request, using fields that already exist:

**Clarification** ("the other one", multiple possible referents): `context_resolution=AMBIGUOUS` → `learner_intent_known` forced `false` → `clarification_required` forced `true` → `derive_overall_status` Rule 1 fires first → **`overall_status=UNCLEAR`**.

**Redirect** ("I like playing football" for "Do you like apples?"): `answer_relevance=NONE` → (once §3's fix is applied) `meaning_status=PRESERVED` → `learner_intent_known` resolves via Rule 4 (nothing forced) → `clarification_required` stays `false` (nothing forces it) → `derive_overall_status` Rule 1 does not fire (clarification_required is false) → Rule 3 fires (`relevance ∈ {NONE, LOW}`) → **`overall_status=OFF_TOPIC`**.

**These are already two structurally distinct values of the same existing field** (`overall_status ∈ {UNCLEAR, OFF_TOPIC}`), reached via two different derivation paths that already exist, unmodified, in `derive_overall_status`. **D6's actual bug was that the off-topic case was being mis-routed into the `UNCLEAR`/Clarification path instead of the `OFF_TOPIC`/Redirect path** — which is a direct, concrete illustration of why this distinction matters in practice: before the fix, a genuinely clear off-topic answer would have produced tutor behavior indistinguishable from a genuinely ambiguous one (asking to clarify, when the correct behavior is to acknowledge and redirect).

**Conclusion: no new field is required.** The distinction is already fully representable; it was simply unreachable for one specific input shape because of the upstream `meaning_status` bug. Fixing that bug (plan §2) is sufficient to make both existing derivation paths reachable correctly. This directly satisfies the instruction not to add a field unless an existing one cannot represent the distinction — verified by tracing the actual derivation, not assumed.

## 5. What must not regress (carried forward, not re-derived)

D1 (unsafe substitution), D2 (safe substitution), D3 (genuine ambiguity, no ordinal involved), the guard priority ordering (explicit raw `false` always wins), `corrected_sentence` nulling exactly when `clarification_required` is true, and occurrence-based repeated-issue tracking are all **unmodified by this revision** — none of the fixes in the sibling plan touch the code paths these depend on (§3's `meaning_status`-forcing guard is scoped specifically to `relevance ∈ {NONE, LOW}`, which none of D1/D2/D3 ever produce). They are carried into the V4.1 calibration set as explicit regression cases (plan §6), not re-derived here.

## 6. What this audit does not do

Does not propose exact guard code, prompt text, or the final calibration set — that is `AI_TUTOR_V4_1_POLICY_PLAN.md`'s job. Does not make any new real-provider API call. Does not modify `backend/app/`, add a migration, or commit/push.
