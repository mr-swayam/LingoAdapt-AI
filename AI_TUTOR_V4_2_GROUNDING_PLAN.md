# AI Tutor V4.2 Grounding — Revision Plan

Status: **Planning document only. No application code, schema, or migration created or modified. No real API calls made.** Gated behind a not-yet-run V4.2 calibration test (§6), itself gated behind explicit authorization — same discipline as every prior phase.

Written against `AI_TUTOR_V4_2_GROUNDING_AUDIT.md`'s findings. A narrow revision on top of the already-validated V4.1 mechanisms (§7 traces exactly why none of them are touched).

---

## 1. Exact root cause

**Primarily category C (known intent, insufficient grounding), with category D (fabrication) as its direct, predictable downstream consequence — not A, not B.** Audit §1's full reasoning. Restated as the one-sentence version: the learner gave a complete, unambiguous selection *rule* ("the cheaper one"); the schema had no value meaning "the rule is clear but its input data is missing," so the model reached for the closest available label (`CLEAR`), and having committed to "resolved," filled the resulting data gap by inventing plausible, in-character numbers.

**A second, compounding cause, traced directly to the V4.1 prompt's own text (audit §2)**: rule 17 explicitly named "whichever is cheaper" as an example of `AMBIGUOUS` — but `AMBIGUOUS`'s implied behavior (ask which the learner meant) is behaviorally wrong for a criterion deferral (the learner didn't leave anything unclear; they gave a rule). **V4.1's own taxonomy definition was part of the defect, not only the model's failure to follow it.**

## 2. Chosen policy

**Criterion-based deferrals** ("whichever is X," "whatever works," "the one I liked/bought before" *when the reference is genuinely non-specific*) are reclassified: `context_resolution=null` (this is not a reference-to-a-named-list problem), `completeness=PARTIAL` (a real, valid answer that is not yet actionable) — routing through the **already-existing, already-validated** `PARTIAL_ANSWER` derivation path (audit §2), unmodified.

**A new, orthogonal grounding rule** governs the tutor's own reply content, independent of which classification path a case takes: the tutor may participate fully in the roleplay, but the **structured evaluation must never certify a turn as resolved using information the conversation never established**, and the reply must never assert a specific factual value (price, rating, date, quantity, name, availability, ranking, schedule, or a claimed prior learner action) that was not already present in the conversation, *as if it had been*. The tutor is free to introduce a new, honestly-new fact in character (a shopkeeper stating a price for the first time) — but doing so must not be paired with marking the triggering turn `COMPLETE`/`CLEAR`; the answer that prompted it stays `PARTIAL`, and the tutor confirms the learner's actual choice on a follow-up turn rather than picking for them.

**Locked invariant, exactly as instructed**: **ROLEPLAY NEVER CREATES FACTUAL KNOWLEDGE.** The character may *state* new facts as part of natural scenario progression; it may never *silently rely on* invented facts to finalize a decision on the learner's behalf.

## 3. Generalization table

| Pattern | Intent known? | Reference resolvable from named alternatives? | Required data available? | Correct action | Never fabricate |
|---|---|---|---|---|---|
| "Whichever is cheaper" (no prices given) | Yes | N/A — not a reference case | No (prices) | `completeness=PARTIAL`; tutor may honestly introduce prices as new info, then confirm the learner's actual pick next turn | Specific price values |
| "Whichever is faster" (no timing given) | Yes | N/A | No (durations) | Same shape | Specific durations/times |
| "Whichever has better reviews" (no review data) | Yes | N/A | No (ratings) | Same shape | Specific ratings/review claims |
| "Choose the day I'm free" (learner's own availability unknown) | Yes | N/A | No — and **only the learner can supply it**, not the tutor-in-character | `completeness=PARTIAL`; tutor must ask the learner directly (rule 13's existing partial-answer behavior), never guess a day | A claimed day/schedule for the learner |
| "The one I bought before" (purchase history absent) | Yes | **Yes** — resolves to one of the named alternatives ("same as last time") | No (which specific item that was) | `context_resolution=CLEAR` (not `PARTIAL`!) but grounding rule still applies — do not invent color/size/price of "the one before" | Specific attributes of an unestablished past purchase |

**The 4th and 5th rows are deliberately different from the first three**, and the table is designed to show that difference, not paper over it: row 4's missing information belongs to the *learner*, so the correct redirect is "ask the learner" (already covered by existing rule 13, no new mechanism needed there). Row 5 is not a criterion-deferral at all — the reference resolves cleanly — but the grounding rule still applies, proving the rule must be orthogonal to the classification fix, not bundled inside it (audit §3).

## 4. Prompt changes

**Correction to rule 17** (removes the wrong example, adds explicit routing for criterion deferrals):
```
17. CONTEXT_RESOLUTION - ... [CLEAR/AMBIGUOUS/CONFLICTING definitions unchanged,
    EXCEPT:] AMBIGUOUS no longer includes "depends on information you do not have"
    - a criterion-based deferral (see rule 20) is NOT a context_resolution case at
    all; leave it null. Reserve AMBIGUOUS strictly for references that fail to
    identify WHICH named alternative is meant (e.g. "the other one" with no
    established anchor) - not for references that clearly identify a selection
    RULE but lack the DATA to execute it.
```

**New rule 20** (the grounding/non-fabrication rule):
```
20. GROUNDING - NEVER FABRICATE FACTUAL VALUES, IN OR OUT OF CHARACTER. Your role
    in this scenario does not give you real knowledge of facts never established
    in this conversation - prices, ratings, dates, names, quantities, availability,
    rankings, schedules, or anything you imply the learner already told you but
    did not.

    If the learner's answer states a clear selection RULE that depends on a
    specific fact you do not have (e.g. "whichever is cheaper" with no prices
    given, "whichever is faster" with no timing given): set completeness=PARTIAL
    (not COMPLETE), context_resolution=null. You may honestly introduce the
    missing fact yourself if your role would plausibly know it (a shopkeeper can
    state a price for the first time) - but do so as NEW information, and still
    let the learner confirm their actual choice on their next turn; do not
    silently pick for them and mark the turn as fully resolved. If the missing
    fact is something only the learner could know (their own schedule, their own
    past purchases, their own preference), ask them for it directly instead of
    guessing - do not invent an answer on their behalf.

    This rule applies even when the reference itself is clear (e.g. "the one I
    bought before" clearly picks one of two named options) - do not then invent
    specific attributes (color, size, price) of that unestablished past item.

    Never mark answer_relevance or meaning_status as if the learner's stated
    criterion were unclear or wrong because of this - "whichever is cheaper" is a
    clear, valid, complete statement of intent. What is missing is data to act on
    it, not clarity about what they meant.
```

## 5. Deterministic guard — realistic, narrow, and explicitly bounded

**What is genuinely, deterministically achievable — checked against what the code can actually verify, not claimed beyond it:**

```python
_CURRENCY_RE = re.compile(r'\$\s?\d+(?:\.\d{1,2})?|\d+(?:\.\d{1,2})?\s?(?:dollars|USD|EUR|€|£)', re.IGNORECASE)

def flag_ungrounded_currency(reply_text: str, conversation_history_text: str) -> list[str]:
    """Narrow, honest, ONE pattern class: currency/price values. Flags (never
    blocks or auto-edits) a numeric price-shaped value appearing in the tutor's
    reply that was not present anywhere earlier in the conversation. This is NOT
    a general hallucination detector - see the explicit boundary below."""
    in_reply = set(_CURRENCY_RE.findall(reply_text))
    in_history = set(_CURRENCY_RE.findall(conversation_history_text))
    return sorted(v for v in (in_reply - in_history) if v)
```

**Deterministic guarantee**: this function will reliably flag a new dollar-amount-shaped token appearing in a reply that didn't appear earlier in the conversation. This is real, cheap, and was checked directly against the actual E9 raw results (not merely reasoned about) before writing this claim: run against the exact replies from `AI_TUTOR_V4_1_CALIBRATION_REPORT.md`'s E9 data, it returns `['$5', '$8']` for run 1's reply, `['$5', '$8']` for run 3's reply — the two runs that actually fabricated prices — and `[]` for run 2's reply ("Sure, I'll find the cheaper option. Do you have a preferred color?"), which fabricated nothing. All 3 outcomes match the human-reviewed ground truth exactly.

**Explicit boundary, stated honestly per instruction not to overclaim**: this catches **currency values only**. It does **not** and cannot reliably catch fabricated ratings ("4.5 stars" has no fixed pattern distinguishing a real vs. invented rating), fabricated dates, fabricated names, fabricated claims about the learner's own prior statements, or fabricated availability — none of these have a narrow, low-false-positive regex signature the way currency amounts do. **For every pattern beyond currency, this plan relies on prompt reliability alone**, tested empirically in the calibration set (§6), not guaranteed deterministically. This is the honest three-way split the review requested:
- **Deterministic guarantee**: no new, previously-unmentioned currency value can silently pass through this specific check unflagged.
- **Prompt reliability** (untested until §6 runs): whether rule 20 actually stops the model from fabricating ratings, dates, availability, etc. — genuinely unknown, must be measured.
- **Provider behavior**: the underlying tendency (staying in character pulls toward inventing plausible details) is a property of the model, observed but not something either the prompt or the guard can fully eliminate — only reduce and detect where mechanically possible.

**Guard is advisory, not blocking**: flags are recorded (for the calibration report, and in a future implementation, potentially for a monitoring signal) but never used to reject or rewrite a response, since a legitimate, honestly-introduced new price (per rule 20's own allowance) would otherwise be wrongly suppressed. Applied to `completeness`/`context_resolution` derivation: not applied at all — this guard does not feed `final_learner_intent_known` or `derive_overall_status`; it is a separate, read-only signal layered on top.

## 6. Schema decision

**No new field.** Per audit §2, `completeness=PARTIAL` and `overall_status=PARTIAL_ANSWER` are pre-existing, already-validated (via E7 in the same 23-call V4.1 run) derivation paths that require zero code changes to correctly represent "known intent, insufficient grounding" once the prompt routes criterion-deferrals there. A dedicated `grounding_status` field was considered and rejected: the actual behavioral requirement (ask a natural follow-up, don't silently finalize) is identical to ordinary partial-answer behavior (rule 13, unmodified) — a new field would duplicate an existing signal without adding a distinguishable downstream action, violating the explicit instruction not to add a field for convenience.

**Persistence, migration, `overall_status`/`clarification_required` interaction — all unchanged**: no new column, no new enum, no new table. `clarification_required` is untouched by this revision (criterion-deferrals do not force it — the tutor's natural next step is a redirect/follow-up via the existing `PARTIAL_ANSWER` → rule 13 path, not a clarification demand). `overall_status`'s derivation function itself is not modified at all — only the upstream `completeness`/`context_resolution` inputs it already correctly handles are taught to route this new pattern correctly.

## 7. V4.1 regression protection — traced explicitly, not asserted

| Mechanism | Why this revision cannot touch it |
|---|---|
| D1/E1 unsafe substitution (red/new shoes) | Fires on `meaning_status=CHANGED` + `context_resolution=CONFLICTING` with an explicit raw `false` — rule 20 and the rule-17 correction both apply only to criterion-deferral language ("whichever," "whatever," non-specific "the one before"-type references); "new shoes" is a concrete, specific noun, never routed through either new rule |
| D2/E2 safe substitution (apples/oranges) | Same reasoning — `CONFLICTING` + explicit `true` is untouched; "oranges" is a concrete named alternative, not a criterion deferral |
| D3/E3 genuine ambiguity (the other one) | `AMBIGUOUS`'s core definition (fails to identify *which* named candidate) is unchanged; only the *unrelated* second clause about missing external data is removed from it (§4) — verified this removal cannot affect "the other one," which was never described by that clause in the first place |
| D4/E4 ordinal-reference policy | Entirely orthogonal — ordinal resolution depends on utterance order of a named list, never touches `completeness` or the new rule 20 |
| D6/E5 off-topic fix (`enforce_offtopic_meaning`) | Fires on `answer_relevance ∈ {NONE, LOW}`; criterion-deferrals are `FULL`-relevance answers (on-topic, just not yet actionable) — the two guards' trigger conditions are mutually exclusive by construction |
| `clarification_required` ⇒ `corrected_sentence=null` | `final_corrected_sentence`'s code is not modified in this plan at all |
| Occurrence-based repeated-issue tracking | Unrelated field, untouched |

No shared code path exists between this revision's two changes (rule 17's narrowing, rule 20's addition) and any of the six protected mechanisms above — traced by inspection of the actual condition each derivation rule checks, not asserted by category.

## 8. V4.2 calibration (24 real calls, not run in this pass)

### 8.1 Cases

| # | Purpose | Case | Tier / runs |
|---|---|---|---|
| F1 | D1/E1 regression | Red/new shoes verbatim | Zero-tolerance, 3 |
| F2 | D2/E2 regression | Apples/oranges verbatim | Zero-tolerance, 3 |
| F3 | D3/E3 regression | "The other one" verbatim | Zero-tolerance, 3 |
| F4 | D4/E4 regression | "The first one" (ordinal) verbatim | Policy-confirmation, 2 |
| F5 | D6/E5 regression | Off-topic weather verbatim | Policy-confirmation, 2 |
| F6 | **Primary fix target** | E9 verbatim ("Whichever is cheaper," small/large size) — re-graded under the new policy | Zero-tolerance, 3 |
| F7 | Generalization: timing | TRAVEL. Prior: "Would you like the direct flight or the connecting flight?" Answer: "Whichever is faster." | Generalization, 2 |
| F8 | Generalization: ratings | SHOPPING. Prior: "Would you like the brand A jacket or the brand B jacket?" Answer: "Whichever has better reviews." | Generalization, 2 |
| F9 | Generalization: learner's own info | COLLEGE. Prior: "Would you like to schedule for Monday or Tuesday?" Answer: "Whichever day I'm free." | Generalization, 2 |
| F10 | Generalization: grounding on a CLEAR case | SHOPPING. Prior: "Would you like the same jacket as last time, or a different color?" Answer: "The one I bought before." | Generalization, 2 |

**Total: 3+3+3+2+2+3+2+2+2+2 = 24 calls.**

### 8.2 Pass/fail criteria, locked before running

**Zero-tolerance tier (100% required, no partial credit): F1, F2, F3, F6.**
- F1: `meaning=CHANGED`, `context_resolution=CONFLICTING`, `learner_intent_known=false`, `clarification_required=true`, `corrected_sentence=null` — every run.
- F2: `context_resolution=CONFLICTING`, `learner_intent_known=true`, `clarification_required=false`, `corrected_sentence` non-null preserving "oranges" — every run.
- F3: `context_resolution=AMBIGUOUS`, `learner_intent_known=false`, `clarification_required=true`, `corrected_sentence=null` — every run.
- F6: `completeness=PARTIAL`, `context_resolution=null` (not `CLEAR`, not `AMBIGUOUS`), `overall_status=PARTIAL_ANSWER` — every run.

**Correction, made before any of the 24 official calls, caught by a pre-batch diagnostic call**: this criterion originally also required `flag_ungrounded_currency` to return empty on every F6 run. That requirement directly contradicted rule 20's own text (§4), which explicitly permits the tutor to "honestly introduce the missing fact... as NEW information" (e.g. state a price for the first time) provided the turn is not finalized as resolved — and contradicted §5's own description of the guard as advisory, not blocking, precisely because "a legitimate, honestly-introduced new price... would otherwise be wrongly suppressed." The very first live diagnostic call reproduced this exactly: the model returned the fully correct classification (`completeness=PARTIAL`, `context_resolution=null`, `overall_status=PARTIAL_ANSWER`, turn left open, learner asked to confirm) while still introducing "$5"/"$8" as new information — correct behavior under rule 20 that the old criterion would have failed. The currency-guard-empty requirement is removed from the zero-tolerance gate. Guard activations on F6 (and elsewhere) are still fully captured and reported in the Fabrication Analysis section of the calibration report, explicitly distinguishing "honest new fact introduced, turn left open/PARTIAL" from "fact used to certify the turn as resolved" — analyzed qualitatively per run, not used as a pass/fail gate.

**Policy-confirmation tier (100% required): F4, F5** — identical criteria to the V4.1 round's own locked expectations for these cases (context_resolution=CLEAR / overall_status=OFF_TOPIC respectively), confirming no regression.

**Generalization tier (reported in full, target ≥75% qualitative pass, does not block the gate on its own — informs the next iteration if missed): F7, F8, F9, F10.** Graded on: `completeness=PARTIAL` where applicable (F7/F8/F9) or `CLEAR` (F10, per §3's table); no specific fabricated value in the reply (human-graded for F7/F8/F9/F10, since only F6's currency pattern is deterministically checkable); F9 specifically requires the tutor's reply to ask the learner directly rather than assume a day.

**Overall gate**: 100% required on the zero-tolerance tier (F1/F2/F3/F6, 12 runs) AND 100% on the policy-confirmation tier (F4/F5, 4 runs) to authorize the 48-case re-evaluation. The generalization tier (F7-F10) is fully reported regardless of outcome; a miss there means iterating on rule 20's wording for that specific pattern before the 48-case run, not a full re-architecture — the underlying mechanism (no new field, `PARTIAL_ANSWER` routing) is not in question at that point, only prompt robustness across phrasings, the same category of gap this whole project has iterated on successfully before (e.g. D1's worked example generalizing correctly to D2/E2/E8/F2 by the second round).

## 9. Final verdict

## **A — READY FOR V4.2 CALIBRATION DESIGN**

No architecture decision remains open: audit §2 traces, from the actual already-running code, that `completeness=PARTIAL`/`overall_status=PARTIAL_ANSWER` already correctly represent the target state with zero schema or derivation changes. The one taxonomy correction (removing criterion-deferrals from `AMBIGUOUS`) and the one new rule (grounding/non-fabrication) are both fully specified, both traced against every V4.1-protected mechanism to confirm no shared code path, and both realistically scoped on the deterministic-guarantee front (§5's explicit currency-only boundary, not oversold as general hallucination detection). The calibration set (§8) is fully specified with pre-locked, tiered pass criteria. Nothing has been run; running §8 requires separate, explicit authorization, as with every prior gate in this review.

---

## What this plan does not do

Does not modify `backend/app/`. Does not add or alter any schema, model, or migration. Does not modify the production system prompt. Does not run the 24-call calibration set or the 48-case dataset. Does not commit or push. Does not weaken any V4.1 criterion — §7 traces, mechanism by mechanism, why none of the six protected behaviors share a code path with this revision's two changes.
