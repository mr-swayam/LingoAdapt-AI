# AI Tutor V4 Semantic Architecture — Revision Plan

Status: **Planning document only. No application code, schema, or migration has been created or modified. No new real-provider API calls were made.** Gated behind a not-yet-run V4 calibration test (§7), itself gated behind explicit authorization to run it — same discipline as every prior phase of this review.

Written against `AI_TUTOR_V4_SEMANTIC_ARCHITECTURE_AUDIT.md`'s findings. Every design decision below traces to a specific finding in that audit, not to a generic architecture preference.

---

## 1. Root cause of the calibration failure — precise, not a blanket statement

Four distinct root causes, each traced to a specific finding, not one undifferentiated "ambiguity handling is broken":

| Failure | Root cause | Category |
|---|---|---|
| C7, C12 (reference resolution never recognized) | `meaning_status` conflates "content diverged" with "reference unresolved" — the latter has no clean home, and the closest existing value (`UNCLEAR`) is itself shared with a third, different meaning (vague/contentless answers) | **Schema design** |
| C8 (2 of 3 runs) | `meaning_status=CHANGED` is the correct, already-working mechanism (proven by C1's 3/3) — it simply didn't generalize past the one worked example in the prompt | **Prompt design** |
| C7 run 1 (guard let a non-null `corrected_sentence` through) | A priority-ordering bug in deterministic Python normalization code, unrelated to the model or the prompt | **Deterministic guard implementation** (not model, not prompt, not schema taxonomy) |
| C1 (3/3), all standard-tier cases, zero schema-invalid responses across 69 total real calls now made in this review | Not a failure — direct evidence the model *can* execute this class of judgment reliably when the schema/prompt gives it a clean, well-taught target | **(control — confirms the fixes below target real gaps, not a fundamentally incapable model)** |

## 2. Whether the primary issue was prompt, schema, model capability, or a combination

**A combination — but a specific, traceable one, not a shrug.** Two of the three real failure classes (C7/C12, C1-vs-C8) are structurally different problems requiring different fixes (schema taxonomy vs. prompt reasoning procedure); the third (the guard bug) is neither a prompt nor a model problem at all. **No evidence in either the original 48-case run or this calibration run points at model incapability** — every case the model was given a well-taught, unambiguous target for, it hit reliably (C1: 3/3; the zero-fabrication category from the original run: 3/3; zero schema-validation failures across 69 real calls total). The failures are best explained as: the schema asked one field to answer two different questions, and the prompt taught one example instead of one rule. Both are fixable without assuming the model needs to be replaced (§8).

## 3. Recommended minimal schema

### 3.1 New field: `context_resolution`

```python
class RawTutorTurn(BaseModel):
    ...
    meaning_status: str              # UNCHANGED - still PRESERVED | SLIGHTLY_WRONG | CHANGED | UNCLEAR
    context_resolution: str | None = None   # NEW
    ...

# Normalized enum:
class ContextResolution(enum.StrEnum):
    CLEAR = "CLEAR"
    AMBIGUOUS = "AMBIGUOUS"
    CONFLICTING = "CONFLICTING"
# null = "no reference-dependent language in this answer" - the majority case,
# same nullable-when-not-applicable convention already used for
# learner_intent_known and (in the original design) semantic_confidence,
# deliberately NOT a 4th explicit "NOT_APPLICABLE" member (smallest design:
# null already means this everywhere else in this schema; adding a 4th
# member would be a redundant second way to say the same thing).
```

**What failure this fixes**: C7, C12, and — per audit §5 — the original run's cases 31/33, all of which needed to express "this answer's meaning depends on an external reference that cannot be resolved" as a fact independent of `meaning_status`'s existing job.

**Why an existing field cannot represent it**: `meaning_status=UNCLEAR` was the closest fit and is retained (audit §1) for genuinely vague/contentless answers ("It was something") — a different phenomenon from an *unresolved pointer* to named alternatives ("the other one"). Collapsing both into one value is the exact overload this revision removes; keeping them separate means each field asks one question, matching the precedent already set once in this project (splitting `Completeness` out of `AnswerRelevance` for the identical reason).

**Required in the raw AI schema**: yes — this is a judgment only the model can make (whether a reference resolves), not a deterministic derivation.

**Must it be persisted**: **yes**, on `ConversationTurnEvaluation`, as a new nullable native-enum column. Justification, per instruction to state one explicitly: it is a typed, bounded-cardinality, directly queryable signal with a plausible future consumer of exactly the kind already used to justify every other persisted field in this design (e.g. a future "you often give ambiguous references — try naming what you mean specifically" trend note, or a Mistake-Notebook-style pattern query "how often does this learner's context resolve cleanly vs. not") — matching the original plan §3.4's Category-A reasoning exactly, not a new justification invented for this field alone.

**Mistake Notebook / analytics impact**: same shape as `answer_relevance`/`completeness` already have — none automatically (V3.3's `mistake_service.py` is not modified by this plan, per the original plan's explicit scope boundary, restated unchanged here), but the column exists and is queryable for a future, separately-approved extension, same as every other typed field in this table.

**Migration implications**: one new native Postgres enum type (3 values). See §6 for the full, precise accounting across all three plan revisions.

### 3.2 `learner_intent_known` — retained as boolean, now fed by two upstream signals

**Retained, not reverted to a graded scale.** The audit's core instruction ("the system must not treat model confidence as a substitute for evidence") is exactly the reasoning that already retired `semantic_confidence` in the V3 calibration plan, and nothing in this calibration run's results argues for undoing that — C1's clean 3/3 pass is direct evidence the boolean, evidentiary framing works when the upstream judgment feeding it is correct. What changes is that `learner_intent_known` is now downstream of **two** independent diagnostic fields instead of one: `meaning_status` (content divergence) and `context_resolution` (reference resolvability) — see §4's exact derivation.

### 3.3 Issue-occurrence representation: `occurrence`, not raw character offsets

**Two options considered:**

*Option 1 — raw `start`/`end` character offsets*, as the authorizing request suggested. Rejected as the primary mechanism: producing exact character indices into a string is a well-documented weak point for LLMs (tokenization does not align with character positions, and the calibration/evaluation data gives no evidence this model was ever asked to do this reliably) — an offset-based guard would likely reject a large fraction of genuinely correct identifications due to off-by-a-few-characters errors, trading a real problem (undercounted repeats) for a new one (spuriously rejected valid corrections).

*Option 2 — a small integer `occurrence` field, recommended*:
```python
class RawTutorIssue(BaseModel):
    type: str
    original: str
    occurrence: int = 1   # NEW - 1st, 2nd, 3rd... literal occurrence of `original`
                           # within the learner's message, when it appears more than once.
    suggestion: str
    explanation: str
    severity: str
```
The model only has to count "is this the first or second time this exact phrase appears" — a task LLMs handle far more reliably than exact character arithmetic. The deterministic guard then computes the actual character span itself, in pure Python, using `original` + `occurrence` (e.g. `[m.start() for m in re.finditer(re.escape(normalize(original)), normalize(learner_text))][occurrence - 1]`) — this gets the same precision the offset approach was reaching for (exact positional identity, so two entries with the same `(type, original)` but different `occurrence` are provably two real spans, not a duplicate) without asking the model to do the part it is unreliable at.

**What failure this fixes**: C9 (3 expected lowercase-"i" occurrences, only 1 survived the old dedupe guard because the schema had no way to tell 3 genuine repeats from 1 accidental triplicate) and C10/original-case-43 (an identical, second occurrence of "i" silently dropped).

**Why an existing field cannot represent it**: `original` alone identifies *which phrase*, never *which instance* of that phrase — this was the audit's own direct finding (calibration report §9).

**Required in the raw AI schema**: yes — only the model knows which occurrence it's flagging as it reads through the sentence; the guard cannot invent this after the fact without re-reading with its own (separate, out-of-scope-here) matching logic that would itself need to guess at model intent.

**Must it be persisted**: **no.** `occurrence` is a normalization-time disambiguation aid only — once the deterministic guard has used it to validate span identity and correctly deduplicate, each surviving issue becomes exactly the `DetectedError` row it already would have (original/corrected/explanation/skill/created_at), with no consumer ever needing to know "this was occurrence #2." Not added to `TutorIssueOut` (the API response), not added to any table. This keeps the migration footprint at zero for this specific field.

**Migration implications**: none.

### 3.4 What is deliberately NOT added

- No new field for "the model's free-text reasoning disagreed with its structured field" (the C8 finding) — per audit §4, this is a prompt-generalization gap, not a missing-dimension gap; adding a field to paper over it would treat a symptom, not the cause.
- No separate field for cross-turn contradiction beyond folding it into `context_resolution=CONFLICTING` (audit §2) — a dedicated `contradiction_detected: bool` was considered and rejected as redundant with a value `context_resolution` already needs to have for other reasons.
- No 4th explicit `context_resolution` value (`NOT_APPLICABLE`) — null already means this throughout the rest of the schema (§3.1).

## 4. Deterministic guard precedence rules (fixes the C7-run-1 bug directly)

**One explicit, ordered pipeline. Each step consumes only the outputs of the steps before it — never a raw field a later step has already superseded.**

```python
def final_learner_intent_known(raw_intent_known, meaning_status, context_resolution):
    # Rule 1 - HIGHEST PRIORITY, unconditional. An explicit raw False is
    # never overridden by anything else, including meaning_status. This is
    # the exact fix for the C7 run-1 bug: the old code checked
    # meaning_status FIRST and never reached this branch.
    if raw_intent_known is False:
        return False

    # Rule 2 - a genuinely unresolved or conflicting reference means intent
    # cannot be safely known, regardless of what meaning_status says
    # (defensive, mirrors the old UNCLEAR-forces-false pattern).
    if context_resolution in ("AMBIGUOUS", "CONFLICTING"):
        return False

    # Rule 3 - vague/contentless answers (meaning_status=UNCLEAR) - same
    # defensive force as the V3 design.
    if meaning_status == "UNCLEAR":
        return False

    # Rule 4 - nothing to assess.
    if meaning_status == "PRESERVED" and context_resolution in (None, "CLEAR"):
        return None

    # Rule 5 - meaning changed/slightly-wrong but the model didn't report a
    # value at all - fail safe, never default to True (closes the same gap
    # V3's plan already fixed once for the original dataset's case 15).
    if raw_intent_known is None and meaning_status in ("CHANGED", "SLIGHTLY_WRONG"):
        return False

    # Rule 6 - only reachable when raw_intent_known is True and nothing
    # above forced a safer answer.
    return raw_intent_known


def final_clarification_required(raw_flag, learner_intent_known):
    return bool(raw_flag) or (learner_intent_known is False)


def final_corrected_sentence(raw_corrected, clarification_required):
    # KEYED OFF clarification_required DIRECTLY - not off
    # learner_intent_known specifically. This is requirement #2 and #3 from
    # the authorizing request: ANY reason clarification_required became
    # true nulls this out, full stop, and this is the LAST step in the
    # pipeline that ever touches corrected_sentence - no code downstream of
    # this function may reassign it (a structural/ordering invariant, not
    # just a runtime check: the normalization module calls this function
    # exactly once, as its final line touching this field).
    if clarification_required:
        return None
    return raw_corrected
```

**Verifying this closes the exact C7 run-1 case**: raw `learner_intent_known=false`, raw `meaning_status=PRESERVED`. Rule 1 fires immediately (`raw_intent_known is False`) → `final=False`, before `meaning_status` is ever consulted. `final_clarification_required` → `True` (via the `learner_intent_known is False` branch, independent of whatever the raw flag said). `final_corrected_sentence` → keyed off `clarification_required=True` → `None`. All three of the authorizing request's required guarantees hold on this exact input.

## 5. Revised `overall_status` derivation

**Unchanged in structure, `clarification_required` remains the sole input to Rule 1** — exactly as the V3 calibration plan already established (§6 of that plan). `context_resolution` does not feed `derive_overall_status` directly; it feeds `learner_intent_known` (§4, Rule 2), which feeds `clarification_required`, which is the only input `derive_overall_status` needs. No new rule is added to the derivation function itself — this is a rewire of its upstream inputs, not a second rewrite of the function (matching the same minimal-change discipline the V3 plan already applied once).

## 6. Exact migration implications (assessed, not created)

| Item | Original plan | V3 calibration plan | V4 (this plan) |
|---|---|---|---|
| `DetectedError.corrected_text` | New nullable `TEXT` column | unchanged | unchanged |
| New table `conversation_turn_evaluations` | proposed | unchanged shape | unchanged shape, **+1 new column** (`context_resolution`) |
| `semantic_confidence` column/enum | proposed (7th enum) | **retired** | stays retired |
| `learner_intent_known` column | n/a | new nullable `BOOLEAN` (no enum) | unchanged |
| `context_resolution` column/enum | n/a | n/a | **new nullable native enum, 3 values** |
| `issues[].occurrence` | n/a | n/a | **not persisted** (§3.3) — zero migration impact |
| Total new native enum types | 7 | 6 | **7** — net unchanged vs. the original plan; the 7th slot is `ContextResolution` instead of `SemanticConfidence`, not a re-addition of the retired one |

**No migration is created now.** This table exists so that whenever implementation is eventually authorized, the actual Alembic revision's shape is already fully specified and requires no further design decisions.

## 7. Calibration redesign (19 real calls, not run in this pass)

### 7.1 The 9 required categories, mapped to specific cases

| # | Category (as required) | Case | Risk / runs |
|---|---|---|---|
| D1 | Canonical red/new shoes | Reuse C1 verbatim — reconfirms the guard fix doesn't regress the one case that already worked | **HIGH, 3 runs** |
| D2 | Meaningful-word substitution, different words | Reuse C8 verbatim (apples/oranges) — direct regression test of the specific documented failure, not a fresh pair (keeps this round focused; a fresh pair is a natural follow-up only if D2 passes) | **HIGH, 3 runs** |
| D3 | Ambiguous reference, two prior alternatives | Reuse C7 verbatim (blue/green shoes) | **HIGH, 3 runs** |
| D4 | Ambiguous reference, different wording | Reuse C12 verbatim (chicken/fish) | **HIGH, 3 runs** |
| D5 | Clear reference to one unambiguous prior alternative | New: SHOPPING. Prior: "We have this jacket in blue. Would you like it?" Answer: "Yes, I'll take it." — tests that `context_resolution=CLEAR` is actually reachable and that the new field doesn't over-trigger `AMBIGUOUS` on legitimately unambiguous pronoun use | Medium (new-field false-positive risk), **2 runs** |
| D6 | Off-topic but grammatically correct | Reuse C13 (JOB_INTERVIEW, "why should we hire you" → "The weather is nice today") | Standard, 1 run |
| D7 | Valid unconventional answer | Reuse C6 ("Can't complain!") — also re-checks the mild, unexplained regression noted in the prior report | Standard, 1 run |
| D8 | Multiple repeated identical error spans | Reuse C9 ("i think i want the soup and i will get water too") — the direct test of the new `occurrence` field | Medium (new-field reliability), **2 runs** |
| D9 | Multiple different mechanical errors | Reuse C10 (jacket case) — regression guard; the cross-type bundling fix already confirmed working, this checks it still holds | Standard, 1 run |

**Total: 4×3 + 2×2 + 3×1 = 12 + 4 + 3 = 19 real calls.**

### 7.2 Repeated-run requirement

D1-D4 (the four cases directly testing semantic ambiguity/substitution — the "high-risk contextual cases" named in the authorizing request) each require **3 independent runs**, same justification and same independence guarantees as the V3 calibration run (fresh request per run, no prior response fed forward, run number recorded separately). D5 and D8 — both testing a brand-new field/mechanism for the first time — get 2 runs each as a lighter-weight reliability check, since a single sample cannot distinguish "this field works" from "this field happened to work once."

### 7.3 Pass/fail criteria, defined before running

**Zero-tolerance tier (100% required, no partial credit, across every run of D1-D4):**
- D1, D2 (word-substitution cases): `meaning_status=CHANGED`, `learner_intent_known=false`, `clarification_required=true`, `corrected_sentence=null` on every run.
- D3, D4 (reference-ambiguity cases): `context_resolution=AMBIGUOUS`, `learner_intent_known=false`, `clarification_required=true`, `corrected_sentence=null` on every run. **This is the direct test of whether splitting the taxonomy actually fixes what `meaning_status=UNCLEAR` alone did not** — D3/D4 are the two cases that failed most (C7: 2/3, C12: 3/3) under the old single-field design.
- Every `issues[].original` must pass the span-exists-in-input guard on every run (unchanged from V3).

**Watch tier (reported, not gating — first real data on new mechanisms):**
- D5: `context_resolution=CLEAR` (not `AMBIGUOUS`) on both runs — failing this doesn't block the gate on its own but is reported prominently, since a new field that immediately over-triggers false positives is a worse outcome than the problem it was built to fix.
- D8: full 3-occurrence enumeration (`occurrence=1,2,3` distinctly represented) on at least 1 of 2 runs.

**Standard tier**: D6, D7, D9 graded with the same adjacent-tolerance rules as every prior round; ≥2 of 3 must pass cleanly.

**Overall gate**: 100% on the zero-tolerance tier is required to authorize the next step (which, per the original plan's own §15, is still the full 48-case re-run — this 19-call set is a cheap pre-check, not a replacement for it). Anything short of 100% on D1-D4 means iterate on this same 19-call set again, not spend the 48-case budget.

## 8. Is the currently configured model (Groq `openai/gpt-oss-120b`) still worth testing after this revision?

**Yes, provisionally — but this conclusion is itself an empirical claim that must be re-verified by running §7, not asserted and trusted.** The reasoning: every failure traced in §1-2 has an identified, non-model-capability cause (a schema overload, a prompt-generalization gap, a Python ordering bug), and the model's own behavior on well-specified targets (C1's clean 3/3, zero schema-invalid responses across 69 real calls spanning two full rounds, zero fabricated corrections on any clean-input case in either round) shows no sign of a capability ceiling being hit. Swapping models now, before testing whether the identified fixes work, would spend real cost to answer a question this plan already has a cheaper, more direct way to answer: run §7 first.

---

## Final status

**READY FOR V4 CALIBRATION DESIGN.**

The schema revision (§3), deterministic guard precedence (§4), derivation rewire (§5), and migration accounting (§6) are complete, each traced to a specific audited finding, with no open design questions. The calibration set (§7) is fully specified with pre-committed pass criteria. Nothing has been run. As with every prior gate in this review, running §7 requires separate, explicit authorization — this plan does not request or assume it.

---

## What this plan does not do

Does not modify `backend/app/`. Does not add or alter any schema, model, or migration — §6 describes a future shape only. Does not modify the production system prompt. Does not run the 19-call calibration set or the 48-case dataset. Does not commit or push.
