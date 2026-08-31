# Improvement Changelog

How this solution evolved, one entry per meaningful experiment. Every number comes from
`src/eval/` scoring the same 24-posting corpus (`CORPUS_SEED=42`) under the protocol frozen
in [`EVAL.md`](EVAL.md) before any of it was measured.

Entries are written when the experiment runs, not reconstructed afterwards.

| Stage | What was tried and why | Evidence | Decision / learning |
|---|---|---|---|
| **Baseline** | One direct prompt, one pass, no help | **F1 0.789** (0.789–0.850 over 3 runs) | Verdicts already perfect; the failure is *attribution*, not detection |
| **Iteration 1** | Taxonomy definitions instead of bare ids — the failures looked like a vocabulary problem | **F1 0.914** (+0.125) · precision 0.750 → 0.941 | **Kept.** Confusable-pair errors eliminated; remaining misses are all on multi-blocker postings |

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
