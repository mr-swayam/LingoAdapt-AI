# AI Tutor V4.1 Policy — Revision Plan

Status: **Planning document only. No application code, schema, or migration has been created or modified. No new real-provider API calls were made.** Gated behind a not-yet-run V4.1 calibration test (§6), itself gated behind explicit authorization — same discipline as every prior phase.

A **narrow** revision, per instruction: two policy/classification fixes on top of the already-validated V4 architecture (`AI_TUTOR_V4_SEMANTIC_ARCHITECTURE_PLAN.md`), not a redesign. No new field. No schema change. Every decision traces to `AI_TUTOR_V4_1_POLICY_AUDIT.md`.

---

## 1. Ordinal-reference policy

**Accepted, with the exact boundary conditions locked in audit §2.** Explicit ordinal references (`first`/`second`/`third`/`last`) resolve to `context_resolution=CLEAR` — not `AMBIGUOUS` — when:
1. The immediately preceding tutor turn poses an explicit, enumerated offer in "X or Y" / "X, Y, or Z" form (not merely a sentence that happens to mention multiple items).
2. The ordinal maps to exactly one of the enumerated alternatives.
3. No other competing enumerated offer exists in the immediately relevant context that the ordinal could instead resolve against.

**This is a policy decision, not a safety relaxation** — audit §1 establishes the actual mechanism-of-danger test (does the reference have a self-resolving anchor available from the utterance itself, or does it require guessing external information) and shows ordinal references pass that test while "the other one" does not. **`the other one`/`that one` without an ordinal remain `AMBIGUOUS`** whenever no exclusion anchor has already been established — this is explicitly unaffected by this policy (audit §2's last row, D3 unchanged).

**Prompt addition** (extends rule 17's `context_resolution` definition from the V4 plan):
```
CLEAR also includes: an ordinal reference ("the first one", "the second one",
"the last one") to an offer YOU explicitly enumerated in your immediately
preceding turn (e.g. "Would you like X or Y?"), when the ordinal maps to
exactly one of the alternatives you named and no other enumerated offer is
present nearby to compete with it. Resolve these deterministically from your
own prior turn - do not ask for clarification on a genuinely well-formed
ordinal reference to a list you just gave. If two or more enumerated offers
are both recent enough to compete for "first"/"second", or the alternatives
were only mentioned in passing rather than posed as an explicit either/or
question, treat the reference as AMBIGUOUS instead.
```

**Calibration expectation updated, not the model's behavior forced**: per instruction, D4 ("Would you like the chicken or the fish?" → "the first one") moves from the zero-tolerance `AMBIGUOUS` tier to a regression check expecting `context_resolution=CLEAR`, `overall_status` resolving via the ordinary clean-answer path (see plan §6, case E4).

## 2. Exact off-topic classification rule

**The rule, precisely**: `meaning_status` measures divergence *relative to a shared question-slot*. When `answer_relevance ∈ {NONE, LOW}`, there is no shared slot for content to have diverged from — `meaning_status` must default to `PRESERVED` (the sentence means exactly what it plainly says; there is nothing to compare it against). `meaning_status ∈ {CHANGED, SLIGHTLY_WRONG}` is **only** a valid classification when `answer_relevance ∈ {FULL, PARTIAL}` — the answer must at least be attempting to address the same topic before "diverged from it" is a coherent judgment. (`meaning_status=UNCLEAR` remains reachable regardless of relevance — a vague, low-content off-topic answer is still meaningfully "unclear" independent of being off-topic; this rule only forecloses `CHANGED`/`SLIGHTLY_WRONG` on off-topic answers, not `UNCLEAR`.)

**Locked invariant, exactly as instructed**: **`OFF_TOPIC != UNKNOWN_INTENT`.** An answer being unrelated to the question is never, by itself, evidence that the answer's own meaning is unresolved.

**Prompt addition** (extends rule 11):
```
11a. meaning_status=CHANGED or SLIGHTLY_WRONG requires a shared topic to
diverge from - only use these values when answer_relevance is FULL or
PARTIAL. When answer_relevance is NONE or LOW, meaning_status must be
PRESERVED (the off-topic sentence means exactly what it says - there is
nothing to compare it against) unless the answer is independently vague or
contentless on its own terms, in which case UNCLEAR still applies. OFF_TOPIC
is never evidence that the learner's intent is unknown - a clearly-written,
clearly-off-topic answer has fully known intent; it just isn't about the
right subject.
```

## 3. Guard-scope correction

**Root-caused, not patched twice.** Once §2's rule holds, `meaning_status` can never be `CHANGED`/`SLIGHTLY_WRONG` for an off-topic answer — so the fail-safe rule that caused D6 (`meaning_status ∈ {CHANGED, SLIGHTLY_WRONG}` with no explicit `learner_intent_known` signal → force `false`) can no longer be *reached* by an off-topic input at all. This is deliberately a **single root-cause fix reflected in two places**, not two independent patches: a deterministic guard enforces §2's rule even if the prompt is imperfectly followed, which is what actually closes the gap for real:

```python
def enforce_offtopic_meaning(meaning_status, answer_relevance):
    # NEW - applied to the raw meaning_status BEFORE it reaches
    # final_learner_intent_known. This is what makes "OFF_TOPIC !=
    # UNKNOWN_INTENT" a guaranteed invariant rather than a hoped-for prompt
    # outcome - the fail-safe rule in final_learner_intent_known now
    # structurally cannot fire for an off-topic input, because its
    # precondition (meaning_status in CHANGED/SLIGHTLY_WRONG) can no longer
    # be true once this guard has run.
    if answer_relevance in ("NONE", "LOW") and meaning_status in ("CHANGED", "SLIGHTLY_WRONG"):
        return "PRESERVED"
    return meaning_status
```

Called once, immediately after normalizing the raw `meaning_status`/`answer_relevance` values, before any of `final_learner_intent_known`/`final_clarification_required`/`derive_overall_status` run. No other function in the V4 pipeline changes.

**Why this is the correctly-scoped fix, not a broader change**: it activates on exactly one condition (`relevance ∈ {NONE, LOW}`), touches exactly one field (`meaning_status`, and only its `CHANGED`/`SLIGHTLY_WRONG` values — `UNCLEAR` and `PRESERVED` both pass through untouched), and every other fail-safe rule in `final_learner_intent_known` (explicit raw `false`, `AMBIGUOUS`, `UNCLEAR`) is completely unaffected — D1/D2/D3's derivations do not pass through this new function's forcing branch at all, since none of them have `relevance ∈ {NONE, LOW}`.

## 4. Clarification vs. Redirect behavior

**Schema change required: no** — audit §4 traces both behaviors to already-existing, already-distinct values of `overall_status` (`UNCLEAR` for Clarification, `OFF_TOPIC` for Redirect), reachable via already-existing derivation rules. The only reason Redirect was unreachable for the D6 shape was the upstream `meaning_status` bug (§2/§3), not a missing field.

**Prompt addition**, pairing with the existing ambiguity-clarification instruction (rule 14):
```
16a. When overall_status will derive to OFF_TOPIC (the answer is not about
the question's subject at all, but is itself clear), your reply should
briefly acknowledge what the learner actually said and then guide the
conversation back to the original question - do NOT ask a clarifying
question (there is nothing ambiguous to clarify) and do NOT treat this as
requiring intent-verification. This is a different tutor action from what
rule 14 describes for genuinely ambiguous answers: Clarification asks "which
did you mean?" when the system cannot safely tell; Redirect says, in effect,
"I understood you, but let's get back to X" when the system can.
```

## 5. Migration impact

**None.** No field is added or altered on `ConversationTurnEvaluation` or anywhere else. `enforce_offtopic_meaning` (§3) is pure in-memory normalization logic, exactly like every other forcing function already in the V4 design — it operates on values before they are ever persisted, and does not change what gets persisted (still `meaning_status`, one of its existing 4 values). The V4 plan's migration accounting (7 native enum types, `occurrence` unpersisted) is entirely unchanged by this revision.

## 6. V4.1 calibration (23 real calls, not run in this pass)

### 6.1 Cases

| # | Category (per review request) | Case | Risk / runs |
|---|---|---|---|
| E1 | D1 regression | Red/new shoes verbatim | HIGH, 3 runs |
| E2 | D2 regression | Apples/oranges verbatim | HIGH, 3 runs |
| E3 | D3 regression | "The other one" (blue/green) verbatim | HIGH, 3 runs |
| E4 | D4 under the new ordinal policy | "The first one" (chicken/fish) verbatim - **expectation now CLEAR, not AMBIGUOUS** | MEDIUM, 2 runs |
| E5 | D6 fix re-test | "The weather is nice today" (job interview) verbatim - **expectation now meaning=PRESERVED, overall_status=OFF_TOPIC** | MEDIUM, 2 runs |
| E6 | Off-topic answer with grammatical errors (new) | JOB_INTERVIEW. Prior: "Why should we hire you?" Answer: "the weather is realy nice today" - tests that forcing meaning=PRESERVED does not suppress a genuine, unrelated mechanical correction (spelling: realy→really) | standard, 1 run |
| E7 | Partial but relevant answer (regression) | SHOPPING. Prior: "What kind of shoes do you prefer to wear?" Answer: "i dont like wearing red shoes" | standard, 1 run |
| E8 | Clear conflicting answer, non-canonical pair (new) | TRAVEL. Prior: "Would you like to visit Paris or Rome?" Answer: "I'd rather go to Tokyo." - tests generalization of the safe-substitution mechanism beyond apples/oranges | HIGH, 3 runs |
| E9 | Genuinely ambiguous reference, different shape (new) | SHOPPING. Prior: "Do you want the small size or the large size?" Answer: "Whichever is cheaper." - ambiguous for a different reason than D3 (depends on external information - price - the tutor does not have), tests generalization of AMBIGUOUS detection | HIGH, 3 runs |
| E10 | Repeated identical grammar errors (regression) | RESTAURANT. Prior: "What did you order?" Answer: "i think i want the soup and i will get water too" (=D8 verbatim) | MEDIUM, 2 runs |

**Total: 3+3+3+2+2+1+1+3+3+2 = 23 calls.**

### 6.2 Pass/fail criteria, locked before running

**Zero-tolerance tier (100% required, no partial credit): E1, E2, E3, E8, E9** — the core substitution-safety and reference-ambiguity mechanisms, both canonical (E1/E2/E3) and generalization (E8/E9) instances.
- E1: `meaning=CHANGED`, `context_resolution=CONFLICTING`, `learner_intent_known=false`, `clarification_required=true`, `corrected_sentence=null` — every run.
- E2, E8: `context_resolution=CONFLICTING`, `learner_intent_known=true`, `clarification_required=false`, `corrected_sentence` non-null and preserving the learner's actual stated alternative (never silently substituted) — every run.
- E3, E9: `context_resolution=AMBIGUOUS`, `learner_intent_known=false`, `clarification_required=true`, `corrected_sentence=null` — every run.

**Policy-confirmation tier (E4, E5) — reported explicitly, gates on internal consistency across runs rather than a pre-existing external "correctness" standard, since these test newly-adopted policy decisions**:
- E4: `context_resolution=CLEAR` on both runs (confirms the new ordinal policy is stably applied, not a one-off); `clarification_required=false` both runs.
- E5: `meaning_status=PRESERVED`, `overall_status=OFF_TOPIC` (not `UNCLEAR`) on both runs — the direct, exact test of §2/§3/§4's fix.

**Standard tier (E6, E7, E10)**: adjacent-tolerance grading as in every prior round. E6 specifically requires `grammar_status=MINOR_ERRORS` with the spelling issue present *and* `meaning_status=PRESERVED` *simultaneously* - confirming the new guard does not over-suppress legitimate mechanical corrections on an off-topic answer. E10 requires full 3-occurrence enumeration (regression check on the already-fixed mechanism).

**Overall gate**: 100% required on the zero-tolerance tier (E1/E2/E3/E8/E9, 15 runs) to authorize the 48-case re-evaluation. E4/E5's policy-confirmation tier and the standard tier are reported and must show no regression, but per the "narrow revision" scope of this round, a soft miss there (e.g. one of E4/E5's two runs disagreeing) triggers a targeted re-check of that specific case only, not a full architecture reconsideration.

## 7. Final status

**READY FOR V4.1 CALIBRATION.**

Both policy questions (§1, §2) are resolved with explicit, defensible reasoning grounded in the actual mechanism of risk, not asserted by convenience. The guard-scope fix (§3) is a single root-cause correction, verified not to touch any of the already-working D1/D2/D3 code paths. No schema change is required (§4), verified by tracing the actual derivation rather than assumed. Migration impact is none (§5). The calibration set (§6) is fully specified with locked pass criteria. Nothing has been run — running §6 requires separate, explicit authorization, as with every prior gate in this review.

---

## What this plan does not do

Does not modify `backend/app/`. Does not add or alter any schema, model, or migration. Does not modify the production system prompt. Does not run the 23-call calibration set or the 48-case dataset. Does not commit or push. Does not touch any code path exercised by D1, D2, D3, the guard priority ordering, `corrected_sentence` nulling, or occurrence tracking — all five are unmodified and carried forward as explicit regression cases (§6).
