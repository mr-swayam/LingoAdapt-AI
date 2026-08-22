# AI Tutor V4.1 Policy Calibration — Real-Provider Test Report

Status: **Calibration test complete. 23/23 real API calls executed exactly as pre-committed in `AI_TUTOR_V4_1_POLICY_PLAN.md` §6. No production code, migrations, commits, or pushes were made.** The revised schema, prompt, and guards exist only in a temporary, disposable script outside `backend/app/`.

**Headline: the calibration test FAILED against the locked zero-tolerance bar (12/15 = 80%, not the required 100%), on a single, narrow, well-characterized case — E9.** Every other case, including both of the two specific policy fixes this round exists to validate (E4's ordinal-reference policy, E5's off-topic/`OFF_TOPIC` fix), passed cleanly and consistently. Full detail below, including a new failure mode this run surfaced that neither of the prior two rounds exposed: **roleplay-induced fact fabrication**, distinct from referential ambiguity.

**Operational note, disclosed for completeness**: this run required two restarts. The first attempt hit a sustained Groq rate-limit condition that turned out to be the account's **daily token quota** (197,057 of 200,000 tokens used, from the cumulative volume of all prior real-provider rounds today), not the usual per-minute limit — confirmed via a direct diagnostic call before any further retries were spent. The user supplied a fresh API key (same provider, same model — `AI_PROVIDER`/`AI_DEFAULT_MODEL` in `backend/.env` were not touched); the 23 calls below were run in full under that key, and the exhausted key's value was not restored. A second, unrelated interruption (a background-process/session boundary, not a rate limit) stopped a subsequent attempt before any call completed; the script was made to save results incrementally after every call specifically so that a future interruption would not lose completed work, though this run in fact completed in full without needing that safety net.

---

## 1-2. Provider/model and call count

Groq, `openai/gpt-oss-120b` — identical to every prior round, model not substituted. **23 of 23 pre-committed calls**: 5 zero-tolerance cases (E1, E2, E3, E8, E9) × 3 runs = 15, 2 policy-confirmation cases (E4, E5) × 2 runs = 4, 3 standard-tier cases (E6, E7, E10 — E10 at 2 runs) = 4. `15 + 4 + 4 = 23`. Every repeated run was built fresh from the case's static definition; no run's response was fed into another run's input.

## 3. Every case and every repeated run — raw vs. normalized

**E1 — D1 regression: red/new shoes (UNSAFE), zero-tolerance, 3 runs**

All 3 runs: `meaning_status=CHANGED`, `context_resolution=CONFLICTING`, `learner_intent_known=false`, `clarification_required=true`, `corrected_sentence=null`. **3/3 PASS**, no instability.

**E2 — D2 regression: apples/oranges (SAFE), zero-tolerance, 3 runs**

All 3 runs: `context_resolution=CONFLICTING`, `learner_intent_known=true`, `clarification_required=false`, `corrected_sentence` non-null and correctly preserving "oranges" in every run (never substituted to "apples"). **3/3 PASS**. `context_feedback` across the 3 runs: "a safe alternative," "it's fine to mention a different fruit," "which changes the meaning of the response" — all three correctly note the substitution without treating it as an error requiring correction.

**E3 — D3 regression: the other one (AMBIGUOUS), zero-tolerance, 3 runs**

All 3 runs: `context_resolution=AMBIGUOUS`, `learner_intent_known=false`, `clarification_required=true`, `corrected_sentence=null`, identical reply ("Do you mean the blue one or the green one?") every time. **3/3 PASS**, zero instability.

**E4 — D4 under the new ordinal-reference policy, policy-confirmation, 2 runs**

Both runs: `context_resolution=CLEAR`, `clarification_required=false` — the model correctly resolved "the first one" to "chicken" from its own immediately-preceding offer, exactly as the accepted policy specifies. **2/2 PASS.** (Minor, non-criterion variance: run 1's `completeness=MINIMAL` vs. run 2's `COMPLETE` — cosmetic, not part of the locked criteria for this case.)

**E5 — D6 fix re-test: off-topic weather, policy-confirmation, 2 runs**

Both runs: `meaning_status=PRESERVED`, `overall_status=OFF_TOPIC` (not `UNCLEAR`) — the exact, direct confirmation that the off-topic/meaning-status bug is fixed. **2/2 PASS.** Notably, `meaning_status_pre_guard` was already `PRESERVED` in both runs — the model got this right on its own; the `enforce_offtopic_meaning` deterministic guard was not needed to correct it (see §5).

**E6 — Off-topic answer with grammatical errors, standard, 1 run**

`answer_relevance=NONE`, `meaning_status=PRESERVED`, `grammar_status=MINOR_ERRORS` with exactly 1 issue (`realy`→`really`), `clarification_required=false`, `corrected_sentence="The weather is really nice today."` (non-null, the mechanical fix shown despite the answer being off-topic), `overall_status=OFF_TOPIC`. **PASS** — direct confirmation that forcing `meaning_status=PRESERVED` on off-topic answers does not suppress a genuine, unrelated mechanical correction.

**E7 — Partial but relevant answer, standard/regression, 1 run**

`answer_relevance=FULL`, `completeness=PARTIAL`, `meaning_status=PRESERVED`, `clarification_required=false`. **PASS**, clean.

**E8 — Clear conflicting answer, non-canonical pair (Paris/Rome → Tokyo), zero-tolerance, 3 runs**

All 3 runs: `context_resolution=CONFLICTING`, `learner_intent_known=true`, `clarification_required=false`. **3/3 PASS on the core criteria.** One test-design imperfection, disclosed rather than hidden: "I'd rather go to Tokyo." is already grammatically clean (no capitalization/punctuation issues), so `grammar_status=CORRECT` and `corrected_sentence=null` in all 3 runs — the locked criterion "`corrected_sentence` must preserve 'Tokyo'" was written assuming a mechanical correction would be produced (as it was for E2's apples/oranges), and this specific non-canonical example didn't need one. The criterion is satisfied *vacuously* (nothing was ever asserted, so nothing could have been silently substituted) rather than *meaningfully exercised* — a minor gap in this test's design, not a model failure; run 2's `context_feedback` ("You chose Tokyo, but I asked about Paris or Rome") shows the model correctly treating Tokyo as the learner's own deliberate answer regardless.

**E9 — Genuinely ambiguous reference, different shape ("Whichever is cheaper."), zero-tolerance, 3 runs**

| Run | `context_resolution` | `learner_intent_known` | `clarification_required` | `corrected_sentence` | Notable |
|---|---|---|---|---|---|
| 1 | **CLEAR** (expected AMBIGUOUS) | true | **false** | "I would like whichever is cheaper." | Reply: *"The small size is $5 and the large is $8. Which one would you like?"* — **fabricated prices**, never stated anywhere in the conversation |
| 2 | **CLEAR** | true | **false** | null | Reply: "Sure, I'll find the cheaper option. Do you have a preferred color?" — no fabricated numbers this run, but still resolved as safe/clear |
| 3 | **CLEAR** | true | **false** | null | Reply: *"The small size is $5 and the large is $8. Would you like the cheaper one then?"* — **fabricated prices again, the identical figures as run 1** |

**E9: 0/3 PASS — the only zero-tolerance failure in this round, and a worse failure shape than a simple misclassification.** See §6 for root-cause analysis — this is not the same mechanism as D4's (defensible) ordinal-reference reading or D6's (now-fixed) off-topic conflation; it is a new failure category this round specifically surfaced.

**E10 — Repeated identical grammar errors, regression, 2 runs**

Both runs: `meaning_status=PRESERVED` ✓, `clarification_required=false` ✓, but `issues[]` contained only **2** occurrence-tagged entries (occurrence 1, 2), not the expected 3 — a partial regression from the V4 round's D8/D9 results, which both achieved full 3-occurrence enumeration cleanly. In both runs, however, `corrected_sentence` correctly capitalized **all three** "I" occurrences ("I think I want the soup and I will get water too.") despite the structured `issues[]` array under-representing the count — the same "prose reasoning ahead of structured commitment" pattern seen elsewhere in this project's evaluation history (e.g. the original 48-case run's apples/oranges-shaped case, and V4's D8/D9 before they were fixed), now recurring specifically in the occurrence dimension. **Fails the full-enumeration criterion on both runs**; the learner-visible correction itself was accurate both times.

## 4. Results by evaluation tier

| Tier | Cases (runs) | Result |
|---|---|---|
| Zero-tolerance | E1, E2, E3, E8, E9 (15 runs) | **12/15 = 80%** — E1/E2/E3/E8 perfect (12/12); E9 failed all 3 |
| Policy-confirmation | E4, E5 (4 runs) | **4/4 = 100%** — both V4.1 policy fixes fully validated |
| Standard | E6, E7, E10 (4 runs) | E6, E7 clean; E10 partial (field-level pass, enumeration-count miss on both runs) |

## 5. Deterministic guard actions

**Zero guard actions fired across all 23 calls** — including the new `enforce_offtopic_meaning` guard (§2/§3 of the plan), which never needed to correct a single `meaning_status` value this round: every off-topic case (E5 ×2, E6) already reported `meaning_status=PRESERVED` on its own, confirmed by comparing `meaning_status_pre_guard` to the final value in every result (identical in all 23). **This is a stronger result than the guard merely being present as a backstop** — it indicates the prompt-level fix (rule 11a) was sufficient on its own this round. The guard remains justified as defense-in-depth (§3 of the plan's own reasoning: a guaranteed invariant should not depend on the prompt being followed perfectly every time), and this result does not argue for removing it.

## 6. Root cause of E9 — a new failure category, not a repeat of D4 or D6

**This is not the same mechanism as either fix this round targeted.** E3 (a structurally similar ambiguous-reference case, "the other one") passed 3/3 in the identical run — so the model's general capacity to recognize unresolved references is intact. The prompt (rule 17) explicitly named "whichever is cheaper" as the textbook example of `AMBIGUOUS` when information is missing, and the model still did not apply it, in any of 3 independent runs.

**The most likely, evidence-supported explanation**: this scenario places the model in a **shopkeeper role** (rule 8: "stay in character for the scenario"). A real shop assistant would, of course, know their own prices — so staying convincingly in character pulls the model toward *acting as if it has the information* (and inventing plausible numbers to sound authoritative) rather than acknowledging a genuine informational gap. Two of the three runs did exactly this, fabricating specific dollar figures never present anywhere in the conversation — and the identical figures appearing in both fabricating runs ($5/$8) suggest a generic, template-like "small/large pricing" pattern drawn from training data rather than a random guess each time, which does not make it acceptable but does help explain why it recurred consistently rather than varying.

**This is a materially different, and in one sense more concerning, risk than either D4 or D6**: D4 was a defensible disagreement about a real linguistic rule; D6 was a classification bug with no invented content. **E9's failing runs invent facts that were never established anywhere in the conversation** — a distinct category the review request's "OFF_TOPIC != UNKNOWN_INTENT" framing does not directly cover, and which the existing `context_resolution` taxonomy was not designed to catch (the taxonomy asks "can this reference be resolved," not "is the model about to state something as fact that it has no basis for"). **Recommended framing for the next design pass**: a rule distinguishing "resolving a reference from context already given" (safe, what `CLEAR` correctly protects) from "supplying invented specifics a character role would plausibly know but the conversation never established" (unsafe, currently unprotected) — this is a roleplay-fabrication guard, not a re-tuning of the ambiguity taxonomy that already works.

**Also worth naming honestly**: this test's own design may have set up the tension it found — "whichever is cheaper" specifically invites a shopkeeper character to supply prices, in a way "the other one"/"the first one" never invite the model to supply anything beyond a color or dish name it was already given. A future test of this same general risk should probably use an off-topic-to-the-scenario missing fact (e.g., asking about something no shopkeeper would obviously know) to isolate the fabrication risk more cleanly from the roleplay-competence signal.

## 7. Instability across repeated calls

**E1, E2, E3, E8: no instability** — identical qualitative behavior across all runs each. **E9: instability of a genuinely concerning shape** — 2 of 3 runs fabricated specific prices, 1 did not; this is not a coin-flip between "safe" and "unsafe" the way earlier rounds' unstable cases were, it is a coin-flip between two different flavors of the same wrong classification, with the more severe flavor (fabricated facts) appearing in the majority of runs. **E10: stable but consistently short** — both runs identically under-enumerated by exactly 1 occurrence, not a sampling fluke.

## 8. Errors or malformed responses

**Zero, within the 23 official calls.** All returned valid, schema-conformant JSON on the first attempt. Two hard failures occurred *before* this official run (documented separately, not counted in the 23): the daily-quota exhaustion on the original API key, diagnosed via direct raw-error inspection rather than assumed, and one background-process interruption unrelated to the API itself.

## 9. Latency/cost observations

| Metric | Value |
|---|---|
| Total real API calls (official run) | 23 / 23 successful |
| Prompt tokens | sum 48,970, avg 2,129/call |
| Completion tokens | sum 18,836, avg 819/call, min 340, max 1,400 |
| Total tokens (23 calls) | 67,806 |
| Latency (model only) | avg 2,852ms, min 1,471ms, max 4,874ms |
| Wall-clock time | 441.7s (~7.4 min), mostly ordinary per-minute rate-limit waits (7-34s), not the daily-quota condition seen earlier |
| Dollar cost | Not stated, same discipline as every prior report |

## 10. Confirmation that no criteria changed after seeing results

**Confirmed.** The 10-case, 23-call structure and every per-case expectation (including E4's revised ordinal-policy expectation and E9's AMBIGUOUS expectation, both locked in `AI_TUTOR_V4_1_POLICY_PLAN.md` §6 before this run) were fixed before the first API call of this round. E9's grading (FAIL, 0/3) and E10's grading (partial fail on enumeration count) are both reported exactly against those pre-locked criteria. §6's root-cause analysis is offered as input to the *next* design iteration, not as grounds to relax this round's verdict.

---

## Final verdict

## **FAILED — the locked zero-tolerance gate is not met (12/15 = 80%, not 100%).**

Per the plan's own pre-committed gate ("100% required on the zero-tolerance tier... to authorize the 48-case re-evaluation"), this is dispositive: **E9 failed all 3 runs.** This does not authorize the 48-case re-evaluation, and per the explicit constraint on this task, this report does not claim READY FOR IMPLEMENTATION.

**This is, by a clear margin, the narrowest and most specific failure surface of the three calibration rounds run so far.** Both of this round's actual purposes — validating the ordinal-reference policy (E4) and fixing the off-topic/`OFF_TOPIC` classification bug (E5, plus E6's coexistence check) — succeeded completely and cleanly, 4/4, with the deterministic guard confirmed unnecessary because the prompt fix alone was sufficient. Every regression case for the prior round's hard-won fixes (E1, E2, E3) held perfectly. The generalization case for the safe-substitution mechanism (E8) held. The single failure (E9) is a newly-discovered, precisely-characterized, and previously-unseen risk category — roleplay-induced fact fabrication — that is mechanistically distinct from every failure this project has found before it, not a recurrence of an old one.

**Recommended next-round scope, narrow and targeted, per this run's own findings**: (1) add an explicit prompt rule prohibiting the model from stating specific facts (prices, quantities, specifications) as if established when they were never given in the conversation, distinguishing this from the already-working reference-resolution rules; (2) separately, fix E10's occurrence-enumeration undercount, likely with a similar reasoning-order instruction to the one that fixed D6 ("before finalizing `issues[]`, count every occurrence of each mechanical error type explicitly, then verify `corrected_sentence` reflects the same count"); (3) reconsider whether "whichever is cheaper" is a clean test of ambiguity-under-missing-information or whether it conflates that with the new fabrication risk, and adjust the next calibration case accordingly if so.

---

## What this report does not do

Does not modify `backend/app/`. Does not add or alter any schema, model, or migration. Does not modify the production system prompt. Does not run the 48-case dataset. Does not commit or push. The calibration script and raw results live only in this session's scratchpad directory, outside the project's git repository. `backend/.env`'s `AI_API_KEY` was updated to the user-supplied replacement key (same provider, same model) after the original key's daily quota was confirmed exhausted; no other configuration was changed.
