# Improvement Changelog

How this solution evolved, one entry per meaningful experiment. Every number comes from
`src/eval/` scoring the same 24-posting corpus (`CORPUS_SEED=42`) under the protocol frozen
in [`EVAL.md`](EVAL.md) before any of it was measured.

Entries are written when the experiment runs, not reconstructed afterwards.

| Stage | What was tried and why | Evidence | Decision / learning |
|---|---|---|---|
| **Baseline** | One direct prompt, one pass, no help | **F1 0.789** (0.789–0.850 over 3 runs) | Verdicts already perfect; the failure is *attribution*, not detection |
| **Iteration 1** | Taxonomy definitions instead of bare ids — the failures looked like a vocabulary problem | **F1 0.914** (+0.125) · precision 0.750 → 0.941 | **Kept.** Confusable-pair errors eliminated; remaining misses are all on multi-blocker postings |
| **Iteration 2** | Four independent per-group checks, merged — iteration 1 found one blocker and stopped | **F1 0.850** (−0.064) · recall 0.889 → 0.944, precision 0.941 → 0.773 | **Removed.** Hypothesis confirmed *and* the change lost: narrowing the question removed the cross-group competition that suppressed marginal claims |
| **Iteration 3** | Every claim must quote the posting verbatim (on top of decomposition) | **F1 0.865** · evidence-correct **0% → 100%** | Precision partly recovered, but still short of iteration 1 at 2× the cost |
| **Iteration 3s** | The same evidence requirement with decomposition **removed** — the isolation test | **F1 0.895** · recall 0.944 · evidence 100% · **$0.0042/task, the cheapest variant** | **Kept.** Evidence was doing all the work; decomposition was contributing nothing but cost |
| **Iteration 3s + grounding** | Drop any claim whose quote is not in the posting — mechanical, no API call | **F1 0.919** · precision 0.850 → 0.895 · hallucination → 0% | **Kept.** Free, deterministic, no regressions |
| **Iteration 4** | Ask the model whether each quote states its condition; reject-only | **F1 0.909** · precision **1.000** · recall 0.944 → **0.833** · decision accuracy 100% → **91.7%** | **Half kept.** Perfect precision bought by rejecting two real blockers — the verifier could not see the profile, so it could not judge relational conditions |
| **Iteration 5** | Give the verifier the profile field its condition is decided by | **F1 0.914** · recall 0.833 → 0.889 · decision accuracy 91.7% → **95.8%** | **Removed.** Partial recovery only, and still worse than no verifier at all on the user-facing metric |
| **Final** | Definitions + verbatim evidence + mechanical grounding, one call | **F1 0.944** (median of 3) · recall 0.944 · evidence 100% · decision accuracy **100%** · **$0.0045/task** | The configuration that survives |

---

## Before the baseline: two harness corrections

Neither is an iteration. Both changed what the baseline number means, so recording them is
part of connecting the claim to the evidence.

**The scorer reported a perfect F1 on an empty run.** `EVAL.md` §4's zero-denominator
conventions compose to precision 1.0 and recall 1.0 when nothing has been scored, giving
F1 = 1.0. A run that crashed before scoring anything would have reported a flawless
result — the most dangerous possible wrong number, on the primary metric, in exactly the
situation where a hoped-for result is least likely to be questioned. `aggregate()` now
refuses an empty match list.

**The baseline's prose was being misread by my own parser.** The 3-posting smoke run cost
$0.02 and was wrong on two of three, in both directions:

| Model actually wrote | Parser scored it | Reality |
|---|---|---|
| "No hard disqualifiers found — worth applying to" | SKIP | the model was right; the word "disqualifiers" matched under a negation |
| "your 6 years of experience clears the 5+ requirement" | claimed a `years_of_experience` blocker | a sentence saying the requirement was **satisfied** |

Left in place, the reported baseline would have measured regex quality, and "the agent
beat the baseline" would have meant "the agent beat my parser". The prompt now asks for a
declared `VERDICT:` / `BLOCKERS:` line and the parser reads only that
([`EVAL.md` §10 amendment, 2026-08-31](EVAL.md)). This makes the baseline **stronger** and
the eventual improvement **smaller**.

---

## Baseline — one direct prompt

**What and why.** The reasonable basic approach: posting, profile, the 14 blocker ids as
bare names, and "Should I apply?". No definitions of what those ids mean, no
per-category decomposition, no verification pass, no evidence requirement, no structured
output. It exists to be the number every later iteration is measured against, so its
prompt is never tuned (`EVAL.md` §9).

**Evidence.** Three runs, 24 postings each, `claude-sonnet-5` at `effort=medium`, $0.36 total.

| Metric | Run 1 | Run 2 | Run 3 | **Median** | Spread |
|---|---|---|---|---|---|
| **Detection F1** | 0.789 | 0.850 | 0.789 | **0.789** | **0.061** |
| Recall | 0.833 | 0.944 | 0.833 | 0.833 | 0.111 |
| Precision | 0.750 | 0.773 | 0.750 | 0.750 | 0.023 |
| Decision accuracy | 1.000 | 1.000 | 1.000 | **1.000** | 0.000 |
| Clean-posting false alarms | 0/8 | 0/8 | 0/8 | 0/8 | — |
| Evidence-correct rate | 0% | 0% | 0% | 0% | — |
| Cost per task | $0.0051 | $0.0049 | $0.0049 | $0.0049 | — |

**Learning 1 — the predicted failure mode did not occur.** `plan.md` §5 predicted an
agreeable, single-pass system that would miss footer-displaced blockers and conflate
"preferred" with "required". It did neither. Every apply/skip verdict was correct in all
three runs, and not one of the eight distractor postings was flagged. The prediction is
left in `plan.md` as written rather than quietly revised.

**Learning 2 — the errors are two confusable pairs, and nothing else.** Across all three
runs, every false positive was one of two types:

```
work_authorization    claimed 9 times where it did not apply
relocation_required   claimed 6 times where it did not apply
```

Both are semantic neighbours of the correct answer: ITAR citizenship read as a visa
question, and "must reside within commuting distance" read as relocation. `jd_16` is the
clearest case — gold is `citizenship_required` + `professional_licensure`, and the
baseline reported only `work_authorization`. The verdict was still SKIP and still correct.

This matters to the user, not just to the score. A tool that says "you are blocked on work
authorization" sends an applicant looking for a sponsor, for a role where no sponsor can
help, because the bar is citizenship.

**Learning 3 — one blocker was missed in all three runs.** `professional_licensure`, in
its footer phrasing: *"Licensure will be verified with the state board prior to an offer
being extended."* This was flagged during the step 2.6 corpus audit as possibly too vague
to be fair — it presupposes a licence requirement without stating one. Missing it 3/3
supports that reading. Whether it is a hard case or an unfair one is still open; the
report will say which, and will not claim credit for a later system solving a defect in
the corpus.

**Learning 4 — the bar for claiming any improvement is now a number.** The baseline's own
F1 varies by **0.061** across three identical runs. Under `EVAL.md` §8, no iteration may
be reported as an improvement unless it beats that. This is the most consequential result
of the phase: it rules out declaring victory on a two- or three-point gain, which is the
size of gain a prompt tweak typically produces.

**Decision.** Keep the corpus as it is. `steps.md` 4.4 suggested hardening it if the
baseline scored well, but that note was written to guard against a *weak* baseline. Here
the failures are specific and mechanistic, so hardening now would be moving the goalposts.
There is ample headroom without it: F1 0.789 → 1.0, fifteen false positives with a known
cause, and evidence at 0%.

**Next.** Iteration 1 gives the model the taxonomy *definitions* rather than bare ids, on
the hypothesis that the two confusable pairs are a vocabulary problem — the model cannot
distinguish ITAR citizenship from visa sponsorship when it has only been shown the labels'
names. Predicted effect: precision rises, recall roughly unchanged. If precision does not
move, the confusion is not about vocabulary and the next iteration should target
something else.


---

## Iteration 1 — taxonomy definitions in context

**What and why.** The baseline was given the 14 blocker ids as bare names. Every one of its
false positives was a confusion between two semantic neighbours, so the hypothesis was that
this is a *vocabulary* problem: the model cannot separate ITAR citizenship from visa
sponsorship when it has only been shown the labels' names. Iteration 1 adds each blocker's
description and — the load-bearing part — **which profile field decides it**:

```
- work_authorization (legal): Role does not offer visa sponsorship.
  Decided by the profile field `work_auth`.
- citizenship_required (legal): Employment restricted to U.S. citizens or
  ITAR-defined U.S. Persons. Decided by the profile field `citizenship`.
```

Nothing else changed. Same model, same effort, same corpus, same output format, same single
pass, same parser. Structured output was deliberately *not* bundled in: the baseline already
had 0% parse failures, so it had nothing to fix and would only have confounded the result.

**Predicted before running:** precision rises, recall roughly flat. If precision did not
move, the confusion was not about vocabulary and iteration 2 would have to target something
else.

**Evidence.** One run (EVAL.md §8 — intermediate iterations get a single run), $0.12.

| Metric | Baseline (median of 3) | Iteration 1 | Change |
|---|---|---|---|
| **Detection F1** | 0.789 | **0.914** | **+0.125** |
| Precision | 0.750 | 0.941 | +0.191 |
| Recall | 0.833 | 0.889 | +0.056 |
| False positives | 5 | 1 | −4 |
| Decision accuracy | 100% | 100% | — |
| Cost per task | $0.0049 | $0.0050 | +$0.0001 |

**The gain clears the noise floor.** The baseline's own F1 varies by 0.061 across three
identical runs; this gain is 0.125, roughly double that. Under EVAL.md §8 it is reportable.
The caveat is stated rather than buried: iteration 1 is a single run compared against a
three-run baseline median, so the *size* of the gain is less certain than its direction.

**The predicted mechanism is visible in the errors, not just the totals.** The confusable
pair that caused every baseline false positive is gone:

| False positives by type | run 1 | run 2 | run 3 | Iteration 1 |
|---|---|---|---|---|
| `work_authorization` | 3 | 3 | 3 | **0** |
| `relocation_required` | 2 | 2 | 2 | **1** |

Nine spurious `work_authorization` claims across three baseline runs, zero here. That
consistency is what makes this a confirmed mechanism rather than a lucky run.

**What is left, and it is a different failure.** Both remaining misses are on
multi-blocker postings, and in both the model found one blocker and stopped:

```
jd_04  gold: employment_type + citizenship_required   claimed: citizenship_required
jd_16  gold: citizenship_required + professional_licensure   claimed: citizenship_required
```

`jd_16` is still an improvement — the baseline found *neither* of its blockers and invented
a third; iteration 1 finds one of two and invents nothing. But the shape of the error has
changed from *wrong answer* to *incomplete answer*.

**An unplanned observation on cost.** Input tokens rose from 20.7K to 35.4K (the definitions
block), but output fell from 8.0K to 4.8K, so cost per task was flat at $0.005. More context
made the model more decisive rather than more verbose. Worth remembering before assuming a
richer prompt costs more.

**Decision — kept.** The hypothesis held, the mechanism is visible, and the gain exceeds the
noise floor.

**Next.** Iteration 2 tests the new failure: a single pass appears to anchor on the first
blocker it finds and stop looking. Checking each taxonomy group independently and merging
the results should recover the second blocker on multi-blocker postings. Predicted effect:
recall rises on the `multi` bucket specifically, precision roughly flat. `professional_licensure`
in its footer phrasing has now been missed in all four runs, and remains a suspected corpus
defect rather than a system failure — see the step 2.6 audit note.


---

## Iteration 2 — per-group decomposition

**What and why.** Iteration 1's two remaining misses were both multi-blocker postings where
the model named one blocker and stopped. So: four independent calls per posting, one per
taxonomy group (legal / logistics / credentials / terms), each shown only its own
conditions, results merged and deduplicated. Nothing else changed.

**Predicted before running:** recall rises on the `multi` bucket specifically; precision
flat or slightly down, since four chances to claim something is four chances to claim
something wrong; cost roughly doubles.

**Evidence.** One run, $0.30.

| Metric | Iteration 1 | Iteration 2 | Change |
|---|---|---|---|
| **Detection F1** | **0.914** | **0.850** | **−0.064** |
| Recall | 0.889 | 0.944 | +0.056 |
| Precision | 0.941 | 0.773 | −0.168 |
| False positives | 1 | 5 | +4 |
| Cost per task | $0.0050 | $0.0124 | ×2.5 |

**The hypothesis was confirmed. The change still lost.** `jd_04` is exactly the case it was
built for — iteration 1 found `citizenship_required` and stopped; iteration 2 recovered
`employment_type` as well. Recall rose precisely where predicted.

But precision fell nearly three times as far as recall rose, and F1 went backwards by 0.064
— marginally beyond the 0.061 noise floor, so a real regression rather than noise, though
close enough that the margin is stated rather than glossed.

**Why it lost, which is the more useful finding.** Three of the four new false positives are
*within-group neighbours* of the correct answer:

```
jd_03  gold citizenship_required   →  also claimed work_authorization    (both legal)
jd_11  gold onsite_location        →  also claimed relocation_required   (both logistics)
jd_06  gold relocation_required    →  also claimed onsite_location       (both logistics)
```

Asking "check this posting for **legal** disqualifiers only" primes the model to find legal
disqualifiers. In a single pass the categories compete: a marginal `work_authorization`
reading loses to a strong `citizenship_required` one. Isolate the group and that competition
disappears, so the marginal claim survives.

**Decomposition traded cross-category suppression for within-category recall.** The
suppression was doing more work than the extra recall was worth. That is not something the
totals show — F1 alone says "worse" — it took the per-posting error breakdown to see that
the losses and the gains had different mechanisms.

**Decision — not kept on its own, carried forward as an input to iteration 3.** The four new
false positives are all claims the model cannot support with a quote: there is no sentence
in `jd_03` denying sponsorship, because the blocker there is ITAR citizenship. That is
precisely what a verification pass is for. Iteration 3 therefore tests decomposition *plus*
verification against iteration 1 directly:

- if it beats iteration 1, decomposition was worth keeping as a recall source that
  verification cleans up;
- if it does not, decomposition is removed and iteration 1's single pass stands.

Either outcome is reportable, and the removal case is written up rather than deleted.

**Cost note.** 2.5× the cost of iteration 1 for a worse score. If iteration 3 does not
recover the precision, this is a straightforward removal on both axes.


---

## Iteration 3 — verbatim evidence, and the removal of decomposition

**What and why.** Iteration 2's new false positives were all claims with nothing in the
posting to support them. Requiring a verbatim quote for every claim should make an
unsupportable claim harder to make: the model has to produce the sentence before it can
report the finding.

The output format changes to JSON here. That is a second change bundled into one iteration,
and it is forced rather than chosen — a quoted sentence does not fit on a comma-separated
line. Saying so is better than claiming a clean single-variable test.

**Predicted:** precision recovers toward iteration 1's 0.941 while keeping iteration 2's
recall; evidence-correct rises from 0% for the first time.

### Then the isolation test

Iteration 3 scored F1 0.865 against iteration 1's 0.914 — a 0.049 gap, *below* the 0.061
noise floor, so the two are indistinguishable on detection while iteration 3 costs twice as
much. That left an obvious question the changelog had already committed to answering: is
decomposition contributing anything, or is the evidence requirement doing all the work?

**Iteration 3s** answers it: the identical evidence requirement, one call, no decomposition.

| Variant | F1 | Recall | Precision | Evidence correct | Cost/task |
|---|---|---|---|---|---|
| Baseline | 0.789 | 0.833 | 0.750 | 0% | $0.0051 |
| Iteration 1 | **0.914** | 0.889 | **0.941** | 0% | $0.0050 |
| Iteration 2 | 0.850 | 0.944 | 0.773 | 0% | $0.0124 |
| Iteration 3 | 0.865 | 0.889 | 0.842 | **100%** | $0.0104 |
| **Iteration 3s** | 0.895 | **0.944** | 0.850 | **100%** | **$0.0042** |

**Decomposition is removed.** Iteration 3s beats iteration 3 on F1, matches it on evidence,
and costs 40% of it. Against iteration 1 the F1 gap is 0.019 — far inside the noise floor,
so detection is a wash — while evidence goes from 0% to 100% and cost *falls*. Four calls
per posting bought nothing that one call did not.

**What decomposition actually taught us.** It was not useless, it was mis-attributed. It
raised recall (0.889 → 0.944) and that gain survived into iteration 3s — which reaches the
same 0.944 with a single call. So the recall was never coming from splitting the question;
it was coming from *asking for a complete list* rather than an answer. Iteration 2's four
narrow prompts happened to do that, and its cost and precision loss were the price of a
side effect that could be had for free.

**The finding that matters most, and it is a negative one.** Requiring evidence did **not**
suppress unsupportable claims. All three remaining false positives are `work_authorization`
on postings that never mention sponsorship at all — the model reasons that silence about
sponsorship is itself a blocker. Asked for a quote, it supplied one anyway:

| Posting | Cited as proof of "no sponsorship" | Actually |
|---|---|---|
| `jd_12` | *"Role does not offer visa sponsorship."* | **not in the posting** — it echoed back the definition I gave it |
| `jd_14` | the equal-opportunity boilerplate | real sentence, unrelated |
| `jd_19` | *"4+ years in applied machine learning"* | real sentence, unrelated |

**A model asked for evidence will produce evidence-shaped text.** Requiring a citation is
not the same as requiring the citation to support the claim, and the hallucination rate
(5%) only caught the one case where the fabrication was detectable by string search. The
other two passed every automated check while proving nothing.

This is why the metric was split into *found* and *correct* — and it shows the split is
still not enough, because "found" only asks whether the sentence exists, not whether it
says what the claim needs it to say.

**Decision — iteration 3s kept, decomposition removed.** Iteration 2 and iteration 3 are
retained in `src/agent/variants.py` and in this changelog rather than deleted; the
comparison is the evidence for the removal.

**Next.** Iteration 4 adds the verification pass: a second call that sees each claim beside
its quote and may only *reject*, never add. It targets exactly the three surviving false
positives, all of which fail the question "does this sentence state this condition?".
Predicted: precision rises toward 1.0, recall unchanged, hallucination to 0%. If the
`jd_14` and `jd_19` claims survive verification, then quoting an unrelated real sentence is
enough to pass a checker too, and the next move is to make the verifier compare the quote
against the *condition* rather than against the posting.


---

## Iteration 4 — reject-only verification

**What and why.** Every false positive surviving iteration 3s was `work_authorization`
claimed on a posting that never mentions sponsorship, justified by a quote that was either
fabricated or real-but-unrelated. Two filters, both of which can only *remove* claims:

1. **Grounding** — mechanical: a quote that is not in the posting is not evidence.
2. **Relevance** — one short model call per surviving claim: does this sentence state this
   condition?

Neither may add a claim. A verifier that could add findings would be a second detector, and
its errors would be indistinguishable from the first pass's.

### The grounding filter — kept, and it was free

It required no API call at all, since it is a string search the harness was already able to
do. Applied to iteration 3s's existing output:

| | Iteration 3s | + grounding |
|---|---|---|
| **Detection F1** | 0.895 | **0.919** |
| Precision | 0.850 | 0.895 |
| Hallucinated quotes | 5% | **0%** |
| Recall / decision accuracy | 0.944 / 100% | unchanged |
| Cost | $0.0042 | **$0.0042** |

The single claim it dropped was the fabricated citation on `jd_12` — the model had quoted
back *my own definition text* as though it were a line from the posting.

### The relevance verifier — did what was asked and cost more than it gained

**Predicted:** precision rises toward 1.0, recall unchanged.

| | iter3s + grounding | Iteration 4 |
|---|---|---|
| **Detection F1** | **0.919** | 0.909 |
| Precision | 0.895 | **1.000** |
| Recall | **0.944** | 0.833 |
| **Decision accuracy** | **100%** | **91.7%** |
| Cost per task | $0.0042 | $0.0047 |

Precision reached 1.000 — every remaining false positive gone, exactly as predicted. It
also rejected **two true blockers**, and for the first time in the project the tool told
the applicant to apply to jobs they are barred from. Decision accuracy had been 100% and
stable at spread 0.000 across every previous run.

**Why it over-rejected — the useful part.** Both wrongly rejected claims are *relational*
conditions, and my verifier prompt made them impossible to judge:

```
jd_15  compensation_floor
       quote: "The salary range for this position is $85,000 - $120,000 annually."
       Does that sentence state "the band falls below the candidate's minimum"?
       Not on its own. It states a band. Whether that band blocks depends on a
       number the verifier was never shown.

jd_18  security_clearance
       quote: "Many roles on our team are open to candidates without a clearance.
               This one requires an active Secret clearance before your start date."
       The condition says "at time of application"; the sentence says "before your
       start date". Judged in isolation, close enough to reject.
```

The prompt said *"Judge only the sentence. Do not consider what the rest of the posting
might say."* That instruction was written to stop the verifier re-deriving the claim it was
meant to check — and it worked, at the price of withholding the candidate profile, without
which a salary band is just a number.

**A verifier cannot check a relational condition from one side of the relation.** Half these
conditions are comparisons — band against floor, years against experience, city against
location — and for those, "does this sentence state the condition?" is not a well-formed
question.

**Decision — grounding kept, relevance verification revised rather than removed.** The
mechanism is sound: it removed every genuine false positive and reached perfect precision.
The prompt is wrong. Iteration 5 gives the verifier the one profile field the condition is
decided by (`taxonomy.profile_field`, already in the data) and asks the comparison directly:
*"the posting says X; the candidate's `comp_floor` is Y; does X disqualify them?"* — still
reject-only, still blind to the rest of the posting.

**Current best configuration: iteration 3s + grounding.** F1 0.919, recall 0.944, precision
0.895, evidence 100%, decision accuracy 100%, $0.0042 per task — cheaper than the baseline.


---

## Iteration 5 — a profile-aware verifier, and the removal of verification

**What and why.** Iteration 4's verifier rejected two real blockers because it was asked to
judge relational conditions from one side of the relation. Every blocker already declares
the profile field that decides it, so iteration 5 shows the verifier that one field and asks
the comparison directly. It stays blind to the rest of the posting.

**Pre-registered criterion:** *"If recall does not recover, the over-rejection was not about
missing data and the verifier should be removed rather than tuned again."*

**Evidence.**

| | iter3s + grounding | Iteration 4 | Iteration 5 |
|---|---|---|---|
| **Detection F1** | **0.919** | 0.909 | 0.914 |
| Recall | **0.944** | 0.833 | 0.889 |
| Precision | 0.895 | **1.000** | 0.941 |
| **Decision accuracy** | **100%** | 91.7% | 95.8% |
| Cost per task | **$0.0042** | $0.0047 | $0.0050 |

The missing data was part of the problem — `jd_15`'s salary blocker came back once the
verifier could see `comp_floor: 140000`. It was not all of it. Recall recovered to 0.889,
not 0.944, and decision accuracy stayed below the 100% the single pass had held in every
run since the baseline. **The criterion was met: removed.**

**The surviving wrong rejection is the most interesting result in the project**, because the
verifier was arguably right and my data was wrong.

```
Condition shown:  security_clearance — "An active government security clearance
                  is required at time of application."
Quote shown:      "This one requires an active Secret clearance before your start date."
Background:       clearance: none
Verifier:         REJECT
```

Read literally, that is defensible. A clearance required *before your start date* is not a
clearance required *at time of application* — someone without one could still be eligible.
The verifier spotted a mismatch between `data/taxonomy.yaml`'s description and its own
phrasings, which say "prior to their start date" in the footer variant and "before your
start date" in the scoped-negation variant. The `blocks_when` rule treats any clearance
requirement as disqualifying; the description I handed the verifier is narrower than the
rule it is meant to describe.

**This is a corpus defect, found by the system under test.** It is recorded rather than
quietly patched: fixing the description now would change the corpus after four variants had
been measured against it, and the honest report is that one of the 18 blockers is described
inconsistently — alongside `professional_licensure`'s vague footer phrasing, which has now
been missed by every variant in every run.

**What removing verification actually taught us.** A verifier is another model call, and it
inherits the failure modes of the thing it is verifying — while seeing *less* context. The
detector handled `jd_18`'s scoped negation correctly; the verifier, shown a narrower slice,
did not. Adding a checking stage does not add a different kind of judgement, it adds the
same judgement with less information.

The one filter kept is the one that cannot be wrong about meaning: **a sentence is either in
the posting or it is not.** That check is mechanical, free, deterministic, and it removed
every fabricated citation without ever touching a real one.

---

## Final configuration

One call per posting: taxonomy definitions naming the deciding profile field, a verbatim
quote required for every claim, and a mechanical grounding check that drops any quote not
present in the posting.

One call per posting. Three runs each for the baseline and the final system, per
`EVAL.md` §8; medians reported with the spread.

| Metric | Baseline (median of 3) | **Final (median of 3)** | Change |
|---|---|---|---|
| **Detection F1** | 0.789 | **0.944** | **+0.155** |
| Recall | 0.833 | 0.944 | +0.111 |
| Precision | 0.750 | 0.944 | +0.194 |
| Evidence-correct rate | 0% | **100%** | +100pp |
| Hallucinated quotes | n/a | 0% | — |
| Decision accuracy | 100% | 100% | — |
| Clean-posting false alarms | 0/8 | 0/8 | — |
| **Cost per task** | $0.0051 | **$0.0045** | **−12%** |

### Run-to-run variation

| | Run 1 | Run 2 | Run 3 | Median | Spread |
|---|---|---|---|---|---|
| Baseline F1 | 0.789 | 0.850 | 0.789 | 0.789 | 0.061 |
| **Final F1** | 0.919 | 0.971 | 0.944 | **0.944** | 0.053 |

**The distributions do not overlap.** The worst final run (0.919) scores above the best
baseline run (0.850). That is a stronger claim than comparing medians: the result does not
depend on which run of each was picked, so the +0.155 gain cannot be an artefact of a lucky
draw. It is also 2.5× the 0.061 noise floor `EVAL.md` §8 requires it to clear.

Recall was identical in all three final runs (0.944, spread 0.000), as were evidence
coverage, decision accuracy and cost. All the remaining variation is in precision (0.895 to
1.000) — one borderline false positive appearing or not.

**It costs less than the baseline.** Requiring evidence makes the model answer in JSON
rather than prose, and the shorter output more than pays for the longer prompt.

### Human time per task

Measured once by hand, per `EVAL.md` §7.

| Condition | Postings | Total | Per posting |
|---|---|---|---|
| Manual triage | `jd_01`–`jd_10` | 16 min 09 s | **96.9 s** |
| Reviewing the tool's output | `jd_11`–`jd_20` | 2 min 20 s | **14.0 s** |

**82.9 seconds saved per posting — an 85.6% reduction.** At twenty postings a week that is
32 minutes of eligibility checking reduced to under five.

The reviewer's note matters as much as the stopwatch: *no verdict prompted a check of the
underlying posting.* Time is only saved if the output is trusted enough to act on — a tool
that halves reading time but leaves you re-reading the posting anyway has saved nothing, and
that is the failure this measurement was designed to expose.

**Stated limitations.** n=1, self-timed, by someone already familiar with the corpus, and
the assisted pass followed the manual one so some speed is practice rather than tooling. The
direction is solid; the magnitude is indicative. A controlled version would use naive
reviewers, counterbalanced order, and unseen postings.

### Cost

All figures from `response.usage`, priced at `claude-sonnet-5`'s published rates
($2.00 / $10.00 per million tokens). Full detail in `results/cost-summary.json`.

| | Baseline | Final |
|---|---|---|
| Cost per task | $0.0051 | **$0.0045** |
| Input tokens (24 postings) | 20,657 | 37,913 |
| Output tokens (24 postings) | 8,018 | 3,186 |
| Calls per posting | 1 | 1 |

**The final system is cheaper despite an 83% larger prompt**, because requiring JSON with
quoted evidence cut output tokens by 60% — and output is priced 5× higher than input.
The definitions and the evidence requirement pay for themselves twice: once in accuracy,
once in tokens.

Cost by variant, per task, showing what the removed branches would have cost:

| Variant | Calls/posting | Cost/task | Kept |
|---|---|---|---|
| Baseline | 1 | $0.0051 | — |
| Iteration 1 | 1 | $0.0050 | yes |
| Iteration 2 (decomposition) | 4 | $0.0124 | **removed** |
| Iteration 3 (decomp + evidence) | 4 | $0.0104 | **removed** |
| Iteration 4 (verification) | 1 + 1/claim | $0.0047 | **removed** |
| Iteration 5 (profile-aware verification) | 1 + 1/claim | $0.0050 | **removed** |
| **Final** | 1 | **$0.0045** | **yes** |

Every branch that was removed also cost more than the one that survived.

**Whole project:** 12 full runs, 469 API calls, 533K input and 60K output tokens,
**$1.67** and 23 minutes of wall time — including all four variants that were removed.
Reproducing just the headline comparison (3 baseline + 3 final runs) costs **$0.67** and
takes about 9 minutes.

**What the saving is really worth.** Ninety seconds a posting is not a large number in
absolute terms. What makes it worth saving is that roughly two thirds of it was being spent
on postings the applicant was never eligible for — the value is not the minutes, it is that
the remaining minutes go to applications that can succeed.
