# AI Tutor V4 Semantic Architecture — Audit

Status: **Audit only. No production code, migrations, commits, or pushes. No new real-provider API calls were made.** Every claim below is a re-derivation from `AI_TUTOR_SEMANTIC_CALIBRATION_REPORT.md` and its underlying raw-results JSON (already collected in the prior calibration run), examined specifically through the question this review raised: is `meaning_status` overloaded, and if so, along exactly which fault line?

Purpose: before designing a V4 schema, this audit separates the calibration run's 7 failing runs into their *actual* distinct root causes — not "ambiguity handling is broken" as one undifferentiated finding, but a precise map of which failures share a mechanism and which don't. Getting this wrong risks adding a field that fixes the wrong problem (e.g., a `context_resolution` field that doesn't touch the apples/oranges case at all, if that case turns out not to be a reference-resolution problem).

---

## 1. Is `meaning_status` overloaded? Yes — but not uniformly across all 7 failures

Re-examining the 7 failing runs (C7 runs 1-2, C8 runs 1-2, C12 runs 1-3) against the specific linguistic phenomenon each one involves, two genuinely different failure shapes emerge, not one:

**Shape A — reference resolution (C7, C12).** "the other one" and "the first one" are not, by themselves, statements with independent content. Their entire meaning is a pointer into the prior turn ("the blue one or the green one," "the chicken or the fish") — resolving what was said requires resolving *which* named alternative the pointer selects, and in both cases the literal words give no basis for choosing. This is a **coreference/anaphora problem**: the answer's meaning cannot even be evaluated for "changed or preserved" until a referent is picked, and no referent can safely be picked from the words alone. `meaning_status`'s existing `UNCLEAR` value was the closest fit for this, but the calibration data (C7: 1/3 uses of `UNCLEAR`; C12: 0/3) shows it did not reliably fire here.

**Shape B — content-word divergence, no reference to resolve (C1, C8).** "new shoes" and "oranges" are not pointers — they are complete, independently-meaningful nouns. There is nothing to *resolve*; the words already say exactly what they say. The open question is not "what does this refer to," it is "does this specific, well-defined word match what was contextually expected, and if not, why." This is the same phenomenon `meaning_status=CHANGED` was built for, and it **worked correctly on C1 (3/3)** — proving the field itself is adequate for this shape. C8's failure (2/3 runs reporting `PRESERVED`) is therefore not evidence that a dimension is missing; it is evidence that the *existing* `CHANGED` judgment did not generalize past the one worked example embedded in the prompt (§4 below).

**Conclusion, stated precisely rather than as a blanket claim**: `meaning_status` is overloaded specifically between "does the content diverge from expectation" (Shape B — already has a working mechanism, `CHANGED`/`SLIGHTLY_WRONG`) and "can the answer's content even be determined without resolving an external pointer" (Shape A — nominally covered by `UNCLEAR`, but that value is doing double duty as both "genuinely vague/contentless" *and* "specific but unresolved reference," two different things). Adding a dimension is the right fix for Shape A. It is not the fix for Shape B's C8 failure, which is a prompt-generalization problem (§4) wearing the same symptom.

## 2. A third shape, already named in the original 48-case dataset, that the new dimension should also capture: cross-turn conflict

The original evaluation's contradiction category (cases 40-42, this calibration's C11) is neither Shape A nor Shape B: the answer's own meaning is perfectly resolvable and perfectly clear ("No, I'm an only child.") — the problem is that it conflicts with an already-established fact from earlier in the same conversation ("I have two brothers."). This has always existed in the dataset as "informational only... this plan does not add [a schema field for it]" (original plan §5.3, §2.14's own note) precisely because there was no natural home for it. It is a third distinct shape — **not** a reference-resolution problem (nothing is ambiguous or unresolved) and **not** a simple content-divergence problem (there is no "expected" single answer to diverge from within the current turn alone) — that a genuinely general "does external context change how safely we can trust this answer" dimension should now be able to hold, rather than remaining permanently unscored. C11's own real result (the model *did* notice the contradiction, 1/1, versus 0/3 in the original dataset) is too small a sample to trust, but it is evidence the underlying capability may already exist and simply has nowhere structured to land.

## 3. The deterministic-guard bug (C7 run 1), restated precisely as an input to the V4 fix

Already documented in `AI_TUTOR_SEMANTIC_CALIBRATION_REPORT.md` §7; restated here with the exact mechanism isolated, since V4's guard redesign must close precisely this gap and no other:

The V3 calibration guard computed `final_learner_intent_known` with `meaning_status` checked **before** the model's own raw `learner_intent_known` flag:
```
if meaning_status == "PRESERVED": return None   # <- checked FIRST
...
return raw_value                                 # <- raw False never reached here
```
C7 run 1's raw output was `meaning_status: PRESERVED`, `learner_intent_known: false` (explicit) — an internally self-contradictory raw response. Because the `PRESERVED` branch fired first, the explicit `false` was discarded, and `final_corrected_sentence` (keyed only off `learner_intent_known is False`, not off `clarification_required`) let a non-null `corrected_sentence` through despite `clarification_required=true`. **This is a pure ordering bug in the guard's own priority list, not a model or prompt failure** — it occurred entirely in deterministic Python, after the AI call returned, and would have produced the wrong result regardless of what the model had said, given this exact combination of raw fields. V4's guard redesign (sibling plan document §3) fixes this by making an explicit raw `false` the first, unconditional check in the priority order, and by keying `corrected_sentence` nullification off `clarification_required` directly rather than off `learner_intent_known` specifically.

## 4. Why the C8 prompt-generalization gap is a reasoning-procedure problem, not a missing-field problem

C8's two failing runs both produced a `context_feedback` string that correctly named the mismatch ("you mentioned oranges instead of apples," "You answered about oranges instead of the asked apples") while the structured `meaning_status` field, in the same response, read `PRESERVED`. **The model's free-text reasoning found the answer; its structured commitment did not reflect it.** No field was absent — `meaning_status=CHANGED` exists and is exactly the right value; the model simply didn't apply it here. This rules out "the schema needs a new field to capture apples/oranges" and points instead at *how* the prompt asks the model to arrive at `meaning_status`: the current prompt gives one fully-worked example (red/new shoes) and states the rule abstractly around it. C1 (the literal worked case) passed 3/3; every differently-worded instance of the identical underlying judgment (C8, and the original 48-case run's cases 17/28/29, which showed the same relevance/meaning-field misrouting in a different but related way) failed at meaningfully worse rates. The evidence points at the prompt teaching *the example* more effectively than *the rule*.

## 5. Smallest-correct-taxonomy analysis for a new context-resolution dimension

Tested against every case in both the original 48-case dataset and the 13-case calibration set to check for a value this taxonomy would need but doesn't have, and for a value it has but never gets used:

| Value | What it captures | Evidenced by |
|---|---|---|
| `null` (not `NOT_APPLICABLE` as an explicit member — see plan §2 for why) | The answer contains no reference-dependent language at all — the overwhelming majority of cases (41 of 48 original cases; 9 of 13 calibration cases contain no pronoun/demonstrative/ordinal referring to a named prior alternative) | Every grammar-only, spelling, off-topic, opinion, and valid-alternative case |
| `CLEAR` | Reference-dependent language present, resolves to exactly one candidate | Not directly evidenced by any *existing* case — flagged in the plan as a genuine coverage gap the V4 calibration set must add (plan §7, case D5), since a dimension with no case ever expected to produce one of its values cannot be trusted to avoid false-triggering |
| `AMBIGUOUS` | Reference-dependent language present, resolves to 2+ candidates or 0 candidates where one was structurally expected | C7 (blue/green), C12 (chicken/fish), and the original run's cases 31/33 (which also showed `meaning_status` failing to register the ambiguity) |
| `CONFLICTING` | The answer's own resolvable meaning contradicts an earlier-established fact in the same conversation | C11 / the original run's cases 40-42 |

**Four candidate states, three real (non-null) values plus the implicit majority-case null — checked against the instruction not to assume the exact members are final.** A fifth candidate was considered and rejected: a separate state for "reference-dependent language present, but the *referent itself* is also mid-conversation-ambiguous due to a contradiction" (a combination of `AMBIGUOUS` and `CONFLICTING`) — no case in either dataset exhibits this combination, and inventing a value with zero evidenced need would violate the smallest-possible-design instruction.

## 6. What this audit does not do

Does not propose exact field names, prompt text, or a final calibration set — that is `AI_TUTOR_V4_SEMANTIC_ARCHITECTURE_PLAN.md`'s job. Does not make any new real-provider API call. Does not modify `backend/app/`, add a migration, or commit/push. Does not re-run the 48-case evaluation.
