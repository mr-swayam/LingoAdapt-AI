# AI Tutor V4.2 Grounding — Audit

Status: **Audit only. No production code, migrations, commits, or pushes. No real API calls.** Every claim below is either (a) a direct trace of the V4.1 calibration script's actual schema/normalization/derivation/prompt logic (the same logic `AI_TUTOR_V4_1_CALIBRATION_REPORT.md`'s 23 real calls ran against), or (b) a re-derivation from that report's own E9 data.

---

## 1. Primary question: what is E9, exactly?

Re-examined against the 5 offered categories, using the actual raw data, not assumption.

**A — reference ambiguity: does not apply.** "The other one" (E3, 3/3 correctly `AMBIGUOUS`) fails because it supplies **no resolution rule at all** — nothing in the utterance says how to pick between blue and green. "Whichever is cheaper" supplies a **complete, unambiguous resolution rule** (compare price, take the lower one) — there is nothing to guess about *which* rule applies. The failure is not in identifying the rule; it is in **executing** it. This is a different linguistic phenomenon from E3's, confirmed by tracing that E3 passed cleanly in the identical run while E9 failed in all 3.

**B — unknown learner intent: does not apply.** The learner's intent ("give me the lower-priced option") is stated more explicitly and completely than most of this dataset's clean-pass cases. There is no guessing involved in understanding *what they want*.

**C — known intent, insufficient grounding: the actual root cause.** The learner's selection *rule* is fully known; the *data* needed to execute it (the two prices) was never established anywhere in the conversation. This is the one category none of the schema's existing values (`context_resolution ∈ {CLEAR, AMBIGUOUS, CONFLICTING, null}`, `completeness ∈ {COMPLETE, PARTIAL, MINIMAL}`) was ever taught to route correctly for — traced in §2.

**D — roleplay-induced fact fabrication: a real, observed symptom, not the root cause.** 2 of 3 runs invented specific prices ("$5"/"$8," identical across both fabricating runs — a template-shaped guess, not a random one). But this is downstream: it happened *because* the model, forced to pick from a taxonomy with no slot for "intent known, data missing," picked the closest available option (`CLEAR`) — and once committed to `CLEAR` (a value whose only documented meaning is "resolved, nothing more needed"), nothing in the prompt told it not to manufacture the missing input to make that resolution true. Fix the classification (§4/§5 of the sibling plan) and the pressure that produces the fabrication is removed at its source, not merely masked.

**Answer: primarily C, with D as C's direct downstream consequence. Not A. Not B.** This is not "a combination" in the sense of several independent causes — it is one root cause with one predictable symptom, verified against the actual data rather than assumed.

## 2. Trace: can the current schema represent "known intent, insufficient grounding" today?

Traced directly against the V4.1 script's actual code (`final_learner_intent_known`, `derive_overall_status`, the `RawTutorTurn`/`ContextResolution` definitions — identical to what the 23 real calls ran against):

```python
class ContextResolution(enum.StrEnum):
    CLEAR = "CLEAR"; AMBIGUOUS = "AMBIGUOUS"; CONFLICTING = "CONFLICTING"

class Completeness(enum.StrEnum):
    COMPLETE = "COMPLETE"; PARTIAL = "PARTIAL"; MINIMAL = "MINIMAL"

def derive_overall_status(...):
    if clarification_required: return UNCLEAR
    if meaning == UNCLEAR: return UNCLEAR
    if relevance in (NONE, LOW): return OFF_TOPIC
    if meaning == CHANGED: return NEEDS_CORRECTION
    if relevance == PARTIAL or completeness != COMPLETE: return PARTIAL_ANSWER   # <- already exists
    ...
```

**Finding: `completeness=PARTIAL` → `overall_status=PARTIAL_ANSWER` is already a complete, working, unmodified derivation path** — traced through the exact rule that already fires for E7 ("i dont like wearing red shoes," a real partial answer that correctly derived `PARTIAL_ANSWER` in the same 23-call run). **Correction after re-verifying against the raw E9 data directly** (an earlier draft of this section misstated these values — checked again before treating this document as locked): `completeness` was actually `PARTIAL` in run 1 and `COMPLETE` in runs 2-3; `context_resolution` was `CLEAR` in all 3 runs.

**This corrected data point makes the case for §4's grounding rule *stronger*, not weaker.** Run 1 is the one run where `completeness` happened to land on `PARTIAL` — and it correctly derived `overall_status=PARTIAL_ANSWER` through the unmodified existing rule, exactly as this section argues. **But run 1 still fabricated prices in its free-text `reply`** ("The small size is $5 and the large is $8...") even though the *structured* classification was already correct. This is direct, first-hand evidence that the classification fix (routing criterion-deferrals to `PARTIAL`) and the grounding fix (rule 20, prohibiting fabricated values in the reply itself) are **two independent defects, not one problem with one fix** — run 1 proves a case can have the classification right and the fabrication happen anyway. (Runs 2-3, where `completeness` stayed `COMPLETE`, show the classification failure on top of the same fabrication risk — run 3 also fabricated, run 2 did not.)

**A second finding, more consequential**: the V4.1 prompt's own `context_resolution` rule (rule 17) **explicitly named this exact phrase as the definitional example of `AMBIGUOUS`**: *"or depends on information you do not have (e.g. 'whichever is cheaper' when you don't know prices)."* The model did not apply its own explicitly-taught rule in any of 3 runs. This raises the question the sibling plan resolves in §1: was `AMBIGUOUS` ever the *behaviorally correct* target for this case, or was the V4.1 taxonomy itself wrong to place it there? Reasoning through the downstream consequence: `AMBIGUOUS` forces `learner_intent_known=false` and `clarification_required=true`, which would make the tutor's correct reply something like *"Do you mean the small one or the large one?"* — a strange, slightly obtuse response to a learner who has already given a perfectly clear, complete decision rule. **The V4.1 taxonomy's own definition of `AMBIGUOUS` was itself part of the problem**, not just the model's failure to follow it — it conflated two different phenomena (an unresolvable pointer, and a resolvable-but-ungrounded criterion) under one value with one implied behavior, and that implied behavior (ask which they meant) is the wrong behavior for the criterion case.

**Conclusion: no new field is required.** `completeness=PARTIAL` (correctly applied to a criterion deferral, not just a topic-partial answer) plus `overall_status=PARTIAL_ANSWER` (already the exact correct downstream signal, unmodified) plus `context_resolution=null` (this is not a reference-to-a-list problem at all — see §3) already gives the schema everything needed. What was missing was prompt clarity on *which* existing value this pattern belongs to, and a wholly new, orthogonal rule about not fabricating the missing data — neither is a schema gap.

## 3. Is `context_resolution=null` correct for "whichever is cheaper," and does that generalize?

Traced against the `AMBIGUOUS` definition's own semantics: it exists to answer "does a reference resolve to exactly one of the *named* candidates." "Whichever is cheaper" does not ask that question — it does not fail to identify *which* named item is meant due to insufficient pointing information; it fails to *execute a stated comparison* due to insufficient *data*. These are different failures at different layers (reference resolution vs. fact availability), and conflating them was V4.1's own design error (§2).

**Stress-tested against a case where this framing does *not* hold, to check it isn't overgeneralized**: "Would you like the same jacket as last time, or a different color?" → "The one I bought before." This *does* resolve to exactly one of the two *named* alternatives ("same as last time") — nothing about *which* option is unclear. `context_resolution=CLEAR` is correct here, unlike the criterion-deferral cases. The risk in this shape is not classification at all — it is that, having resolved "which option," the model might then invent *specific attributes* of that past purchase (a color, a size) it has no data for. This is the same fabrication risk (D) attached to a `CLEAR`, not a `PARTIAL`, case — direct evidence that the grounding/non-fabrication rule needs to be **orthogonal** to `context_resolution`/`completeness`, applying regardless of which classification path a case takes, not bundled only into the criterion-deferral fix. The sibling plan's calibration set (§6) includes this exact case (case F10) specifically to test the grounding rule independent of the classification fix.

## 4. Trace: the tutor's role/persona instructions, and why they interact with fabrication risk

Rule 8 of the V4.1 prompt (unchanged since the very first version of this system prompt): *"Stay in character for the scenario and keep the conversation moving naturally."* This rule has no exception for factual grounding — it was never designed with this risk in mind, because until this round every prior failure mode was about *classifying* a learner's answer, not about the *tutor's own reply* asserting unestablished facts. Traced against the actual scenario in E9 (`RESTAURANT`... actually `SHOPPING`, "small size or large size") — a shopkeeper character *would*, in real life, know prices. Staying convincingly in character is genuinely in tension with admitting "I don't actually have that information," which a real shopkeeper never would say. **This is confirmed, not speculative** — 2 of 3 real runs demonstrate exactly this: the model produced fluent, in-character, confident price statements rather than any hedge.

**Important nuance, worth stating precisely rather than overcorrecting**: it is not obviously wrong, in a *language-practice roleplay*, for a tutor-as-shopkeeper to introduce a price as a natural next conversational beat — a human roleplay partner would very plausibly do the same, and refusing to ever state a price would make the tutor a worse, less natural conversation partner. **The actual risk is not the reply text containing a number — it is the *structured evaluation* simultaneously claiming the turn was `CLEAR`/fully resolved *using only already-established context*, when resolving it required inventing the context.** The sibling plan's grounding rule (§4) is designed around this precise distinction: a tutor introducing new, honest, in-character information is fine and should still be graded as an incomplete turn (`PARTIAL`, prompting a follow-up); a tutor *silently* finalizing a choice using invented data and marking the turn `CLEAR` is the actual defect. This reframing changes the fix from "restrict the tutor's roleplay freedom" (a real cost to the product's core pedagogical value) to "keep the tutor's roleplay freedom, but stop the *evaluation layer* from certifying an interaction as safely resolved when it wasn't."

## 5. What this audit does not do

Does not propose the exact prompt text, the deterministic guard's code, or the calibration set — that is `AI_TUTOR_V4_2_GROUNDING_PLAN.md`'s job. Does not make any real API call. Does not modify `backend/app/`, add a migration, or commit/push. Does not weaken any V4.1 pass criterion — §2/§3's findings are additive (a new rule, a corrected taxonomy boundary), not a reopening of D1/D2/D3/D4/D6's already-validated behavior, traced explicitly in the sibling plan's regression section.
