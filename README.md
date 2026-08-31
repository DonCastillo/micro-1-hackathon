# Hard Blocker Detector

**Reads a job posting against your profile and tells you whether a hard rule disqualifies
you before you spend an hour applying — with the sentence that proves it.**

Built for the micro1 Agentic Workflows Hackathon. This repository began empty; the initial
commit contains only the competition brief and a plan. Everything else was written during
the competition.

```
Detection F1     0.789 → 0.944    +0.155   (2.6× the measured noise floor)
Evidence            0% → 100%     every claim now cites the line that proves it
Human time      96.9s → 14.0s     per posting, measured with a stopwatch
Cost per task  $0.0049 → $0.0044  the better system is also the cheaper one
```

---

## The user and the bottleneck

An active software-engineering job applicant.

A tailored application costs 30–40 minutes: reading the posting, adjusting the résumé,
writing the cover note, filling the ATS form. A meaningful share of that goes to postings
the applicant was **never eligible for**, because a disqualifying rule was stated once,
indirectly, somewhere easy to skim past:

> *"We are unable to provide visa sponsorship for this position."* — in the benefits footer
>
> *"Candidates must reside within commuting distance of our Austin, TX office."* — in a
> posting whose header says **Remote**
>
> *"We are able to sponsor visas for a number of our engineering roles. This particular
> position is not eligible for sponsorship."* — the reassuring half first

The applicant finds out after investing the time, or never — the rejection is automated and
unexplained.

**Measured, not assumed:** triaging ten postings by hand took **16 minutes 9 seconds**, and
a third of them had a hard blocker. That is the bottleneck: not the applying, the *checking*
— and the checking is worth doing only because so much of the applying is wasted without it.

### Why solving it is valuable

The saving is not really the ninety seconds a posting. It is that the remaining minutes go
to applications that can actually succeed. Misattribution matters just as much: a tool that
says *"you're blocked on work authorization"* when the real bar is ITAR citizenship sends
someone hunting for a sponsor for a role no sponsor can unlock.

**Scope.** This decides whether the posting is worth *your* time. It does not evaluate you,
score your fit, or rank candidates — that is the employer's side of the problem, and it is
deliberately out of scope.

---

## How it works

One model call per posting.

```
posting + profile + 14 blocker definitions
        ↓
  model returns JSON: each blocker it found, with the exact sentence that states it
        ↓
  grounding check: any quote not present in the posting is dropped (mechanical, free)
        ↓
  SKIP if anything survives, APPLY if not
```

That is the whole system. Four more elaborate designs were built, measured, and removed —
per-group decomposition and two verification passes — each with its own changelog entry
explaining what it cost and what it taught. See [`CHANGELOG.md`](CHANGELOG.md).

### Using it

```bash
python -m src.check posting.txt              # one posting
python -m src.check inbox/*.md               # a batch, with a summary
```

```
 SKIP    Machine Learning Engineer
         Remote (United States)

  ✗  Onsite location
     "Candidates must reside within commuting distance of our Austin, TX office."
     You're in Los Angeles and not open to relocating.

  14 conditions checked · 1 blocker · 3.2s · $0.0049
```

Three things are on screen deliberately. **The posting's own sentence**, so the verdict is
checkable without reopening the posting. **The line from your profile it collides with**,
generated from your profile rather than by the model — it cannot hallucinate, and it
supplies the half of the comparison the quote does not. **What was checked and what it
cost**, so an `APPLY` is a statement rather than a shrug.

A batch ends with the thing you actually wanted:

```
  Summary
  ────────────────────────────────────────────────────────────
  APPLY  Data Engineer
  SKIP   Integrations Engineer                        years of experience
  SKIP   Application Security Engineer                citizenship required
  SKIP   Data Engineer                                citizenship required, employment type
  APPLY  Developer Experience Engineer

  2 of 5 worth applying to · 17s · $0.0239
```

---

## Running it

Full instructions, exact commands, versions, runtime and cost: [`REPRODUCE.md`](REPRODUCE.md).

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
cp .env.example .env                     # add your ANTHROPIC_API_KEY

.venv/bin/python -m src.injector.generate --seed 42 --out data/corpus   # free, deterministic
.venv/bin/python -m src.agent.run --variant final --out results/mine
.venv/bin/python -m src.eval.run --predictions results/mine/predictions.json
```

Reproducing the headline comparison — three baseline runs and three final runs — costs
about **$0.67** and takes **nine minutes**.

---

## How it is evaluated

The evaluation protocol was **frozen before the first line of the system was written**:
[`EVAL.md`](EVAL.md). Changing it afterwards requires a dated amendment in its §10, and
four such amendments are recorded there — every one of which made the result *less*
impressive.

- **24 synthetic postings**, generated from a seed. Ground truth comes from construction,
  not judgment: the injector plants each blocker and records the exact character span, so
  the answer key is a fact about an edit rather than an opinion about a document.
- **8 of the 24 are clean but carry near-misses** — *"8+ years of experience preferred"*
  against a candidate with 6. Flagging one is a false alarm. Without them, a system that
  flags everything scores perfect recall.
- **Primary metric is F1**, not recall, for that reason. A committed fixture
  (`tests/fixtures/sanity_flag_everything.json`) demonstrates it: flagging every blocker on
  every posting earns **recall 1.000 and F1 0.102**.
- **Three runs each** for the baseline and the final system. The model has no temperature
  control, so the baseline's own F1 varies by 0.061 between identical runs — and no gain
  smaller than that may be claimed.

Full results: [`results/COMPARISON.md`](results/COMPARISON.md).

---

## Improvement Changelog

Full entries with evidence and decisions: [`CHANGELOG.md`](CHANGELOG.md).

| Stage | What was tried and why | Evidence | Decision |
|---|---|---|---|
| **Baseline** | One direct prompt, no help | F1 0.789 (3 runs, spread 0.061) | Verdicts already perfect; the failure is *attribution* |
| **Iteration 1** | One-line definition per blocker — errors looked like a vocabulary problem | **F1 0.914 (+0.125)**, precision 0.750 → 0.941 | **Kept** |
| **Iteration 2** | Four per-group checks, merged — it found one blocker and stopped | F1 0.850 (−0.064), recall ↑, precision ↓↓ | **Removed** |
| **Iteration 3** | Verbatim quote required for every claim | F1 0.865, evidence **0% → 100%** | Evidence kept, decomposition still suspect |
| **Iteration 3s** | The same, decomposition removed — isolation test | F1 0.895, recall 0.944, **cheapest variant** | **Kept** — evidence was doing all the work |
| **+ grounding** | Drop any quote not found in the posting (mechanical) | F1 0.919, hallucination → 0%, **no API call** | **Kept** |
| **Iteration 4** | Model verifies each quote states its condition | Precision **1.000**, recall 0.944 → 0.833, decision accuracy 100% → 91.7% | **Removed** |
| **Iteration 5** | Same verifier, given the profile field it was missing | Partial recovery only; decision accuracy 95.8% | **Removed** |
| **Ablation** | Iteration 1's definitions *without* the profile field | F1 0.919 — identical | Corrected an earlier claim: the descriptions alone did it |
| **Final** | Definitions + evidence + grounding, one call | **F1 0.944**, evidence 100%, $0.0044/task | Shipped |

**Largest contributor: defining the labels.** +0.130 of the +0.155 gain came from ~200
words of description already sitting in `data/taxonomy.yaml` as documentation. No extra
calls, no orchestration. Every agent technique tried afterwards was removed.

---

## The dominant failure mode

**Right answer, wrong reason, no citation — the failure that looks like success.**

The baseline got **100% of apply/skip verdicts correct** in all three runs. On the surface,
a working tool. Underneath, it misattributed the cause on five of twenty-four postings, and
`jd_16` shows what that means:

```
posting has:  citizenship_required (ITAR)  +  professional_licensure
baseline said: work_authorization
verdict:       SKIP — correct
blockers found: 0 of 2
```

It reached the right conclusion through reasoning that was wrong twice, and cited nothing,
so no one could tell. Any metric watching only the verdict would have called it finished.

---

## Hot take

**Three things this project found, in the order they surprised me.**

**1. The cheapest possible change beat every agent technique.** Writing one sentence
explaining what each label means was worth 96% of the accuracy gain. Decomposition, a
verification pass, and a profile-aware verification pass were all built, measured, and
removed — and every one of them also cost more than the thing that survived. Before
reaching for orchestration, check whether the model simply does not know what your terms
mean.

**2. A model asked for evidence will produce evidence-shaped text.** Requiring a quote did
not stop unsupportable claims; it made the model supply a quote anyway. On one posting it
cited back *my own definition text* as though it were a line from the job ad. On two others
it quoted real sentences that had nothing to do with the claim — and those passed every
automated check while proving nothing. **Requiring a citation is not the same as requiring
the citation to support the claim.** The only filter that survived is the one that cannot
be wrong about meaning: a sentence is either in the posting or it is not.

**3. A verifier inherits the failure modes of what it verifies, while seeing less.** The
verification pass reached perfect precision by also rejecting real blockers, and never
recovered the decision accuracy the single pass already had. Its most instructive rejection
was *correct*: shown *"clearance required at time of application"* beside the posting's
*"requires clearance before your start date"*, it rejected the mismatch — and it was right,
because my taxonomy's description was narrower than the rule it described. **The system
under test found a defect in the benchmark.** That is logged in `EVAL.md` §10 rather than
quietly patched.

**And the lesson that ties them together:** the change that mattered most to the *user*
moved the primary metric by nothing. Requiring evidence was worth **zero F1** — and it is
why human review took 14 seconds a posting instead of 97, with no verdict sending the
reviewer back to check. `SKIP — relocation_required` is a claim you must verify yourself.
`SKIP — "Relocation to Seattle, WA is a condition of employment"` is one you can act on.

Pick your primary metric carefully, then watch for the moment it stops tracking the thing
you actually care about.

---

## Repository

| Path | What |
|---|---|
| `EVAL.md` | Evaluation protocol, frozen before the system existed; amendments in §10 |
| `CHANGELOG.md` | Full improvement changelog, one entry per experiment |
| `REPRODUCE.md` | Clean-environment setup, exact commands, versions, runtime, cost |
| `data/taxonomy.yaml` | The 14 blocker types, their phrasings and near-miss distractors |
| `data/corpus/` | The 24 generated postings and `labels.yaml`, the answer key |
| `src/injector/` | Corpus generation — seeded, deterministic, regenerable |
| `src/agent/variants.py` | Every variant, including the four that were removed |
| `src/eval/` | Scoring harness; `tests/fixtures/` holds its sanity checks |
| `results/` | Every run's predictions, metrics and per-posting breakdown |
| `runs/curated/` | Representative agent trajectories |

1,200+ tests. The ones worth knowing about: `tests/test_agent_variants.py` asserts that no
variant is ever shown the exact sentences planted in the corpus, and
`tests/test_eval_run.py` scores three deliberately broken systems to prove the harness can
tell good from bad.

## Known limitations

**One blocker type is never caught.** `professional_licensure` in its footer phrasing —
*"Licensure will be verified with the state board prior to an offer being extended"* — states
no requirement, only that one will be checked. Missed by every variant in every run. Flagged
as a suspected corpus defect during the step 2.6 audit, before any system was measured
against it, and reported as an open question rather than fixed.

**Roughly one claim in eighteen is mislabelled.** Precision is 0.944, not 1.000. In practice
this looks like the right posting being flagged under a neighbouring condition — during
manual testing one run reported `work_authorization` while quoting a sentence about
commuting distance. Three subsequent runs on the same posting were correct.

The output is designed so this is *visible* rather than silent: the quote sits beside the
label, so a mismatch is apparent to the reader. That is the mitigation, and it is a weaker
one than fixing the underlying error would be.

**The corpus is synthetic and the profile is one person.** These numbers describe 24
generated postings checked against one invented candidate. Real postings are longer, messier,
and more repetitive; a different profile changes which conditions are even reachable.
Nothing here has been measured on a real job board.

**Verification was removed, so nothing catches a plausible-but-wrong claim.** Two attempts
are documented in the changelog. Both reached perfect precision by also rejecting real
blockers, and neither recovered the decision accuracy the single pass already had.

## Coding agents used

Required disclosure.

**Every line of this repository — code, tests, corpus, documentation and analysis — was
written by Claude Opus 5 running in Claude Code**, directed turn by turn by the participant.
No part of it was hand-written.

| | |
|---|---|
| Agent | Claude Opus 5 via Claude Code |
| Human turns | 115 |
| Tool calls | 288 |
| Commits | 30, each carrying `Co-Authored-By: Claude Opus 5` |

Two sets of trajectories are submitted, because the deliverable is ambiguous between them:

- **`runs/agent-traces/`** — the *development* trajectory. The complete Claude Code session
  transcript, plus `human-checkpoints.md` listing all 115 instructions the participant gave.
  Redacted for credentials only; the agent's mistakes, failed tests and corrected claims are
  all present.
- **`runs/curated/`** — the *product* trajectories. Seven traces of the blocker detector
  itself running against job postings.

The system this project delivers is also agent-based: one Claude API call per posting,
described in [How it works](#how-it-works).

## Ground rules

Synthetic data throughout; no private information, no scraped postings. The tool is
advisory — it never submits an application or contacts an employer, and the applicant makes
the final call. Every number here is reproducible from the commands above.
