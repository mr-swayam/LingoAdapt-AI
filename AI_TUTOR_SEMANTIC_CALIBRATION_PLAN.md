# AI Tutor Semantic Calibration — Revision Plan

Status: **Planning document only. No application code, schema, or migration has been created or modified. No new real-provider API calls were made to produce this document.** This plan is not yet approved for implementation — work stops after this document and its sibling `AI_TUTOR_SEMANTIC_CALIBRATION_AUDIT.md` are written, per explicit instruction. It is gated behind a not-yet-run adversarial calibration test (§7), which is itself gated behind approval to run it.

This plan is written against the audit's verified findings (`AI_TUTOR_SEMANTIC_CALIBRATION_AUDIT.md`), not against assumptions. Every design decision below is defended against a specific finding from that audit or from `AI_TUTOR_REAL_PROVIDER_EVALUATION_REPORT.md`, with the reasoning shown — never asserted as self-evidently correct.

---

## 1. The core design question: is model self-rated confidence the right schema primitive?

**Critically reviewed, per instruction, not assumed.** The original design (`AI_TUTOR_CONVERSATION_INTELLIGENCE_PLAN.md` §3.3/§5.3) asked the model to introspect and self-report *how confident* it is on a 3-tier scale (`CONFIDENT`/`PROBABLE`/`UNCERTAIN`). The audit's §1 finding is decisive: across 48 real calls, including two cases purpose-built to elicit the middle and low tiers, the model used **only** the top tier or `null` — never once the middle or low tier. This is not "under-calibrated," it is "the graded scale was never functionally a 3-way scale in practice, in this data." A self-rated confidence field asks the model a *soft, introspective* question ("how sure am I?") that structured-output generation appears to systematically resolve toward the assertive end — consistent with the well-documented general tendency of instruction-tuned LLMs to prefer completing a task decisively over flagging uncertainty, especially inside a JSON contract that reads as "pick one of these values" rather than "tell me honestly if you don't know."

**Decision: retire `semantic_confidence` as a self-rated confidence field.** Replace it with a primitive that asks an *evidentiary, checkable* question instead of an introspective one: not "how sure are you," but "is there enough information in the learner's literal words to state what they meant, without guessing." This reframes the judgment from calibration (hard for LLMs, evidenced by the real data) to fact-pattern recognition (a task closer to what structured extraction already does reliably elsewhere in this exact pipeline — e.g., the model correctly identifies `meaning_status=CHANGED` on case 16, i.e., it *can* recognize that a substitution occurred; it just cannot reliably rate how sure to be about what to do next).

### Option A — keep `semantic_confidence`, strengthen the prompt wording

*What it does*: adds a concrete worked example to rule 17, anchoring `PROBABLE`/`UNCERTAIN` with the red/new-shoes case itself (this was recommendation #2 in the real-evaluation report).

*Why it is insufficient on its own*: it only addresses **Mode 1** (audit §2) — cases where the model correctly detects a meaning issue but mis-rates its confidence. It does nothing for **Mode 2** — cases 31/33, where the model never recognizes the ambiguity exists at all, so no amount of better confidence-tier wording is ever reached. Even restricted to Mode 1, a stronger example is a plausible but unproven fix for a documented, structural LLM tendency (assert over hedge) — the audit found *zero* instances of the model using the middle tier across 48 real calls, which is a much larger gap than "the wording wasn't specific enough" typically explains on its own.

*Verdict*: **rejected as the primary fix**, though its core idea (a concrete worked negative example in the prompt) is retained and strengthened in the semantic non-invention rule (§3) regardless of which schema primitive is chosen — that part of Option A was sound and is kept.

### Option B — replace with `learner_intent_known: bool` + `clarification_required: bool`

*What it does*: converts the introspective 3-way scale into two binary, evidentiary flags. `learner_intent_known` answers "is there enough evidence in the literal text to safely state what the learner meant" (a fact-pattern question: did a content word change with no explanatory signal — that is answerable more mechanically than "how confident am I"). `clarification_required` is the action-consequence flag, forced deterministically from `learner_intent_known` (§4), matching the same "derive the safety-critical field, don't fully trust one AI-reported bool in isolation" principle the original plan already used for `overall_status` and the confidence-forcing rules.

*Considered and rejected alternative — Option C, a relabeled 3-way evidentiary scale (e.g. `intent_basis: STATED | INFERRED_LOW_RISK | UNKNOWN`)*: this was considered and rejected because it reintroduces exactly the same shape of problem Option A has — a graded categorical judgment the model has to self-calibrate — under a different name. The audit's finding is not that the *labels* `CONFIDENT`/`PROBABLE`/`UNCERTAIN` were poorly worded; it is that a 3-way self-assessed category collapsed to a 2-way one (`CONFIDENT`/`null`) in every real observation. Renaming the tiers does not change that underlying dynamic.

*What is deliberately preserved despite the collapse to boolean*: the ability to **hedge in prose** is not lost. `context_feedback` and `reply` remain free-form and can still say "this might be a typo, I'm not fully sure" — what changes is that this nuance is no longer trusted as a *structured, machine-actionable* signal (nothing downstream — persistence, `corrected_sentence` suppression, `overall_status` derivation — reads a granular confidence enum today, because the real data shows that enum was never actually granular). The boolean governs what is safe to *assert as fact* (a `corrected_sentence`, a persisted `DetectedError`); it does not govern what is sayable in natural language.

**Decision: adopt Option B.** It is the smaller schema (2 booleans, one of which — `requires_clarification`/`clarification_required` — already existed in the original design; only `semantic_confidence`'s 3-value native enum is retired, and no new enum type is added) and the safer one (a boolean is trivially and unambiguously guardable server-side in a way a graded scale that the real model doesn't actually use gradedly cannot be).

## 2. Revised schema

```python
class RawTutorTurn(BaseModel):
    reply: str = Field(min_length=1)
    understood_question: bool
    answer_relevance: str
    completeness: str
    meaning_status: str
    grammar_status: str
    naturalness: str
    learner_intent_known: bool | None = None   # REPLACES semantic_confidence.
        # Meaningful (non-null) only when meaning_status is CHANGED or
        # SLIGHTLY_WRONG - same conditional-nullability contract the old
        # semantic_confidence field had, same reasoning: nothing to assess
        # when meaning was PRESERVED, and UNCLEAR is a distinct, already-
        # "we don't know" state that is forced to False regardless (see §4).
    issues: list[RawTutorIssue] = Field(default_factory=list)
    corrected_sentence: str | None = None
    context_feedback: str | None = None
    clarification_required: bool = False   # renamed from requires_clarification
        # for symmetry with learner_intent_known; same field, same role.
```

`answer_relevance`, `completeness`, `meaning_status`, `grammar_status`, `naturalness` — **unchanged**. `overall_status` — still not requested from the AI, still purely derived (§6). No new field is added beyond what already existed; `semantic_confidence` is removed and `learner_intent_known` takes its structural place (same nullability contract, different value domain).

**Persisted-enum impact (for whenever implementation is eventually authorized — not built now)**: the plan's original migration (`AI_TUTOR_CONVERSATION_INTELLIGENCE_PLAN.md` §8) proposed 7 new native Postgres enum types, one of which was `SemanticConfidence`. Under this revision, that enum type is **retired entirely** — `learner_intent_known` is a plain nullable `BOOLEAN` column, not a new enum. The eventual migration would therefore create **6** new native enum types instead of 7, one fewer than originally planned. This is the only migration-shape change this plan produces; **no migration is created now**.

## 3. Semantic non-invention rules (exact prompt text)

New system-prompt rule, replacing rule 17 in `AI_TUTOR_CONVERSATION_INTELLIGENCE_PLAN.md` §5.4:

```
17. NEVER replace one meaningful content word in the learner's answer with a
    different meaningful content word from your own question merely because
    the replacement would answer your question better. A word is only a
    "typo" of another word if they are visually/phonetically close variants
    of the SAME word (e.g. "recieve"/"receive", "thier"/"their") - if the
    learner's word and your word are two different, unrelated, fully-formed
    words (e.g. you asked about "red" and they wrote "new" - these share no
    root and are not a typo relationship), you do NOT know why they differ.
    Do not silently substitute your word for theirs anywhere, including in
    corrected_sentence. Do not classify this as a spelling, grammar, or any
    other mechanical issue type - it belongs in meaning_status, not issues[].

    When a content word differs like this: set meaning_status=CHANGED (or
    SLIGHTLY_WRONG if the drift is more subtle), set
    learner_intent_known=false, set clarification_required=true, set
    corrected_sentence=null, and ask which one they meant in your reply -
    do not state a specific interpretation as if it were settled.

    MANDATORY WORKED EXAMPLE - study this exactly:
    Question: "Do you like wearing red shoes?"
    Learner:  "no i didnt like wearing new shoes"
    CORRECT:   meaning_status=CHANGED, learner_intent_known=false,
               clarification_required=true, corrected_sentence=null,
               reply asks e.g. "Did you mean red shoes, or do you actually
               mean new shoes?" - the mechanical errors (capitalization,
               missing apostrophe) are still listed in issues[], but no
               corrected_sentence is produced because the meaning itself is
               unresolved.
    WRONG (never do this): corrected_sentence="No, I didn't like wearing
               red shoes." - this fabricates the learner's intent by
               substituting your word for theirs.
    WRONG (never do this): treating "new" as a mishearing/misspelling of
               "red" and listing it as a spelling issue - they are not the
               same word.

    Set learner_intent_known=true only when the literal words the learner
    used are, by themselves, enough to know what they meant without
    guessing - e.g. a real typo/mishearing relationship, a grammatically
    wrong but semantically unambiguous sentence, or an answer that uses
    different but clearly-equivalent phrasing. When meaning_status is
    UNCLEAR (the sentence's own meaning is too vague to assess, e.g. "It
    was something"), learner_intent_known is always false.
```

This directly operationalizes the audit's §4 finding (the one directly-observed invented-intent instance) as a mandatory, concrete, negative example embedded in the prompt itself — not left as an abstract principle the way the original rule 11 was.

## 4. Deterministic forcing rules (revised)

```python
def final_clarification_required(raw_flag: bool, learner_intent_known: bool | None) -> bool:
    return bool(raw_flag) or (learner_intent_known is False)

def final_corrected_sentence(raw_corrected: str | None, learner_intent_known: bool | None) -> str | None:
    if learner_intent_known is False:
        return None
    return raw_corrected

def final_learner_intent_known(raw_value: bool | None, meaning_status: str) -> bool | None:
    # Defensive normalization, mirrors the original plan's meaning-status
    # nullability contract exactly, just for a bool instead of a 3-value enum.
    if meaning_status == "PRESERVED":
        return None       # nothing to assess
    if meaning_status == "UNCLEAR":
        return False       # UNCLEAR already IS "don't know" - force it, don't trust a stray True
    if raw_value is None:
        return False       # CHANGED/SLIGHTLY_WRONG with no value reported -> treat as unknown, never default to True
    return raw_value
```

The last function is new relative to the original design and closes a real gap: the original `semantic_confidence` forcing logic never specified what happens if the AI reports `meaning_status=CHANGED` but omits `semantic_confidence` entirely (a case the original 48-case dataset's own consistency audit found and fixed *in the dataset* — case 15 — but the *production normalization code* never had an equivalent guard). `final_learner_intent_known` makes the missing-value case fail safe (defaults to "not known," never to "known") rather than leaving it to whatever Pydantic's `None` default happens to mean downstream.

## 5. One-span-one-issue rule (exact prompt text) + deterministic guards

**Prompt addition**, new rule alongside rule 17 above:

```
18. Each concrete incorrect span in the learner's message gets its OWN
    separate entry in issues[] - never merge two corrections into one
    entry's suggestion (e.g. if "yes" needs capitalizing AND "i" needs
    capitalizing in the same sentence, that is 2 entries, not 1). If the
    same kind of mistake occurs more than once (e.g. two separate lowercase
    "i" occurrences), report each occurrence as its own entry. The
    "original" field must be the exact short phrase as it literally appears
    in the learner's message - never a phrase you invented or already
    corrected.
```

**Deterministic guards** (pure Python, no AI call, applied to every response after schema validation — the user's instruction to identify which rules are checkable this way, answered explicitly below):

| # | Guard | Deterministic? | Evidence basis |
|---|---|---|---|
| 1 | `corrected_sentence` forced to `null` when `learner_intent_known is False` | **Yes** — pure boolean logic, already the existing forcing-rule pattern (§4) | Directly closes the audit §4 failure |
| 2 | Every `issues[].original` must exist as a case/apostrophe-normalized substring of the learner's actual message; drop (don't persist/render) any entry that fails this check | **Yes** — string containment check | Audit §5: 0 violations observed in 48 real cases, so this is a preventive guard, not a corrective one — stated honestly as such |
| 3 | Deduplicate `issues[]` entries with an identical `(type, original)` pair | **Yes** — set/dict-based dedup | Audit §5: 0 duplicates observed; preventive |
| 4 | For `issues[]` entries typed `SPELLING`/`CAPITALIZATION`/`PUNCTUATION` **only**: reject (do not persist as a `DetectedError`, flag for review instead) if `original` and `suggestion` do not share the same first letter and differ by more than ~40% of the longer word's length (proportional edit distance, not raw count) | **Yes** — string-distance computation | Audit §6: tuned against real data — every genuine spelling fix in the 48-case run stayed ≤33% change with a shared first letter; a dangerous mislabeled substitution like `red`→`new` is 67% change with no shared first letter. **Explicitly scoped to mechanical types only** — never applied to `GRAMMAR`/`TENSE`/`WORD_CHOICE`, which legitimately swap full different words (`go`→`went`, `have`→`has`) as correct behavior |
| 5 | `grammar_status` is deterministically upgraded to `MAJOR_ERRORS` if any `issues[]` entry has `severity` reported as major, regardless of the AI's own top-level `grammar_status` value | **Yes** — pure comparison | Real-evaluation report §7: case 2 reported a major-severity issue alongside `grammar_status=MINOR_ERRORS`, an internal inconsistency nothing in the current design prevents |
| 6 | `overall_status` remains 100% deterministically derived (§6) — never requested from the AI | **Yes** — unchanged from the original design | Audit §8: the derivation logic was never implicated in any failure; only its inputs were wrong |

**Not deterministically checkable, explicitly acknowledged**: whether the model *correctly recognized* that an answer is ambiguous in the first place (Mode 2, audit §2) cannot be verified post-hoc without another semantic judgment — there is no reliable, general, string-level test for "this input was objectively ambiguous." A narrow, optional, explicitly-limited heuristic is worth naming here rather than silently omitting: if the learner's answer is short (under ~4 words) and consists mostly of bare pronouns/demonstratives with no concrete noun (`"it"`, `"that one"`, `"the other one"`) while the prior tutor turn offered two or more named alternatives, flag the response for closer review before trusting `learner_intent_known=true` if the model asserted it. This is a narrow pattern-matcher, not a general solution — proposed here as an optional, disclosed-as-limited supplementary signal, not a claimed fix for Mode 2, which remains primarily a prompt/model problem to be measured (§7), not deterministically guarded against.

## 6. Revised `overall_status` derivation

**Minimal change — a rewire, not a rewrite.** Only Rule 1's input source changes; the rule order and every other rule are untouched, since the audit (§8) found the derivation logic itself was never at fault:

```python
def derive_overall_status(
    *, relevance, completeness, meaning, grammar, clarification_required: bool
) -> OverallStatus:
    # Rule 1 - now keyed off clarification_required (derived from
    # learner_intent_known, §4) instead of the old requires_clarification-
    # or-UNCERTAIN combination. Same semantics: if we can't safely commit to
    # an interpretation, nothing else matters yet.
    if clarification_required:
        return OverallStatus.UNCLEAR
    if meaning == MeaningStatus.UNCLEAR:
        return OverallStatus.UNCLEAR
    if relevance in (AnswerRelevance.NONE, AnswerRelevance.LOW):
        return OverallStatus.OFF_TOPIC
    if meaning == MeaningStatus.CHANGED:
        return OverallStatus.NEEDS_CORRECTION
    if relevance == AnswerRelevance.PARTIAL or completeness != Completeness.COMPLETE:
        return OverallStatus.PARTIAL_ANSWER
    if grammar == GrammarStatus.MAJOR_ERRORS or meaning == MeaningStatus.SLIGHTLY_WRONG:
        return OverallStatus.NEEDS_CORRECTION
    if grammar == GrammarStatus.MINOR_ERRORS:
        return OverallStatus.MINOR_ISSUES
    return OverallStatus.CORRECT
```

Rules 2-7 are byte-for-byte identical to the original plan §5.3. The 20-case boundary-test suite already designed there (§12.1) needs only its inputs relabeled (`requires_clarification`/`semantic_confidence=UNCERTAIN` → `clarification_required`), not redesigned.

## 7. Adversarial calibration set (13 cases)

**Not run in this pass — defined only, per instruction.** Small, bounded, real cost when eventually run (§7.3 estimates it), same "disclosed honestly, not hidden" cost discipline as the original 48-case dataset.

### 7.1 The 13 cases, mapped to the 12 required categories

| # | Category (as requested) | Case | Risk tier |
|---|---|---|---|
| C1 | Red/new shoes (canonical) | Reuse case 16 verbatim: "Do you like wearing red shoes?" → "no i didnt like wearing new shoes" | **HIGH — repeated runs** |
| C2 | Clear spelling correction | Reuse case 4: "What are you looking for today?" → "I need a new jaket" | Low |
| C3 | Grammar correction, meaning preserved | Reuse case 1: "Would you like something to drink?" → "yes i want a coffee" | Low |
| C4 | Partial answer | Reuse case 25 (the other flagship, passed cleanly): "What kind of shoes do you prefer to wear?" → "i dont like wearing red shoes" | Low — regression guard |
| C5 | Off-topic answer | Reuse case 28: "What color do you like?" → "My brother is a doctor." | Medium — targets the relevance/meaning conflation fix |
| C6 | Valid unconventional answer | Reuse case 34: "How's it going?" → "Can't complain!" | Low — regression guard (6/6 passed originally) |
| C7 | Ambiguous intent | Reuse case 31: "Would you like the blue one or the green one?" → "the other one" | **HIGH — repeated runs** |
| C8 | Meaningful word substitution (non-canonical) | New: "Do you like eating apples?" → "no i dont like eating oranges" — a different, unrelated substitution pair, to test generalization beyond the one worked example embedded in the prompt | **HIGH — repeated runs** |
| C9 | Repeated identical mechanical errors | New: "Restaurant. Prior: 'What did you order?' Answer: 'i think i want the soup and i will get water too'" — three separate lowercase "i" occurrences, directly targeting the one-span-one-issue rule under repetition | Medium |
| C10 | Multiple simultaneous errors | Reuse case 43: "What kind of jacket are you looking for?" → "i want a jaket thats waterproof and i dont like the blue ones" | Medium — previously failed enumeration 3/3 times |
| C11 | Contradictory conversation context | Reuse case 40: earlier "I have two brothers," later "Do you have any siblings?" → "No, I'm an only child." | Low — informational, unaffected by this revision |
| C12 | Clarification definitely required | New, deliberately more airtight than C7: "Restaurant. Prior: 'Would you like the chicken or the fish?' Answer: 'the first one'" — genuinely zero disambiguating signal (no context establishing an order), a harder version of C7 | **HIGH — repeated runs** |
| C13 | Off-topic, second independent sample | Reuse case 29-shaped, different domain: "Why should we hire you?" → "The weather is nice today" | Medium — a second, differently-worded sample of the same fix C5 targets, rather than a literal repeat |

### 7.2 Repeated-run requirement for high-risk cases

C1, C7, C8, C12 (the 4 cases directly testing ambiguity-recognition and semantic non-invention) must each be run **N=3 independent real-provider calls**, not once. Justification, directly from the audit (§4): the same real case (16) produced two different outcomes across two real attempts at `temperature=0.4` — a single sample is not sufficient evidence to trust or distrust a fix on cases in this risk class. Total real calls for this calibration test: 9 single-run cases + 4 cases × 3 runs = **21 real API calls**.

### 7.3 Pass/fail criteria, defined before running (per instruction)

**Zero-tolerance tier (must hold on every single run, no exceptions, across all 21 calls):**
- C1, C7, C8, C12: on every one of the 3 runs each, `learner_intent_known` must be `false`, `clarification_required` must be `true`, and `corrected_sentence` must be `null`. **A single violation on a single run, on any of these 4 cases, fails the entire calibration test** — not just that one case.
- Every `issues[].original` across all 21 calls must pass the span-exists-in-input guard (§5, guard 2).
- Zero fabricated/silently-substituted content words anywhere in `corrected_sentence` across all 21 calls (the direct, literal test for the audit §4 failure).

**Standard tier (adjacent-tolerance grading, same style as the original 48-case spec §4), applied to C2-C6, C9-C11, C13:**
- `grammar_status`/`completeness`/`answer_relevance` within one ordinal step of expectation.
- `meaning_status` PRESERVED-vs-not-PRESERVED boundary held exactly.
- C9, C10: full issue enumeration (every expected span present as its own entry) required on **at least 2 of the cases' respective runs** if run more than once, or the single run if not — stricter than the original 48-case run's 0/3 result on this exact criterion, but not requiring literal 100% given real sampling variance.

**Overall calibration-set gate:**
- **100%** pass on the zero-tolerance tier (C1/C7/C8/C12, all runs) — required, no partial credit, matching the original spec's own "non-negotiable" zero-tolerance framing.
- **≥80%** pass on the standard tier (allowing 1-2 misses of 9 cases) — required.
- If either bar is missed: **do not proceed to a full 48-case re-run.** Iterate on the prompt/guards again and re-run only this 13-case, 21-call calibration set (cheap, fast feedback) until both bars are met.

### 7.4 What must pass before re-running all 48 cases

Both gates in §7.3, in full, on a completed calibration-set run. The full 48-case re-run is the expensive, slower confirmation step (§12 of the real-evaluation report: ~11 minutes wall-clock, mostly rate-limit-bound) and should only be spent once the cheap 21-call calibration set already clears both bars — this two-stage structure (cheap targeted gate, then expensive full confirmation) is the direct answer to "what must pass before rerunning all 48 cases."

## 8. Whether this design still requires only one AI call

**Yes — unchanged.** Every guard in §5 and every forcing rule in §4 is pure Python post-processing over the single response already returned by the one existing `provider.chat(...)` call. No guard, rule, or calibration-set case in this plan introduces a second AI call, a re-prompt, or a self-critique pass. This was an explicit constraint on this design and is satisfied structurally, not just claimed: nothing described above has a code path that calls `provider.chat` (or any AI provider method) more than once per learner message.

## 9. What this plan does not do

Does not modify `backend/app/` in any way. Does not add or alter any schema, model, or migration — §2's migration-impact note describes a *future* shape, not a present action. Does not modify the production system prompt in `conversation_ai.py`. Does not run the calibration set defined in §7 — that is the next, separately-gated step. Does not commit or push. Does not claim the calibration-set design is proven; it is a reasoned, evidence-grounded design that itself needs to be run and judged against its own pre-committed criteria (§7.3), exactly as the original 48-case dataset was.

---

## Final status

**NEEDS FURTHER DESIGN WORK is not accurate — the design is complete and evidence-grounded. READY FOR CALIBRATION TEST is not accurate either — nothing has been run yet and this plan explicitly does not authorize running it.**

Stated precisely, since the two offered options don't quite fit without qualification: **READY FOR CALIBRATION TEST, pending explicit authorization to spend the 21 real API calls in §7.2.** The schema revision (§2), prompt rules (§3, §5), deterministic guards (§5), derivation rewire (§6), and calibration-set design with pre-committed pass criteria (§7) are all complete and each is traceable to a specific, verified finding in the audit — no open design questions remain. The only remaining step is executing §7 against the real provider, which — consistent with the same discipline applied to the original 48-case run — should not happen silently as a continuation of this planning pass, but only once explicitly requested, the same way the original evaluation gate required explicit authorization before its 48 real calls were made.
