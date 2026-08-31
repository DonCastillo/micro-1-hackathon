# Baseline vs Final

Same 24 postings (`CORPUS_SEED=42`), same model (`claude-sonnet-5`, `effort=medium`),
same scoring code. Three runs each; medians reported with spread.
Protocol frozen in [`EVAL.md`](../EVAL.md) before any of it was measured.

## Headline

| Metric | Baseline (median run) | Final (median run) | Change |
|---|---|---|---|
| Detection F1 (primary) | 0.789 | 0.944 | +0.155 |
| Recall | 0.833 | 0.944 | +0.111 |
| Precision | 0.750 | 0.944 | +0.194 |
| Clean-posting false alarms | 0.0% | 0.0% | +0.0% |
| Decision accuracy | 100.0% | 100.0% | +0.0% |
| Evidence correct | 0.0% | 100.0% | +100.0% |
| Hallucinated quotes | 0.0% | 0.0% | +0.0% |
| Parse failures | 0.0% | 0.0% | +0.0% |
| Cost per task | $0.0049 | $0.0045 | $-0.0004 |

## Run-to-run variation

| | Run 1 | Run 2 | Run 3 | Median | Spread |
|---|---|---|---|---|---|
| Baseline F1 | 0.789 | 0.850 | 0.789 | **0.789** | 0.061 |
| **Final F1** | 0.919 | 0.971 | 0.944 | **0.944** | 0.053 |

**The distributions do not overlap.** The worst final run (0.919) scores above the best baseline run (0.850), so the +0.155 gain does not depend on which runs were compared. `EVAL.md` §8 requires any claimed improvement to exceed the baseline's own spread of 0.061; this is 2.6× that.

Recall, evidence coverage, decision accuracy and cost were identical across all three
final runs. The only variation is precision (0.895–1.000), from a single
borderline false positive appearing or not.

## Human time per task

| Condition | Postings | Total | Per posting |
|---|---|---|---|
| Manual triage | `jd_01`–`jd_10` | 16 min 09 s | **96.9 s** |
| Reviewing the tool's output | `jd_11`–`jd_20` | 2 min 20 s | **14.0 s** |

**82.9 s saved per posting, an 85.6% reduction.** The reviewer reported that no verdict
prompted a check of the underlying posting — time is only saved if the output is trusted
enough to act on.

*Limitations:* n=1, self-timed, reviewer already familiar with the corpus, assisted pass
run second so some speed is practice. Direction solid, magnitude indicative.

## Cost

| | Baseline | Final |
|---|---|---|
| Cost per task | $0.0051 | **$0.0045** |
| Input tokens / 24 postings | 20,657 | 37,913 |
| Output tokens / 24 postings | 7,678 | 3,186 |

Cheaper despite a larger prompt: output is priced 5× input, and requiring JSON with
quoted evidence cut output tokens by 60%.

Whole project including the four removed variants: **$1.67**, 469 calls, 23.3 minutes.
Reproducing this comparison alone: **$0.67**, about 9.2 minutes.

## Where the remaining error is

| Bucket | Baseline recall | Final recall |
|---|---|---|
| contradiction | 3/4 | 4/4 |
| injected | 9/10 | 10/10 |
| multi | 3/4 | 3/4 |

| Phrasing style | Baseline recall | Final recall |
|---|---|---|
| explicit | 5/5 | 5/5 |
| footer | 3/4 | 3/4 |
| indirect | 4/5 | 5/5 |
| scoped_negation | 2/2 | 2/2 |
| title_body_conflict | 1/2 | 2/2 |

The single remaining miss is `professional_licensure` in its footer phrasing —
*"Licensure will be verified with the state board prior to an offer being extended"* —
which states no requirement, only that one will be checked. It was missed by every
variant in every run, and was flagged as a suspected corpus defect during the step 2.6
audit, before any system had been measured against it. It is reported as an open
question rather than counted as a system failure or quietly fixed.

