# AI Tutor Pre-Implementation Consistency Audit — Report

Status: **Audit complete. No production code, migrations, commits, or pushes were made — this report and its one edited artifact (`AI_TUTOR_SEMANTIC_EVALUATION_SPEC.md`) are the entire output of this pass.**

Scope: a final consistency pass over the 3 planning documents (`AI_TUTOR_CONVERSATION_INTELLIGENCE_AUDIT.md`, `AI_TUTOR_CONVERSATION_INTELLIGENCE_PLAN.md`, `AI_TUTOR_SEMANTIC_EVALUATION_SPEC.md`) before the real-provider evaluation run described in the plan's §15. The audit and plan documents required no changes — every inconsistency found was in the 48-case evaluation dataset (the spec document), which is the one artifact this report modifies.

---

## 1. Number of inconsistencies found

**CORRECTION (this revision):** a strict external review found that the previous version of this report contained an internal arithmetic contradiction — it stated "12 cases required a fix" while listing 13 case numbers, stated "36 cases were already correct" against a list that actually enumerated 35, and asserted "12 + 36 = 48." All three were counting errors in the report's prose, not in the underlying dataset. §3 below now carries a machine-checkable accounting block so this class of error can't recur silently.

**16 distinct inconsistencies**: 13 case-level fixes (across 13 of the 48 cases, exactly one fix-cause per case) and 3 document-level fixes. Each case is counted exactly once, in whichever row its primary cause falls under:

| Cause | Cases | Count |
|---|---|---|
| Text/expectation mismatch (audit items 1-2) | 16, 25 | 2 |
| Issue-count granularity errors (audit item 3, generalized to all 48 cases per item 6) | 1, 9, 11, 43, 44, 45 | 6 |
| Ambiguous "X or Y" values (audit item 4) | 30, 32, 33 | 3 |
| Missing fields with no ambiguous value involved (found while auditing item 6) | 31 | 1 |
| `semantic_confidence` rule-compliance gap (found while verifying item 5) | 15 | 1 |
| **Case-level subtotal** | | **13** |
| New §2.0 "Ground rules" section (document-level) | — | 1 |
| §4 grading-criteria "categories" terminology disambiguation (document-level) | — | 1 |
| §2.0's own cross-reference self-correction (document-level) | — | 1 |
| **Document-level subtotal** | | **3** |
| **Total** | | **16** |

No inconsistency was found in `AI_TUTOR_CONVERSATION_INTELLIGENCE_AUDIT.md` or `AI_TUTOR_CONVERSATION_INTELLIGENCE_PLAN.md` — both were re-read against the corrected spec and remain accurate; neither was edited.

---

## 2. Every correction made

### 2.1 The 2 named text/expectation mismatches (audit items 1-2)

| Case | Before | After | Why |
|---|---|---|---|
| **16** | Answer text `"No, I didn't like wearing new shoes."` (already clean) but grammar expectation claimed capitalization/apostrophe errors | Answer text changed to `"no i didnt like wearing new shoes"` (the true original messy-typing example); grammar expectation restated as 3 explicit spans: capitalization "no"→"No", capitalization "i"→"I", punctuation "didnt"→"didn't" | The clean text and the claimed mechanical errors contradicted each other. Restoring the true original learner input (lowercase, no apostrophe) makes the claimed errors real. Semantic fields (`meaning=CHANGED`, `semantic_confidence=UNCERTAIN`, `requires_clarification=true`) were left unchanged — those were never the problem. |
| **25** | Answer text `"I don't like wearing red shoes."` (already clean) but grammar expectation claimed capitalization/apostrophe errors | Answer text changed to `"i dont like wearing red shoes"`; grammar expectation restated as 2 explicit spans: capitalization "i"→"I", punctuation "dont"→"don't" | Same class of bug as case 16, same fix strategy: use the literal original reported example instead of a cleaned-up paraphrase. |

### 2.2 Issue-granularity rule (audit item 3) — defined once, applied to all 6 affected cases

**The rule, now stated in a new §2.0**: each concrete incorrect text span is its own `issues[]` entry, even when multiple spans share the same type. "Expected issue count" means mechanical issues only (grammar/spelling/capitalization/punctuation/tense/word-choice/vocabulary) — semantic signals are carried by turn-level fields and never double-counted as an extra issue.

Applying that rule by re-deriving each affected case's spans word-by-word surfaced **6 cases with wrong counts, not the 1 the audit named**:

| Case | Text | Before | After (explicit spans) |
|---|---|---|---|
| **1** | `"yes i want a coffee"` | 1 issue implied ("capitalize 'I'") | 2: "yes"→"Yes", "i"→"I" |
| **9** | `"yes please Ill take one"` | 1 issue implied (apostrophe only) | 2: "yes"→"Yes", "Ill"→"I'll" |
| **11** | `"yes i visited japan last year"` | 2 issues ("I", "Japan") | 3: "yes"→"Yes", "i"→"I", "japan"→"Japan" |
| **43** (named) | `"i want a jaket thats waterproof and i dont like the blue ones"` | 4 ("capitalization ×2, spelling, punctuation 'thats'/'dont'" — the last written as one entry) | 5: capitalization "i"→"I" (1st), spelling "jaket"→"jacket", punctuation "thats"→"that's", capitalization "i"→"I" (2nd), punctuation "dont"→"don't" |
| **44** | `"no i dont have alergies but my friend have"` | 4 ("capitalization" written as one entry) | 5: capitalization "no"→"No", capitalization "i"→"I", punctuation "dont"→"don't", spelling "alergies"→"allergies", subject-verb "friend have"→"friend has" |
| **45** | `"i has three class on monday and i dont like it"` | "at least 4" ("capitalization ×2" — actually ×3, and "monday" was missing entirely) | 6: capitalization "i"→"I" (1st), subject-verb "has"→"have", plural "class"→"classes", capitalization "monday"→"Monday", capitalization "i"→"I" (2nd), punctuation "dont"→"don't" |

The pattern in every miss was the same: a sentence-initial lowercase interjection or connective ("yes," "no") needing its own capitalization fix, separate from a pronoun "i" later in the same sentence, was being folded into a single "capitalization" mention instead of counted as 2 (or, for case 45, 3) separate spans.

### 2.3 Ambiguous "X or Y" values (audit item 4)

A `grep` for `or`/`likely`/`at least`/`probably`/`maybe` across every expected-value field (excluding quoted prior-context text and the meta-level procedure/grading sections, which aren't per-case expected values) found exactly 3 real violations — confirming there were no others hiding beyond what a careful case-by-case read located:

| Case | Before | After |
|---|---|---|
| **30** | `relevance=LOW or NONE` | `relevance=LOW` — resolved definitively rather than to NONE, specifically because doing so gives the dataset actual coverage of the LOW value that §4's adjacent-tolerance tier for `answer_relevance` references but no other case exercises. Also added `meaning=PRESERVED`, `grammar=CORRECT` (present in the text but previously unstated). |
| **32** | `completeness=PARTIAL or MINIMAL`, `requires_clarification likely true` | `completeness=PARTIAL`, `requires_clarification=true`. Also added `meaning=PRESERVED`, `grammar=MINOR_ERRORS (1 issue: capitalization "just"→"Just")` (previously unstated). |
| **33** | `meaning=UNCLEAR or completeness=MINIMAL`, `requires_clarification likely true` | Both stated as separate definitive fields — `meaning=UNCLEAR` **and** `completeness=MINIMAL` (this was never really an either/or; the two fields answer different questions and both are true) — plus `requires_clarification=true`. Also added `relevance=FULL`, `grammar=CORRECT` (previously unstated). |

### 2.4 Missing required fields (found while auditing items 4 and 6)

Beyond the ambiguous-value cases above, one more case in the same category was missing fields outright (not merely ambiguous):

| Case | Before | After |
|---|---|---|
| **31** | Only `meaning`, `requires_clarification`, `semantic_confidence` stated | Added `relevance=FULL`, `completeness=PARTIAL`, `grammar=MINOR_ERRORS (1 issue: capitalization "the"→"The")` |

### 2.5 `semantic_confidence` normalization-rule violation (found while verifying audit item 5)

Item 5 asked me to verify the normalization rules are deterministic. Doing that meant checking every case against them, not just restating the rules — which surfaced a real, previously undetected conflict between two of the document's own rules:

| Case | The problem | Fix |
|---|---|---|
| **15** | `meaning=SLIGHTLY_WRONG` was stated, but `semantic_confidence` was never given. The **default-expectation rule** says an unstated `semantic_confidence` defaults to `null`. The **normalization rule** says `meaning ∈ {CHANGED, SLIGHTLY_WRONG}` must **never** be `null`. Case 15 sat in the gap between these two rules — a literal machine reading would have produced a contradiction. | Added `semantic_confidence=CONFIDENT, requires_clarification=false`, using the same reasoning already given for its category sibling case 13 (an unambiguous tense mismatch, not a word-meaning question). |

I re-verified this rule against all 6 cases with `meaning ∈ {CHANGED, SLIGHTLY_WRONG}` (13, 14, 15, 16, 17, 18) — case 15 was the only gap; the other 5 already stated (or, for case 14, correctly inherited via "same shape as #13") an explicit value.

### 2.6 Document-level fixes (structure and clarity, self-initiated)

| Item | Fix |
|---|---|
| **New §2.0 "Ground rules"** | Added ahead of the case list: the issue-granularity rule, the 5 `semantic_confidence` normalization rules (restated from the plan so the spec is machine-runnable standalone), and the default-expectation rule (`requires_clarification=false`, `semantic_confidence=null` unless a case states otherwise). This is the section that makes the case-by-case fixes above actually enforceable instead of ad hoc. |
| **§4 grading criteria, "categories" terminology** | Two adjacent bullets used the word "categories" to mean two different things — case numbers in one sentence ("categories 16-18"), section numbers in the next ("categories 8-9," "category 10"). A runner implementing the grading logic could not tell which was meant without cross-checking by hand. Disambiguated to explicit `§2.X` (sections) vs. "cases N-M" (individual cases) throughout §4, matching the one place the document already did this correctly (`Category 2.16 (cases 46-48)`). |
| **§2.0's own cross-reference** | The ground-rules section, when first written, said the "or"-style values had appeared in "Section 2.11 and 2.15." Re-verifying against the actual fix list above, the real locations were **§2.10 and §2.11** (cases 30, 32, 33) — §2.15 (multiple-simultaneous-errors) never had an "or" value, it had the separate issue-count bug. Corrected before this report was ever written, so no reader sees the wrong self-reference. |

---

## 3. Confirmation that all 48 cases are internally consistent

Every case was checked against: exact learner input, expected grammar errors, expected relevance, expected completeness, expected meaning, expected issue count, and expected clarification behavior (audit item 6). This re-check was done by direct re-inspection of the current `AI_TUTOR_SEMANTIC_EVALUATION_SPEC.md` — reading all 48 numbered cases and identifying, for each, whether it carries a fix marker not present in the document's baseline pattern (an explicit "N issues:"/"N distinct entries" count, an added field, a changed answer string, or added justification prose) — cross-checked against this session's own edit history rather than taken from the prior version of this report.

**Conclusion: the dataset itself was correct. Only the previous version of this report's summary counts were wrong** (see the correction note in §1). No case's expected values were changed as part of producing this corrected report.

### 3.1 Machine-checkable accounting

```
Total cases: 48
Modified cases: [1, 9, 11, 15, 16, 25, 30, 31, 32, 33, 43, 44, 45]
Modified count: 13
Unchanged cases: [2, 3, 4, 5, 6, 7, 8, 10, 12, 13, 14, 17, 18, 19, 20, 21, 22, 23, 24, 26, 27, 28, 29, 34, 35, 36, 37, 38, 39, 40, 41, 42, 46, 47, 48]
Unchanged count: 35
Overlap: none
Missing cases: none
13 + 35 = 48
```

- **Disjointness**: no case number appears in both lists.
- **Coverage**: every integer 1 through 48 appears in exactly one of the two lists (verified by walking 1→48 and marking each against both).
- Every `"same shape"` backreference (cases 5, 6, 8, 9, 11, 14, 20, 21, 29, 35, 36, 38, 39, 47, 48) was traced to confirm it resolves to a fully-specified antecedent earlier in its own category — none point to an underspecified case, and none of these cases were themselves modified.
- Cases 40-42 (contradictions) and the wording in case 8 were reconfirmed as intentionally exempt / already correct, not overlooked.

All 48 cases carry a complete, unambiguous set of expected values, consistent with both each other and with the two normalization-rule sets (`derive_overall_status` precedence and `semantic_confidence` normalization) they're meant to test.

## 4. Is the dataset machine-runnable?

**Yes.** Specifically:
- No case expresses an expected value as "A or B" — every field is a single definite value or, where the schema itself allows a set (e.g. `semantic_confidence ∈ {CONFIDENT, PROBABLE, UNCERTAIN}` when meaning is CHANGED/SLIGHTLY_WRONG), an explicit closed set, never bare prose.
- Every case has an explicit or unambiguously-inherited value for `answer_relevance`, `completeness`, `meaning_status`, and `grammar_status`.
- `semantic_confidence` and `requires_clarification` are either stated explicitly or resolve via the now-explicit default-expectation rule — and that rule no longer conflicts with the normalization rule for any case (the case-15 gap was the only one and is closed).
- The issue-granularity rule gives a single, consistently-applied definition of "issue count" that a runner can check by counting `issues[]` array length, with no case left at a stale or ambiguous count.
- §2.0 restates the normalization rules inline, so the spec document is self-contained and doesn't require cross-referencing the plan document at run time.

## 5. Is the design READY FOR IMPLEMENTATION?

**No change from the prior review's conclusion, restated precisely: ready for the real-provider evaluation run (plan §15), not yet ready for full implementation.**

This audit fixed the dataset itself — it did not run it. The gate that matters (whether the actual configured provider, given the actual prompt, produces outputs that pass this dataset's now-unambiguous criteria) still has not been exercised. Nothing in this pass changes that; if anything, this pass is a precondition for that run being meaningful, since a runner executing the previous version of the dataset would have hit real ambiguities (cases 30/32/33's "or" values, case 15's rule gap) it had no principled way to resolve on its own.

**Next gated step, unchanged from before**: build the small, temporary, non-CI script described in §3, run it once against the real provider, grade against §4's now-fully-disambiguated criteria, and only then revisit the implementation question — per `AI_TUTOR_CONVERSATION_INTELLIGENCE_PLAN.md` §15's existing gate.

---

## 6. What was not done (per the explicit constraints of this review)

No application code was modified. No migrations were created. No commits or pushes were made. `git status --short` at the end of this pass shows only markdown planning documents as untracked/changed:

```
?? AI_TUTOR_CONVERSATION_INTELLIGENCE_AUDIT.md
?? AI_TUTOR_CONVERSATION_INTELLIGENCE_PLAN.md
?? AI_TUTOR_SEMANTIC_EVALUATION_SPEC.md
?? AI_TUTOR_PREIMPLEMENTATION_CONSISTENCY_REPORT.md
?? graphify-out/
```

(`graphify-out/` is unrelated output from a separate, still-in-progress `/graphify` knowledge-graph pipeline run and is not part of this audit.)
