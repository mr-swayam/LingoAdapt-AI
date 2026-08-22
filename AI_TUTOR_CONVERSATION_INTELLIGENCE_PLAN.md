# AI Tutor Conversation Intelligence — Implementation Plan

Status: **Planning document only. No application code, schema, or migration has been created.** This plan is not yet approved for implementation - per explicit instruction, work stops after this document and `AI_TUTOR_CONVERSATION_INTELLIGENCE_AUDIT.md` are written and internally verified for consistency.

This plan is written against the audit's findings, not against assumptions. Every "current" claim below is the audit's already-verified finding; every "proposed" claim is a design decision made here, for the first time, with its reasoning shown.

---

## 0. Revision 2 — pre-implementation architecture review

This plan was critically re-reviewed before implementation, against four specific concerns. No code was written to produce this revision - every fix below is a change to this document only. Nothing here was assumed correct just because it was already written down; each concern below is worked through from scratch against the concrete schema, not defended.

**1. `conversation_turn_evaluations` was at real risk of becoming an AI dump table.** The original design (§3.2, v1) included `context_feedback: Text` and `corrected_sentence: Text` - free AI prose, persisted per turn, with no proven downstream consumer (nothing was ever going to run a structured query against a prose column). *Revised*: both fields are removed from persistence entirely and kept API-response-only (ephemeral, rendered for that turn, never stored). Only typed, enum-shaped, queryable columns remain in the table. Full reasoning and the resulting field-by-field ownership table are in §3.2 and the new §3.4.

**2. "Completeness" was silently conflated with "relevance."** The v1 schema used `answer_relevance=PARTIAL` to mean both "off-topic-ish" and "on-topic but didn't fully answer" - two different facts (an answer can be 100% on-topic and still incomplete, e.g. "I like shoes" for "what *kind* of shoes"). *Revised*: `completeness` is now a genuinely separate field (`COMPLETE | PARTIAL | MINIMAL`), and `overall_status`'s derivation is now an explicit, priority-ordered rule list (not an ad hoc if-chain) with every conflict case named in the review worked through by hand. See §5.3.

**3. Ambiguity handling had no confidence signal.** The v1 schema had only a binary `requires_clarification` - not enough to distinguish "I'm confident this is a mistake" from "this is probably a mismatch, worth a soft note" from "I genuinely can't tell." *Revised*: a new, nullable `semantic_confidence` field (`CONFIDENT | PROBABLE | UNCERTAIN`, only meaningful when `meaning_status` indicates a possible issue) is added, and `requires_clarification`'s *final* value is deterministically forced to `true` whenever `semantic_confidence=UNCERTAIN`, regardless of what the AI separately reported for that flag - the same "derive the safety-critical field, don't fully trust one AI-reported bool" principle already applied to `overall_status`. See §5.1-5.3.

**4. No evaluation dataset existed to test the real model before implementation.** `AI_TUTOR_SEMANTIC_EVALUATION_SPEC.md` (new, sibling document) defines a 48-case dataset with expected values per dimension and explicit, honest pass/fail criteria per category - including a zero-tolerance bar specifically for the "confidently wrong" failure mode this whole task started from. This must be run against the real configured provider before implementation is treated as approved - see §15.

---

## 1. Current architecture (recap)

One AI call per learner message (`conversation_ai.generate_turn`), producing `{reply, corrections[]}` where `corrections[]` is a flat list of `{original, corrected, explanation, skill}`. Persisted as two `ConversationMessage` rows plus, per correction, one `DetectedError` + one `CONVERSATION_CORRECTION` `LearningEvent`. No relevance, meaning, completeness, tense-appropriateness, or naturalness dimension exists anywhere in the schema, the prompt, the persistence layer, or the UI. Full detail in the audit, §1-4.

## 2. Proposed architecture

```
Learner message
      ↓
Validation (unchanged - SendMessageRequest, 1-2000 chars)
      ↓
Ownership + active-conversation check (unchanged)
      ↓
Learner context (unchanged - learner_context.build_learner_context)
      ↓
ONE AI call (conversation_ai.generate_turn - same function, richer prompt + schema)
      ↓
Raw JSON parsed + validated against RawTutorTurn (new, larger schema - see §6)
      ↓
Normalized (TutorTurn.from_raw):
  - overall_status DERIVED deterministically in Python via the precedence rules (§5.3),
    not asked of the AI directly
  - requires_clarification's FINAL value deterministically forced to true whenever
    semantic_confidence=UNCERTAIN, regardless of the AI's own raw flag (§5.3)
  - each issue's skill keyword-normalized exactly as today, only for issue types that
    map to a real curriculum skill
      ↓
Persistence (only after the AI call succeeds - unchanged ordering guarantee):
  - ConversationMessage × 2 (unchanged) - the ONLY place learner/tutor text itself lives
  - Mechanical issues (GRAMMAR/SPELLING/CAPITALIZATION/PUNCTUATION/TENSE/WORD_CHOICE/
    VOCABULARY) → DetectedError + LearningEvent, exactly the existing pipeline,
    now also populating the new DetectedError.corrected_text column (§3.1)
  - The whole-turn evaluation - ONLY typed/enum fields: overall_status, answer_relevance,
    completeness, meaning_status, grammar_status, naturalness, semantic_confidence,
    requires_clarification → one new ConversationTurnEvaluation row (§3.2), only when
    there is something non-trivial to record (see §4 for the exact "when" rule).
    context_feedback and corrected_sentence are NOT persisted here (§3.4) - ephemeral,
    API-response-only, rendered for that turn and gone.
      ↓
Frontend rendering (new structured panel - §7) - a single response body carries
everything the UI needs; still one round trip, still one AI call
      ↓
Next tutor message = turn.reply, now written under an explicit prompt instruction to
be grounded in the same turn's evaluation (§5.4, rule 16) rather than a disconnected next line
```

**No new AI call is introduced anywhere in this diagram.** Voice messages still transcribe (existing, necessary, separate STT call) then call the same upgraded `send_message`.

---

## 3. Schema changes

Two additive changes, both nullable/new, neither touching an existing column's meaning:

### 3.1 `DetectedError.corrected_text: Mapped[str | None] = mapped_column(Text, nullable=True)`

Closes the exact gap this session's V3 work already found and deliberately deferred (`V3_REVISED_IMPLEMENTATION_PLAN.md` revision item 7: "a `DetectedError.corrected_text` nullable column would let new AI-tutor corrections persist the AI's `corrected` field... existing historical rows would remain NULL, never backfilled or invented"). This plan proposes actually building that now, since this task is already touching every write path that would populate it. Historical rows (every `DetectedError` created before this ships) stay `NULL` - never backfilled, matching the same principle applied everywhere else this session. Once built, this closes the "Mistake Notebook always shows `correct_text: null` for TUTOR-source mistakes" limitation documented in `V3_IMPLEMENTATION_REPORT.md` §8 - but only prospectively, for corrections recorded after the change ships.

Also used by SHORT_ANSWER exercise grading (`ai_grading.py`'s `evaluation_repository.record_detected_error` call) - that call site would simply keep passing `corrected_text=None` unless a follow-up decision is made to also populate it there (out of scope here; SHORT_ANSWER already has its own `corrected_answer` on the `ExerciseAttempt`/`PracticeQuestion` row, so it doesn't have the same gap the tutor path has).

### 3.2 New table: `conversation_turn_evaluations`

```python
class ConversationTurnEvaluation(Base):
    __tablename__ = "conversation_turn_evaluations"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # 1:1 with the LEARNER ConversationMessage this evaluation is about.
    conversation_message_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("conversation_messages.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    # Denormalized for direct user-scoped queries without a join through
    # conversations - matches the existing DetectedError/LearningEvent convention.
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    overall_status: Mapped[str] = mapped_column(
        Enum(OverallStatus, name="conversation_overall_status", native_enum=True), nullable=False
    )
    answer_relevance: Mapped[str] = mapped_column(
        Enum(AnswerRelevance, name="conversation_answer_relevance", native_enum=True), nullable=False
    )
    completeness: Mapped[str] = mapped_column(
        Enum(Completeness, name="conversation_completeness", native_enum=True), nullable=False
    )
    meaning_status: Mapped[str] = mapped_column(
        Enum(MeaningStatus, name="conversation_meaning_status", native_enum=True), nullable=False
    )
    grammar_status: Mapped[str] = mapped_column(
        Enum(GrammarStatus, name="conversation_grammar_status", native_enum=True), nullable=False
    )
    naturalness: Mapped[str] = mapped_column(
        Enum(Naturalness, name="conversation_naturalness", native_enum=True), nullable=False
    )
    # Nullable: only meaningful when meaning_status indicates a possible issue
    # (CHANGED/SLIGHTLY_WRONG) - null for PRESERVED (nothing to be confident
    # about) and for UNCLEAR (UNCLEAR already IS the "don't know" state).
    semantic_confidence: Mapped[str | None] = mapped_column(
        Enum(SemanticConfidence, name="conversation_semantic_confidence", native_enum=True),
        nullable=True,
    )
    requires_clarification: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(TZ_DATETIME, server_default=func.now(), nullable=False, index=True)
```

**Revision 2: `context_feedback` and `corrected_sentence` were removed from this table** (both were `Text | None` free-AI-prose columns in the original design). Full reasoning in §3.4 - in short: neither has a downstream consumer that queries prose, both are fully reconstructable in spirit from data already stored elsewhere (the learner's actual text and the tutor's prior question are both already in `ConversationMessage`), and persisting unbounded AI-generated text with no structured query ever run against it is exactly the "AI dump table" failure mode this table must not become. They remain in the API response only (§6), rendered for that turn, never written to the database.

**Why a new table rather than columns on `ConversationMessage` or a JSONB blob:**
- Keeping `ConversationMessage` itself unchanged means every existing query/relationship/test that touches it (there are many - it's a core model) is provably unaffected. The new table is purely additive and only ever referenced by new code.
- Typed columns (not a JSONB evaluation blob) match this codebase's existing convention for fixed-shape structured data (`DetectedError`'s fields are typed; `Exercise.payload`/`correct_answer` are JSONB specifically *because* they vary per exercise type - a genuinely different situation). Typed enum columns are directly filterable/aggregable in SQL, which matters for the Mistake Notebook and future V4.1 personalized-practice queries this needs to support (§4.1-4.2) - "how many LOW-relevance answers has this learner given in the last 30 days" is a plain `WHERE`/`COUNT` on a typed column, not a JSONB path query.
- One row per learner message, not per conversation, so historical granularity is preserved exactly at the level the evaluation actually happened.

**Why NOT tie this to `DetectedError`:** `DetectedError` is fundamentally "one categorized mistake tied to a skill_id" - that shape is correct and proven for grammar/vocabulary issues (it drives `SkillMastery` via `LearningEvent`, which is a real, working, spaced-repetition-integrated pipeline). A relevance/meaning/completeness verdict about a whole turn is a different kind of fact with no curriculum skill to attach to - forcing it through `DetectedError` would mean either inventing a fake skill (dishonest - there is no "conversational relevance" skill in the curriculum, and the recommendation engine's skill-priority formula assumes every skill row is a real, learnable, masterable thing) or dropping the information. Keeping it structurally separate is the honest choice.

### 3.3 Enums (Python-level, backing the new `native_enum=True` columns above - real DB enums, unlike V3's `TaskType`/`MistakeSource`, because these values are genuinely persisted)

```python
class OverallStatus(enum.StrEnum):
    CORRECT = "CORRECT"
    MINOR_ISSUES = "MINOR_ISSUES"
    NEEDS_CORRECTION = "NEEDS_CORRECTION"
    PARTIAL_ANSWER = "PARTIAL_ANSWER"
    OFF_TOPIC = "OFF_TOPIC"
    UNCLEAR = "UNCLEAR"

class AnswerRelevance(enum.StrEnum):
    """Purely topical: does this answer relate to what was asked, at all -
    independent of whether it fully answers it (that's `Completeness`)."""
    FULL = "FULL"
    PARTIAL = "PARTIAL"
    LOW = "LOW"
    NONE = "NONE"

# Revision 2, concern 2: split out of AnswerRelevance, which originally
# conflated "is this on-topic" with "does this fully answer the question" -
# two different facts (e.g. "I like shoes" for "what KIND of shoes" is 100%
# relevant and still incomplete).
class Completeness(enum.StrEnum):
    COMPLETE = "COMPLETE"
    PARTIAL = "PARTIAL"
    MINIMAL = "MINIMAL"

class MeaningStatus(enum.StrEnum):
    PRESERVED = "PRESERVED"
    SLIGHTLY_WRONG = "SLIGHTLY_WRONG"
    CHANGED = "CHANGED"
    UNCLEAR = "UNCLEAR"

class GrammarStatus(enum.StrEnum):
    CORRECT = "CORRECT"
    MINOR_ERRORS = "MINOR_ERRORS"
    MAJOR_ERRORS = "MAJOR_ERRORS"

class Naturalness(enum.StrEnum):
    NATURAL = "NATURAL"
    UNDERSTANDABLE_BUT_UNNATURAL = "UNDERSTANDABLE_BUT_UNNATURAL"
    AWKWARD = "AWKWARD"

# Revision 2, concern 3: the ambiguity/confidence signal. Deliberately a
# 3-value category, not a raw 0-1 float - an LLM cannot reliably self-report
# a calibrated float, and a category is directly, exhaustively unit-testable
# at its boundaries the way a float threshold never honestly is.
class SemanticConfidence(enum.StrEnum):
    CONFIDENT = "CONFIDENT"    # state the correction/mismatch directly
    PROBABLE = "PROBABLE"      # flag it without asserting it as fact
    UNCERTAIN = "UNCERTAIN"    # must not guess - forces requires_clarification
```

The five original dimensions plus the two added in this revision are each independently necessary - confirmed by walking every worked case (§5.5) and every named conflict case (§5.3) against this exact set and finding no pair that can be merged without losing a real distinction the review specifically asked for.

### 3.4 Field ownership - resolving concern 1 explicitly

| Category | Fields | Where they live | Why |
|---|---|---|---|
| **A. Structured learner-state/evaluation data (persisted)** | `overall_status`, `answer_relevance`, `completeness`, `meaning_status`, `grammar_status`, `naturalness`, `semantic_confidence`, `requires_clarification` on `ConversationTurnEvaluation`; `corrected_text` on `DetectedError` (mechanical issues only) | New table / existing table, new column | Typed, bounded-cardinality, directly queryable/aggregable - the actual signal a future trend query or Mistake Notebook pattern needs. `DetectedError.corrected_text` is a short, specific, per-mistake fix (not free prose) with an already-proven UI consumer (Mistake Notebook already renders `correct_text` for LESSON/PRACTICE mistakes in exactly this shape). |
| **B. Conversation content already stored elsewhere** | The learner's literal answer text; the tutor's prior question text | `ConversationMessage.content` (unchanged, already exists) | Never duplicated. `ConversationTurnEvaluation.conversation_message_id` is a foreign key, not a copy - anything that needs the raw text joins to the message it already has a reference to. The preceding tutor question is the previous row in the same `Conversation.messages` ordering, also already available with no new column. |
| **C. Ephemeral AI-generated UI feedback (NOT persisted)** | `context_feedback`, `corrected_sentence` | `TutorEvaluationOut` API response only (§6) | Free-form prose explaining *why* something was flagged, useful exactly once - at the moment the learner reads that turn's reply - with no structured query ever run against it. Reconstructable in spirit at any later time from the two Category-B texts (the actual question + the actual answer) plus the Category-A typed verdict, without needing to have stored the AI's specific wording. Storing it anyway would be exactly the dump-table anti-pattern this concern named. |

`DetectedError.description` (pre-existing, unmodified by this plan) is the one existing precedent for *some* AI prose being persisted - it survives this review's scrutiny only because it is short (already bounded to 200 chars, pre-existing constraint), per-mistake (not per-turn), and has a real, already-shipped consumer (Mistake Notebook renders it today). `context_feedback`/`corrected_sentence` had neither the length bound nor a proven consumer, which is exactly why they were cut rather than kept "because the AI already generates them anyway."

---

## 4. Persistence decisions

- **What is always persisted**: the two `ConversationMessage` rows (unchanged). One `ConversationTurnEvaluation` row per learner message **only when the evaluation is not the trivial all-good case** - see the exact rule below. Mechanical issues continue to persist exactly as today (`DetectedError` + `LearningEvent`), now with `corrected_text` populated.
- **The "only when non-trivial" rule, precisely (revised)**: a `ConversationTurnEvaluation` row is written when `overall_status != CORRECT` **or** `requires_clarification is True` **or** `naturalness != NATURAL`. Note `overall_status != CORRECT` already structurally covers every case that matters - the precedence rules (§5.3) guarantee `overall_status=CORRECT` is only reachable when relevance=FULL, completeness=COMPLETE, meaning=PRESERVED, and grammar=CORRECT simultaneously, so checking `overall_status` alone (plus the two explicit naturalness/clarification carve-outs, which `overall_status`'s 6 values don't otherwise capture) is sufficient - not five separate conditions repeated. A fully correct, fully complete, fully relevant, natural answer does not get a row - there is nothing corrective or noteworthy to record, and rules.md §2.6 ("avoid unnecessary AI calls") extends in spirit to "avoid unnecessary persistence" (the same reasoning V3 already applied). This also directly satisfies Phase E's "for a fully correct answer, do not generate fake corrections" at the persistence layer, not just the UI layer.
- **What is NOT persisted**: the full AI JSON response is not stored verbatim anywhere (matches the existing pattern - `AIConversationTurn`/`turn.reply` is not stored as a blob either; only its already-decomposed pieces are). `context_feedback` and `corrected_sentence` are never persisted, for any turn, regardless of severity (§3.4) - not just "for issues that don't reach `DetectedError`" as an earlier draft of this plan implied, but categorically, everywhere. `issues[].suggestion` text is likewise UI-only for that turn, never stored verbatim (the corresponding *fact* - a short, specific fix - is what lands in `DetectedError.corrected_text` for mechanical issues; the AI's exact wording of the suggestion is not separately kept).
- **What decides whether an issue becomes a `DetectedError` row**: only issue types with a real skill mapping - `GRAMMAR, SPELLING, CAPITALIZATION, PUNCTUATION, TENSE, WORD_CHOICE, VOCABULARY` - exactly as today (`_SKILL_TO_ERROR_TYPE`, extended with `CAPITALIZATION`→`GRAMMAR`, `PUNCTUATION`→`GRAMMAR`, `TENSE`→`GRAMMAR` since `DetectedErrorType` already only has 5 categories and none of these three need a new one). `CONTEXT`, `RELEVANCE`, `COMPLETENESS`, `MEANING` issue types never produce a `DetectedError` row - they are represented only in the turn-level `ConversationTurnEvaluation` typed fields (`answer_relevance`, `completeness`, `meaning_status`), which is the correct home for them per §3.2/§3.4's reasoning.

### 4.1 Mistake Notebook (V3.3) compatibility

**Not modified in this task** (out of scope - this plan proposes the persistence shape that would let a future, explicitly-approved change extend `mistake_service.py` to also surface `ConversationTurnEvaluation` rows, e.g. "3 off-topic answers this week" as a new pattern alongside today's Type A/Type B repeated-mistake groups). What this plan *does* guarantee for that future work: `ConversationTurnEvaluation.user_id` is directly queryable (no join required), `conversation_message_id` links back to the exact learner message, and the new `DetectedError.corrected_text` column means tutor-sourced Mistake Notebook entries can finally show a real corrected answer instead of `null` - a real, immediate, prospective improvement to the *existing* V3.3 feature, achieved with zero change to `mistake_service.py` itself (it already reads `DetectedError.corrected_text`... actually it does not yet - see the discrepancy flagged in §11).

### 4.2 V4.1 compatibility

Named only because the request references it. This plan does not design V4.1. It only confirms the new table's shape (typed, per-turn, user-scoped, timestamped) is a reasonable foundation for a future personalized-practice or trend feature to query, without committing to what that feature is.

---

## 5. AI prompt and schema design

### 5.1 Raw (AI-facing) schema

```python
class RawTutorIssue(BaseModel):
    type: str  # keyword-normalized, same tolerance as today's `skill` field
    original: str
    suggestion: str
    explanation: str
    severity: str  # keyword-normalized: MINOR | MODERATE | MAJOR

class RawTutorTurn(BaseModel):
    reply: str = Field(min_length=1)
    understood_question: bool
    answer_relevance: str
    completeness: str                    # Revision 2, concern 2 - new
    meaning_status: str
    grammar_status: str
    naturalness: str
    semantic_confidence: str | None = None  # Revision 2, concern 3 - new
    issues: list[RawTutorIssue] = Field(default_factory=list)
    corrected_sentence: str | None = None
    context_feedback: str | None = None
    requires_clarification: bool = False
```

`overall_status` is deliberately **not** in the raw AI-facing schema - see §5.3. The prompt (§5.4) instructs the model to set `semantic_confidence` only when `meaning_status` is `CHANGED` or `SLIGHTLY_WRONG`, and to leave it `null` otherwise - validated, not merely requested (§5.3 shows the normalization layer enforcing this regardless of what the AI actually sends).

### 5.2 Normalized schema (`TutorTurn`, `TutorIssue`)

Same shape, with `type`/`severity`/`answer_relevance`/`completeness`/`meaning_status`/`grammar_status`/`naturalness`/`semantic_confidence` keyword-normalized exactly like `normalize_skill`/`normalize_error_type` already do, plus a `skill: ConversationSkill | None` derived only for mechanical issue types (`None` for CONTEXT/RELEVANCE/COMPLETENESS/MEANING), plus the deterministically-derived `overall_status` and the deterministically-finalized `requires_clarification` (§5.3).

**`understood_question` is deliberately requested from the AI but not carried into the normalized schema, the API response, or persistence.** It is asked for as a prompting aid, not a UI signal: explicitly asking the model to consider "did the learner understand what I asked" before scoring relevance tends to improve the *other* fields' quality (a standard structured-prompting technique - make the model reason about a precursor question before the fields that actually matter downstream), but the field itself would be redundant with `answer_relevance`/`requires_clarification` for anything the UI or Mistake Notebook would actually do with it, and this codebase's existing convention (rules.md §2.6, "avoid unnecessary AI calls" extended in spirit) favors not exposing a field with no distinct consumer. This is a deliberate simplification, stated explicitly here rather than silently dropped between §5.1 and §6.

### 5.3 The `overall_status` precedence matrix and `requires_clarification` finalization

The user's conceptual schema asks the AI to self-report `overall_status` *and* the independent dimensions it's supposedly summarizing. Asking the model to do both risks self-contradiction (e.g. the model says `overall_status: CORRECT` while also reporting `answer_relevance: PARTIAL` - which one does the UI trust?) with no way to resolve the conflict except guessing. This plan treats `overall_status` as a pure function of the other, independently-scored fields, evaluated as a **priority-ordered rule list - first matching rule wins**, not an unordered set of conditions:

```python
def derive_overall_status(
    *, relevance: AnswerRelevance, completeness: Completeness, meaning: MeaningStatus,
    grammar: GrammarStatus, requires_clarification: bool,
) -> OverallStatus:
    # Rule 1 - clarification always wins. If the tutor doesn't have enough
    # confidence to know what was meant, nothing else matters until that's
    # resolved - stating a specific correction/verdict would mean guessing.
    if requires_clarification:
        return OverallStatus.UNCLEAR

    # Rule 2 - meaning genuinely unclear, independent of the clarification
    # flag (defensive: the AI can report UNCLEAR meaning without separately
    # setting requires_clarification; this rule catches that regardless).
    if meaning == MeaningStatus.UNCLEAR:
        return OverallStatus.UNCLEAR

    # Rule 3 - zero or low relevance beats everything else below. If the
    # answer isn't meaningfully about the question, the grammar/completeness
    # of that unrelated answer is moot - there is nothing to "complete".
    if relevance in (AnswerRelevance.NONE, AnswerRelevance.LOW):
        return OverallStatus.OFF_TOPIC

    # Rule 4 - a real semantic substitution (e.g. red -> new) beats
    # completeness/grammar - the learner said something different from what
    # they likely intended, which matters more than how completely or how
    # grammatically they said it.
    if meaning == MeaningStatus.CHANGED:
        return OverallStatus.NEEDS_CORRECTION

    # Rule 5 - from here relevance is FULL or PARTIAL and meaning is
    # PRESERVED or SLIGHTLY_WRONG. A partial-relevance or incomplete answer
    # is a PARTIAL_ANSWER regardless of how good the grammar is - "did they
    # actually answer" outranks "did they answer well".
    if relevance == AnswerRelevance.PARTIAL or completeness != Completeness.COMPLETE:
        return OverallStatus.PARTIAL_ANSWER

    # Rule 6 - fully relevant, fully complete, meaning intact: now it's
    # purely about mechanics.
    if grammar == GrammarStatus.MAJOR_ERRORS or meaning == MeaningStatus.SLIGHTLY_WRONG:
        return OverallStatus.NEEDS_CORRECTION
    if grammar == GrammarStatus.MINOR_ERRORS:
        return OverallStatus.MINOR_ISSUES

    # Rule 7 - only reachable when every dimension is clean.
    return OverallStatus.CORRECT
```

`naturalness` deliberately does not feed this function - none of the 6 `overall_status` values are naturalness-specific (there is no "AWKWARD" status), so it stays a separate, independently-shown dimension (§6) rather than being forced into a classification it doesn't belong in. It still independently triggers persistence (§4's "only when non-trivial" rule) even when every other dimension is clean.

**Nothing is lost when a higher-priority rule wins.** `overall_status` is a headline summary; the full detail (`grammar_status=MAJOR_ERRORS`, the specific `issues[]` entries, etc.) remains independently visible in the same response object regardless of which rule decided the headline - a turn that is both `PARTIAL_ANSWER` (rule 5) and has major grammar errors still reports `grammar_status=MAJOR_ERRORS` and lists the grammar issues; it just isn't *headlined* as a grammar problem when there's a bigger-picture relevance/completeness problem to headline instead.

**Named conflict cases, worked through explicitly:**

| Case | Inputs | Rule that fires | Result | Why this is right |
|---|---|---|---|---|
| Grammatically correct but off-topic | relevance=NONE, grammar=CORRECT | Rule 3 | `OFF_TOPIC` | Being grammatically perfect doesn't rescue an answer that isn't about the question. |
| Grammatically incorrect but fully relevant | relevance=FULL, completeness=COMPLETE, meaning=PRESERVED, grammar=MAJOR_ERRORS | Rule 6 | `NEEDS_CORRECTION` | Nothing else is wrong, so the headline correctly becomes grammar-driven. |
| Partial but meaningful | relevance=FULL, completeness=PARTIAL, meaning=PRESERVED | Rule 5 | `PARTIAL_ANSWER` | Not confused with a meaning problem - meaning is fine, completeness isn't. |
| Semantic mismatch with low intent confidence | meaning=CHANGED, semantic_confidence=UNCERTAIN → requires_clarification forced true (below) | Rule 1 | `UNCLEAR` | Confidence-forced clarification outranks even a detected meaning change - never assert a specific correction when genuinely unsure. |
| Ambiguous answer | requires_clarification=true (AI-reported, general) | Rule 1 | `UNCLEAR` | Direct. |
| Multiple independent problems (e.g. PARTIAL relevance AND MAJOR grammar errors) | relevance=PARTIAL, grammar=MAJOR_ERRORS | Rule 5 (before rule 6 is ever reached) | `PARTIAL_ANSWER` | Headline is completeness-driven; `grammar_status`/`issues[]` still separately report the grammar problem in full - see "nothing is lost" above. |

**`requires_clarification`'s final value - a second deterministic derivation, not a single trusted AI flag:**

```python
final_requires_clarification = raw.requires_clarification or (semantic_confidence == SemanticConfidence.UNCERTAIN)
```

The AI's own `requires_clarification` flag is kept (it can fire for reasons unrelated to a specific word-substitution - e.g. a genuinely incomprehensible answer), but `semantic_confidence=UNCERTAIN` **always** forces it to `true` regardless of what the AI separately set that boolean to - the same "derive the safety-critical field, don't fully trust one AI-reported bool in isolation" principle already applied to `overall_status` itself. This directly closes concern 3: the system cannot silently assert a specific interpretation of an uncertain meaning mismatch even if the model's own `requires_clarification` flag was inconsistently set.

**`corrected_sentence`'s final value gets the identical defensive treatment (§7):**

```python
final_corrected_sentence = None if semantic_confidence == SemanticConfidence.UNCERTAIN else raw.corrected_sentence
```

If the AI reports `semantic_confidence=UNCERTAIN` but still fills in `corrected_sentence` anyway (prompt instruction §5.4 rule 17 says not to, but nothing here trusts that in isolation), the normalization layer discards it. The UI can never display an asserted "suggested answer" for a turn the system itself has just classified as genuinely ambiguous - the schema makes this structurally impossible to get wrong, rather than relying on the frontend to remember not to render it.

Both `derive_overall_status` and these two OR/override-derivations are pure, deterministic, exhaustively unit-testable functions with no AI involvement - see §12 for the boundary test list.

### 5.4 System prompt (draft)

The existing 8 numbered rules (mirroring `rules.md` §6) are kept - they govern tone/pacing/level and are not the problem. New rules are added specifically targeting the audited gaps, plus the Phase E anti-overcorrection rules:

```
9. Before evaluating grammar, first determine: did the learner's answer relate to what
   you just asked, and did it answer completely? Judge this independently of whether the
   sentence is grammatically correct - a grammatically perfect sentence can still be
   off-topic, partial, or use the wrong tense for the question asked.
10. If the question asks about a current/general state (e.g. "Do you like...") and the
    learner answers in the past tense, treat this as a tense/context issue - explain that
    the tense doesn't match what the question was asking about, not just that the
    apostrophe/spelling is wrong.
11. If a word in the learner's answer might not be the word used in your question (e.g.
    they wrote "new" when you asked about "red"), do not silently assume they meant the
    same thing, and do not silently substitute your word for theirs. Either note the
    possible mismatch in context_feedback, or set requires_clarification=true and ask
    which they meant - never state what they "meant" as if it were certain.
12. A valid alternative or partial answer is not automatically wrong. "I prefer coffee"
    answers "Do you like tea?" naturally. "I don't really have one" is a complete, valid
    answer to "what's your favorite color?" - never force the learner toward a specific
    wording or force a yes/no answer that wasn't the only valid response shape.
13. If the learner's answer only partially satisfies what the question asked for (e.g.
    it states a dislike but not the requested preference), say so via completeness
    and context_feedback, and let your `reply` naturally ask for the missing piece - do
    not silently treat this as fully answered, and do not silently move to an unrelated
    next question. `answer_relevance` measures whether the answer is *about* the right
    topic; `completeness` measures whether it *fully* answers what was asked - these are
    different questions and must be scored independently, not collapsed into one.
14. Never invent or assume learner intent you cannot support from what they actually
    wrote. When genuinely ambiguous, ask a short clarifying question instead of guessing.
15. Do not rewrite a sentence that is already correct. Do not correct valid stylistic
    variation. Do not mark an opinion or preference as factually wrong.
16. Your `reply` must react to what the learner actually said in this turn, informed by
    your own evaluation above (e.g. if the answer was partial, your reply should
    acknowledge what was said and ask for what's missing - not ask a disconnected new
    question).
17. Whenever meaning_status is CHANGED or SLIGHTLY_WRONG, you must also set
    semantic_confidence to exactly one of: CONFIDENT (you are sure this is a genuine
    mistake or substitution - state the correction directly), PROBABLE (you believe
    there is likely a mismatch but a different, valid reading exists - note it without
    asserting it as fact), or UNCERTAIN (you genuinely cannot tell what the learner
    meant - you must not guess; set requires_clarification=true and ask which they
    meant in your reply). Leave semantic_confidence null when meaning_status is
    PRESERVED or UNCLEAR. Never mark a genuinely ambiguous word choice as CONFIDENT
    just to avoid asking a clarifying question.

Respond with ONLY a single JSON object matching exactly this shape:
{
  "reply": "...",
  "understood_question": true,
  "answer_relevance": "FULL" | "PARTIAL" | "LOW" | "NONE",
  "completeness": "COMPLETE" | "PARTIAL" | "MINIMAL",
  "meaning_status": "PRESERVED" | "SLIGHTLY_WRONG" | "CHANGED" | "UNCLEAR",
  "grammar_status": "CORRECT" | "MINOR_ERRORS" | "MAJOR_ERRORS",
  "naturalness": "NATURAL" | "UNDERSTANDABLE_BUT_UNNATURAL" | "AWKWARD",
  "semantic_confidence": "CONFIDENT" | "PROBABLE" | "UNCERTAIN" | null,
  "issues": [{"type": "...", "original": "...", "suggestion": "...", "explanation": "...", "severity": "..."}],
  "corrected_sentence": "... or null if the answer needs no correction",
  "context_feedback": "... or null if there is nothing beyond grammar to note",
  "requires_clarification": false
}

Only include an issue for something genuinely worth teaching (as today). corrected_sentence
and context_feedback should be null, not empty strings, when there is nothing to say.
```

This is a draft for implementation-time refinement, not a final, frozen prompt - real testing (Phase I) against the actual provider is what determines whether it needs adjustment, and this plan says so explicitly rather than presenting untested prompt wording as a solved problem. Whether the model reliably honors rule 17's three-way confidence distinction (rather than defaulting to CONFIDENT out of habit) is exactly the kind of thing `AI_TUTOR_SEMANTIC_EVALUATION_SPEC.md`'s dataset is designed to catch before implementation is trusted.

### 5.5 Worked validation against the four cases in the request

- **Case 1** (pure grammar, "yes i like red shoes"): `grammar_status=MINOR_ERRORS`, `answer_relevance=FULL`, `completeness=COMPLETE`, `meaning_status=PRESERVED` → derived `overall_status=MINOR_ISSUES` (rule 6). One `issues` entry (capitalization). Matches the expected feedback exactly.
- **Case 2** (tense/context mismatch): `grammar_status` may be `CORRECT` (the sentence is grammatically valid), but a new rule-10-driven `issues` entry of `type=TENSE` fires with an explanation about the mismatch, and `meaning_status=SLIGHTLY_WRONG` with `context_feedback` carrying the "doesn't match a present-preference question" note. `overall_status` derives to `NEEDS_CORRECTION` (rule 6) - correctly distinct from a pure mechanical case, without needing a clarification question (this mismatch is unambiguous, not a case for `semantic_confidence=UNCERTAIN`).
- **Case 3** (red/new substitution, the exact reported failure): `issues` gets the two mechanical entries (capitalization, apostrophe) *and* `meaning_status=CHANGED`, with `semantic_confidence` set per rule 17 - most likely `PROBABLE` (a real possible mismatch, not obviously a typo, but not necessarily certain either) or `UNCERTAIN` if the model judges it genuinely can't tell. If `PROBABLE`: `context_feedback` explains the red/new mismatch without asserting which the learner meant, `requires_clarification` stays whatever the AI reports (not forced), `overall_status` derives to `NEEDS_CORRECTION` (rule 4). If `UNCERTAIN`: `requires_clarification` is forced `true` regardless of the AI's own flag, `overall_status` derives to `UNCLEAR` (rule 1), and `reply` asks "did you mean red shoes or new shoes?" per rule 14 - explicitly never silently substituted, and the schema now makes the *degree* of certainty explicit rather than collapsing "probably a mismatch" and "no idea what they meant" into the same binary flag.
- **Case 4** (partial answer): `grammar_status=MINOR_ERRORS` (capitalize/apostrophe), `answer_relevance=FULL` (the answer *is* about shoe preferences - it's on-topic), `completeness=PARTIAL` (it states a dislike but not the requested preferred type) → `overall_status` derives to `PARTIAL_ANSWER` (rule 5), correctly driven by completeness rather than relevance now that the two are distinct fields. `reply` (per rule 16) acknowledges the stated dislike and asks what the learner does prefer - not a disconnected new question.

All four are representable without contradiction, and Case 3 now demonstrates the confidence-graded behavior concern 3 specifically asked for - not just "ask or don't ask" but three distinguishable levels of certainty driving three distinguishable behaviors. This is a structural validation of the schema design, not a claim that a live model will reliably produce these exact judgments - that is `AI_TUTOR_SEMANTIC_EVALUATION_SPEC.md`'s job.

---

## 6. API changes

`SendMessageResponse`/`VoiceSendMessageResponse` (`schemas/conversation.py`) change from `corrections: list[CorrectionOut]` to a richer, still-single response:

```python
class TutorIssueOut(BaseModel):
    type: str
    original: str
    suggestion: str
    explanation: str
    severity: str
    skill: ConversationSkill | None  # None for CONTEXT/RELEVANCE/COMPLETENESS/MEANING

class TutorEvaluationOut(BaseModel):
    overall_status: OverallStatus
    answer_relevance: AnswerRelevance
    completeness: Completeness
    meaning_status: MeaningStatus
    grammar_status: GrammarStatus
    naturalness: Naturalness
    semantic_confidence: SemanticConfidence | None
    issues: list[TutorIssueOut]
    # Ephemeral (§3.4) - present in this response for the frontend to render
    # this turn, deliberately never written to ConversationTurnEvaluation.
    corrected_sentence: str | None
    context_feedback: str | None
    requires_clarification: bool

class SendMessageResponse(BaseModel):
    learner_message: ConversationMessageOut
    tutor_message: ConversationMessageOut
    evaluation: TutorEvaluationOut
```

`corrections` is removed rather than kept alongside `evaluation` as a deprecated duplicate - this is a full-stack app with no external API consumers and frontend+backend ship together (confirmed: no versioned public API exists anywhere in this codebase), so there is no one else's integration to preserve, and keeping two representations of the same information invites them drifting inconsistent. This is a genuine breaking change to the response *shape*, made deliberately - flagged explicitly here, not silently.

**`corrected_sentence`/`context_feedback` living in the API response but not the database is intentional, not an oversight** (§3.4) - the *turn* that just happened is exactly when that prose is useful and it is never recoverable afterward, by design.

**Correction to an implicit overclaim caught during this same review**: it would be inaccurate to say the persisted typed fields (`answer_relevance`, `meaning_status`, etc.) "remain available historically" *through the API* without an explicit, separate decision to expose them there. Checked directly: today's `ConversationMessageOut` (`{id, role, content, created_at}`) does not include `corrections` at all - historical corrections are already only visible in the `SendMessageResponse` of the turn that produced them, never when re-fetching a conversation later via `GET /tutor/conversations/{id}`. This plan's persisted `ConversationTurnEvaluation` rows are real and queryable *directly* (by a repository function, an admin query, or a future Mistake Notebook extension) regardless of what the conversation-detail endpoint does - but whether `ConversationDetailOut`/`ConversationMessageOut` is ever extended to inline evaluation data per historical message is a genuinely separate, still-open API decision, not something this plan resolves. Recommendation, stated as a recommendation and not a settled fact: leave `ConversationMessageOut` unchanged for now (matching today's `corrections` precedent exactly) and revisit only if a concrete future feature needs it.

---

## 7. Frontend changes

`CorrectionNote` (currently one generic amber block) is replaced with a panel that only renders the sections that have real content - never a fabricated section for a clean answer, and never a "Suggested answer" box when the AI itself is not confident enough to propose one:

**`semantic_confidence=UNCERTAIN` case (the exact example in concern 3 - no asserted correction):**
```
Your answer
"No, I didnt like wearing new shoes."
─────────────────────────────
Writing corrections              (only if issues[] has mechanical entries)
• i → I
• didnt → didn't
─────────────────────────────
Context                          (only if context_feedback is non-null)
I'm not sure if you meant red shoes or new shoes.
─────────────────────────────
                                  (NO "Suggested answer" box - corrected_sentence
                                   must be null whenever semantic_confidence=UNCERTAIN;
                                   asserting one here would be exactly the "silently
                                   assume intent" failure this review exists to prevent)
─────────────────────────────
Tutor                            (the existing reply, unchanged rendering - MessageBubble)
"Did you mean red shoes or new shoes?"
```

**`semantic_confidence=PROBABLE` case (a likely-but-not-certain mismatch - hedged, not asserted):**
```
Context
The question was about red shoes, but your answer mentions new shoes - if that
was a slip, you could say:
─────────────────────────────
Suggested answer                 (shown, but framed as a hypothesis, not a fact)
"No, I don't like wearing red shoes."
```

The system prompt (§5.4, rule 17) instructs `corrected_sentence` to be null whenever `semantic_confidence=UNCERTAIN` - the normalization layer should also defensively null it out server-side if the AI sets both anyway, the same "don't fully trust one AI-reported field in isolation" principle applied everywhere else in this schema.

For a pure Case-1-style grammar-only turn, only the "Writing corrections" section renders (no fabricated Context/Suggested-answer boxes) - this directly satisfies Phase D's "for a simple grammar-only mistake, do not show unnecessary context warnings." For a fully correct answer (`overall_status=CORRECT`, no `ConversationTurnEvaluation` row persisted at all per §4), no panel renders beneath the message at all - just the tutor's natural `reply`, exactly as a correct answer should look.

Reuses the existing design system unchanged: `Card`, the established dark palette/spacing, `useReducedMotion` (already used in this exact file for `TypingDots`), the same `role="status"`/`aria-label` conventions already used for audio errors in `MessageBubble`. No new component library, no new color tokens - new semantic groupings of the same visual language, per the request's own instruction to use the existing premium design system.

`frontend/src/types/conversation.ts` gains `TutorEvaluation`/`TutorIssue` types mirroring the new backend schema; `Correction`/`CorrectionOut`-shaped types are removed together with the backend change (frontend+backend change atomically, per §6's reasoning).

---

## 8. Migration strategy

One Alembic revision: `ADD COLUMN detected_errors.corrected_text TEXT NULL` + `CREATE TABLE conversation_turn_evaluations (...)` + the 7 new native enum types (`OverallStatus`, `AnswerRelevance`, `Completeness`, `MeaningStatus`, `GrammarStatus`, `Naturalness`, `SemanticConfidence` - revised up from 5 in this document's first draft, per concern 2's `Completeness` split and concern 3's `SemanticConfidence` addition). Both changes are purely additive - no existing column is altered, no existing row is touched, no backfill is attempted or needed (nullable-by-design, exactly matching the `corrected_text` precedent this session already established the pattern for in the V3 phase). Reversible by a straightforward downgrade (drop the table, drop the column, drop the enum types) since nothing else will depend on their presence at the schema level - application code must simply be deployed *after* the migration runs, same ordering requirement every other migration in this codebase already has.

## 9. Backward compatibility

- **Historical `ConversationMessage`/`DetectedError` rows**: fully valid, unmodified, correctly readable exactly as before. No historical row ever gets a fabricated `corrected_text` or a fabricated `ConversationTurnEvaluation` - both are simply absent for anything that predates the change, which is the honest state of affairs.
- **API contract**: `SendMessageResponse.corrections` → `SendMessageResponse.evaluation` is a breaking change to the response shape (§6). Acceptable because frontend and backend are one deployable unit with no external consumer - confirmed by inspecting this codebase for any versioned/public API surface (none exists).
- **Existing 24 tests** (`test_tutor.py` ×9, `test_conversation_ai.py` ×7, `test_voice_conversation.py` ×8): assertions that check `body["corrections"]` will need updating to check `body["evaluation"]` - this is expected, not a regression, since the response shape is intentionally changing. Every *behavior* those tests verify (ownership, auth, ended-conversation 409, AI-failure-leaves-no-trace, malformed-JSON 503, timeout handling, rate limiting, history ordering) must continue to hold and must be re-verified, not just left passing by accident.

## 10. Cost analysis

Still exactly **one AI call per learner message** (rules.md §2.6 fully honored - confirmed no new call site is introduced anywhere in §2's diagram). The only cost change is a larger completion (more output tokens per call, since the JSON response has more fields) - `max_tokens` should move from 600 to roughly 900-1000 to avoid truncating the richer JSON under `json_mode`, a real, honest, disclosed cost increase, not a hidden one. Prompt (input) tokens grow modestly (the added system-prompt rules are a few hundred tokens). No new provider, no new dependency, no new AI-touching endpoint. Fully reuses `get_metered_ai_provider` (rate limiting + `MeteredAIProvider` logging) unmodified - the exact same `AI_RATE_LIMIT_PER_HOUR=30` budget applies, and `ai_call_logs` will show the increased `completion_tokens` honestly once implemented, which is itself useful signal for confirming the real cost impact post-launch rather than guessing at it now.

## 11. A discrepancy already found while writing this plan

While designing §4.1 (Mistake Notebook compatibility), inspection of `backend/app/services/mistake_service.py` (built earlier this session, V3.3) shows `_from_detected_error` currently sets `correct_text=None` **unconditionally** for every TUTOR-source mistake, with a comment stating this is because `corrected_text` is never persisted. Once `DetectedError.corrected_text` exists (§3.1), that function would need a small, explicit follow-up change (`correct_text=row.corrected_text`) to actually surface the new data - it will not happen automatically just because the column exists. Flagging this now, honestly, as a real dependency this plan creates for a currently-out-of-scope file, rather than letting it surface as a surprise during implementation.

## 12. Test plan

Every scenario from the request, and what kind of test can honestly verify it:

| Scenario | Test type | What it actually proves |
|---|---|---|
| Grammar only | `FakeAIProvider`-backed API test | Given a canned AI response shaped like Case 1, the pipeline parses/validates/derives/persists/responds correctly. **Does not prove a live model produces this judgment.** |
| Tense/context mismatch | Same, canned Case-2-shaped response | Pipeline correctness for this shape. Same caveat. |
| Wrong word changes meaning | Same, canned Case-3-shaped response, in both a `semantic_confidence=PROBABLE` and an `=UNCERTAIN` variant | Pipeline correctness for both the "flagged, not asserted" and "forced clarification, corrected_sentence nulled" sub-cases. Same caveat about live-model reliability. |
| Valid alternative answer | Canned response with `answer_relevance=FULL`, `completeness=COMPLETE`, no issues | Confirms no forced rewrite occurs when the AI itself reports a clean, relevant, complete answer. |
| Partial answer | Canned response with `completeness=PARTIAL`, `answer_relevance=FULL` | `overall_status` derivation (completeness-driven, not relevance-driven - the exact distinction concern 2 introduced), persistence-only-when-non-trivial rule, response shape. |
| Off-topic answer | Canned `NONE`-relevance response | Same, at the `OFF_TOPIC` derivation branch. |
| Ambiguous answer | Canned `requires_clarification=true` response, and separately a `semantic_confidence=UNCERTAIN` response with `requires_clarification=false` | Confirms both the direct flag AND the forced-override path round-trip correctly; **cannot** prove an AI won't invent intent - that's a prompt-quality question only real testing answers. |
| Correct answer | Canned all-clean response | Confirms **no** `ConversationTurnEvaluation` row is written and no `issues` render - directly testing §4's "only when non-trivial" rule. |
| Multiple grammar errors + semantic issue | Canned response with 2+ mechanical issues and `meaning_status=CHANGED` | Confirms issues are kept separate (mechanical → `DetectedError` rows with correct skills; meaning/relevance signals → the turn-level typed fields only), not merged. |
| Conversation continuity | Existing `test_conversation_history_preserves_message_order`-style test, extended | Confirms full history still reaches the model unchanged - this mechanism is not touched by the schema change, so this is mostly a non-regression check. |
| AI malformed response | Extend existing `test_malformed_ai_response_returns_503_and_records_nothing` for the new, larger schema | Existing validation/error-handling path continues to work unmodified in spirit. |
| AI provider failure (timeout/error) | Extend existing `test_ai_timeout_does_not_corrupt_conversation_state` | Existing state-safety guarantee continues to hold for the new schema. |
| Rate limiting | No change needed - `test_rate_limiting.py`'s AI-endpoint coverage is schema-agnostic (it just counts calls) | Confirms nothing about the richer schema affects the rate-limit gate. |
| User isolation | Extend existing `test_cannot_access_another_users_conversation`-style coverage to also assert `ConversationTurnEvaluation` rows are scoped by `user_id` and never leak cross-user | New, since this is genuinely new persisted state that didn't exist before. |

### 12.1 `derive_overall_status` and confidence-derivation exhaustive boundary tests (new, per concern 2)

**This is the one place "correctness" can be proven outright** - these are pure functions, no AI involved, so every listed case can be asserted exactly rather than approximately. 20 cases, one per rule boundary plus every named conflict case from §5.3's table plus the two confidence-derivation functions from the same section:

| # | relevance | completeness | meaning | grammar | requires_clarification (raw) | Expected `overall_status` | What this boundary proves |
|---|---|---|---|---|---|---|---|
| 1 | FULL | COMPLETE | PRESERVED | CORRECT | **true** | `UNCLEAR` | Rule 1: clarification wins even when every other field is clean. |
| 2 | FULL | COMPLETE | **UNCLEAR** | CORRECT | false | `UNCLEAR` | Rule 2: unclear meaning forces UNCLEAR even without the raw clarification flag set. |
| 3 | **NONE** | COMPLETE | PRESERVED | CORRECT | false | `OFF_TOPIC` | Rule 3: zero relevance beats perfect grammar - "grammatically correct but off-topic." |
| 4 | **LOW** | COMPLETE | PRESERVED | CORRECT | false | `OFF_TOPIC` | Rule 3's other branch. |
| 5 | FULL | COMPLETE | **CHANGED** | CORRECT | false | `NEEDS_CORRECTION` | Rule 4: a real meaning change is flagged even with perfect grammar. |
| 6 | **PARTIAL** | COMPLETE | PRESERVED | CORRECT | false | `PARTIAL_ANSWER` | Rule 5, relevance-driven branch. |
| 7 | FULL | **PARTIAL** | PRESERVED | CORRECT | false | `PARTIAL_ANSWER` | Rule 5, completeness-driven branch - "partial but meaningful," the exact case concern 2 was about. |
| 8 | FULL | **MINIMAL** | PRESERVED | CORRECT | false | `PARTIAL_ANSWER` | Rule 5's other completeness value. |
| 9 | FULL | COMPLETE | PRESERVED | **MAJOR_ERRORS** | false | `NEEDS_CORRECTION` | Rule 6: "grammatically incorrect but fully relevant" - correctly grammar-driven since nothing else is wrong. |
| 10 | FULL | COMPLETE | **SLIGHTLY_WRONG** | CORRECT | false | `NEEDS_CORRECTION` | Rule 6's meaning-driven branch. |
| 11 | FULL | COMPLETE | PRESERVED | **MINOR_ERRORS** | false | `MINOR_ISSUES` | Rule 6's minor branch. |
| 12 | FULL | COMPLETE | PRESERVED | CORRECT | false | `CORRECT` | Rule 7: only reachable when every dimension is clean - also the exact condition gating "no `ConversationTurnEvaluation` row written" (§4). |
| 13 | **NONE** | COMPLETE | PRESERVED | CORRECT | **true** | `UNCLEAR` | Priority: rule 1 beats rule 3 - clarification outranks even off-topic. |
| 14 | **NONE** | COMPLETE | **CHANGED** | CORRECT | false | `OFF_TOPIC` | Priority: rule 3 beats rule 4 - relevance is checked before meaning-changed. |
| 15 | FULL | **PARTIAL** | PRESERVED | **MAJOR_ERRORS** | false | `PARTIAL_ANSWER` | Priority: rule 5 beats rule 6 - "multiple independent problems," headline is completeness-driven; `grammar_status` field independently still reports `MAJOR_ERRORS` in the same response object. |
| 16 | FULL | **PARTIAL** | **CHANGED** | CORRECT | false | `NEEDS_CORRECTION` | Priority: rule 4 beats rule 5 - a genuine meaning change outranks mere incompleteness. |

| # | Function under test | Inputs | Expected output | What it proves |
|---|---|---|---|---|
| 17 | `final_requires_clarification` | `semantic_confidence=UNCERTAIN`, `raw.requires_clarification=False` | `True` | The core fix for concern 3 - uncertainty forces clarification regardless of the AI's own flag. |
| 18 | `final_requires_clarification` | `semantic_confidence=CONFIDENT`, `raw.requires_clarification=False` | `False` | Confidence does *not* spuriously force clarification. |
| 19 | `final_corrected_sentence` | `semantic_confidence=UNCERTAIN`, `raw.corrected_sentence="No, I don't like wearing red shoes."` | `None` | The AI cannot get an asserted "suggested answer" through to the UI for a turn it just classified as genuinely ambiguous - structurally, not by prompt request alone. |
| 20 | `final_corrected_sentence` | `semantic_confidence=PROBABLE`, `raw.corrected_sentence="No, I don't like wearing red shoes."` | `"No, I don't like wearing red shoes."` | Confirms only `UNCERTAIN` triggers the null-out - a `PROBABLE` hedge is still allowed to show a hypothesis (§7). |

**Honest summary**: deterministic tests (schema validation, persistence rules, all 20 cases above, error handling, auth/isolation, the "only when non-trivial" persistence rule) can be proven correct outright and will be. Whether the *live* Groq model reliably produces correct semantic judgments for real, varied learner input is not something any unit test can establish - that is precisely what `AI_TUTOR_SEMANTIC_EVALUATION_SPEC.md` (§15) exists to check, honestly and separately, before implementation is trusted.

---

## 13. Risks

1. **The single biggest risk: prompt reliability is unproven - now gated, not just flagged.** Every structural piece of this plan (schema, persistence, derivation, UI) can be built and tested deterministically. Whether Groq's configured model *actually* reliably distinguishes "red" from "new" as a meaning mismatch, reliably recognizes a partial answer, or - the specific new bar concern 3 set - reliably reports `UNCERTAIN` rather than false `CONFIDENT`, is genuinely unknown until real-tested. This is no longer an open risk this plan just names and moves past: `AI_TUTOR_SEMANTIC_EVALUATION_SPEC.md` (§15) is the explicit, required gate before implementation proceeds. rules.md §2.7-8 ("cheapest suitable model for simple tasks... stronger models only when the task genuinely requires them") still has real tension worth watching: semantic/contextual judgment is a harder task than mechanical grammar-checking, and the currently-configured model was presumably chosen, long before this task, for the simpler version of this job. If the evaluation dataset's zero-tolerance bar (§15) fails, that tension becomes the reason, not a hypothetical.
2. **Schema size and JSON reliability - now larger still.** The schema grew again in this revision (2 more fields: `completeness`, `semantic_confidence`). A larger required JSON shape gives the model more surface area to malform. The existing keyword-normalization pattern (`normalize_skill` etc.) already absorbs casing/wording variance for enum-shaped fields; genuinely missing required fields still hard-fail validation exactly as today (`AIResponseValidationError`, 503, nothing persisted) - the failure mode is unchanged and safe, but will likely fire *more often* than today's simpler schema until the prompt is tuned against real traffic. This is exactly what `AI_TUTOR_SEMANTIC_EVALUATION_SPEC.md`'s 48 real-provider calls will surface concretely (a real malformed-response rate) rather than leaving as a guess.
3. **Persistence-timing risk on the "only when non-trivial" rule.** If the derivation or the "when to write a row" boundary is ever inconsistent with what the UI decides to render, the UI and the database could disagree about what happened on a given turn. Mitigated by deriving both from the exact same normalized `TutorTurn` object in one place, not recomputed separately in two layers - but worth a specific integration test, not just unit tests of each piece in isolation.
4. **Migration risk is low but real.** Additive-only, no backfill, no altered column - the lowest-risk category of schema change this codebase has, but it is still a real migration against a real production database path, and must be tested against a copy of real schema state before being treated as safe to ship (same discipline every other migration in this codebase already follows).
5. **Cost risk is small and bounded**, not open-ended - quantified honestly in §10, not hand-waved. The 2 additional fields added in this revision (`completeness`, `semantic_confidence`, the latter nullable and often absent) grow the completion size marginally further - not re-quantified with a new token estimate here, since it's a small, bounded addition on top of an already-honest estimate, not a new order of magnitude.
6. **Scope discipline risk**: the temptation to also wire this into Mistake Notebook / V4.1 in the same change is real (they're adjacent and the user's own Phase G asks about compatibility) - this plan deliberately does not do that (§4.1), to keep this change reviewable and to avoid modifying V3.3's already-shipped, already-tested `mistake_service.py` without a separate, explicit go-ahead.
7. **New, from this revision: the precedence matrix's priority order (§5.3) encodes real value judgments** (e.g. "a meaning change matters more than incompleteness," rule 4 before rule 5) that were made here, by reasoning through named cases, not derived from any external authority. They are internally consistent and each is individually defensible, but a different, equally defensible ordering could exist - this is a genuine design choice, not a mathematical necessity, and is worth a second pair of eyes specifically on the ordering itself, not just on whether the code correctly implements whatever ordering is chosen.

---

## 14. What this plan explicitly does not do

- Does not modify any application code, add any migration, or touch `mistake_service.py`/Mistake Notebook.
- Does not claim the prompt in §5.4 is final - it is a reasoned draft, explicitly labeled as needing real-provider validation before being trusted.
- Does not claim semantic/contextual understanding is "solved." It claims the *pipeline* to support it can be built and deterministically tested; whether the *model* delivers on it is unverified until the real-provider evaluation (§15) runs, and even then only for the cases actually tried.
- Does not implement V3.3 Mistake Notebook integration or V4.1 - both are explicitly named as future, out-of-scope, prepared-for-but-not-built.
- Does not claim the precedence ordering in §5.3 is the only correct one - it is one internally-consistent, individually-defensible ordering, flagged in §13 risk 7 as worth independent scrutiny on the ordering itself.

---

## 15. Real-provider evaluation gate (new in this revision)

`AI_TUTOR_SEMANTIC_EVALUATION_SPEC.md` (sibling document) defines a 48-case dataset spanning every category named in this review's concern 4, with expected values per dimension and explicit pass/fail criteria per category, including a **zero-tolerance bar** for the exact failure mode this whole task started from: the model must never report `semantic_confidence=CONFIDENT` on a case this dataset has deliberately constructed to be genuinely ambiguous.

**This plan treats that dataset's results as a precondition for implementation, not a nice-to-have follow-up.** Concretely:
- If the zero-tolerance bar fails on even one case, implementation does not proceed until either the prompt is revised and re-tested, or a different/larger model is evaluated (§13 risk 1) - whichever the results actually point to.
- If the category-level pass thresholds (defined in the spec document) are not met, the specific failing categories' prompt rules (§5.4) get revised and re-tested before those categories are trusted, without necessarily blocking categories that did pass.
- Running this dataset is real, metered AI usage against the actual configured provider (48 real calls) - small, bounded, one-time, and worth the cost precisely because it is the only honest way to answer "does this actually work" rather than assuming it from the schema design alone.
