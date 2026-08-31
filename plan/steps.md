# Hard Blocker Detector — Execution Steps

Companion to `plan.md`. That file is *what and why*; this one is *do this, then this*.
Work top to bottom. Every step has a **Done when** — don't advance until it's true.

Time estimates in parentheses. Total ≈ 18h.

> **Status — 2026-08-31.** Phases 0–6 complete. Phase 7 complete except the video (7.5).
> Actual spend $2.02 of $20; actual elapsed far under the 18h estimate. Several steps were
> changed by what the measurements showed — those are annotated **→ actual** below rather
> than rewritten, because a plan quietly edited to match the outcome is not a record.

---

## Phase 0 — Setup (0.5h)

- [X] **0.1 — Initialize the repo.** The directory is not currently under version control. `git init`, and make the first commit before writing anything else — Reproducibility (15 pts) needs history, and the README must distinguish what pre-existed from what was built during the competition. This repo starts empty, so that claim is clean.
- [X] **0.2 — Python environment.** `.venv`, pinned. Dependencies: `anthropic`, `pyyaml`, `pytest`. Write `requirements.txt` with exact versions immediately — the repro guide needs them and reconstructing versions later is guesswork.
- [x] **0.3 — API key in `.env`, `.env` in `.gitignore`.** Ground rule #8: no credentials in the submission. Do this before the first API call, not after.
- [x] **0.4 — Directory skeleton** per `plan.md` §8. Empty `__init__.py` files, `.gitkeep` in `runs/` and `results/`.

**Done when:** `git log` shows one commit, `pip install -r requirements.txt` works from scratch, and no secret is tracked.

---

## Phase 1 — Freeze the specs (2h)

Nothing here calls a model. This phase exists so the evaluation can't drift to flatter the results.

- [x] **1.1 — `data/taxonomy.yaml`.** All 14 blocker types from `plan.md` §3. Per type:

```yaml
- id: work_authorization
  group: legal
  description: Role does not offer visa sponsorship
  blocks_when: candidate.work_auth == "requires_sponsorship"
  phrasings:
    explicit: "Must be authorized to work in the US without sponsorship."
    indirect: "We are unable to provide visa sponsorship for this position."
    footer: "This position is not eligible for immigration sponsorship."
  distractor: "Visa sponsorship may be available for exceptional candidates."
```

  The `distractor` field matters as much as the phrasings — it generates the near-miss cases that make the false-alarm metric real.

- [x] **1.2 — `data/profile/candidate.yaml`.** Synthetic but realistic: `work_auth`, `citizenship`, `location`, `willing_to_relocate`, `timezone`, `years_experience`, `degree`, `certifications`, `clearance`, `comp_floor`, `employment_types`, `max_travel_pct`.

- [X] **1.3 — `EVAL.md`.** Freeze the metrics before any agent exists: primary F1 (recall + false-alarm rate), decision accuracy, evidence accuracy, evidence-hallucination rate, human time, cost. State the target explicitly: *every hard blocker caught, ≤1 clean posting flagged, correct evidence span on every reported blocker.*

**Done when:** another person could read `EVAL.md` and score a run identically to you, with no judgment calls left open.

---

## Phase 2 — Injector and corpus (3h)

- [x] **2.1 — Write 12 clean base postings** (`src/injector/bases/`). Realistic structure: title, about-us, responsibilities, requirements, nice-to-haves, benefits, EEO footer. Vary length and tone. These must contain **zero** blockers — verify by hand, since every false alarm later is scored against them.

- [x] **2.2 — `src/injector/inject.py`.** One function per blocker type, taking `(posting, phrasing_style)` and returning `(modified_posting, char_span)`. Insertion points vary by style: `explicit` → requirements section; `indirect` → mid-body; `footer` → benefits/legal boilerplate.

- [x] **2.3 — Distractor injection.** Inserts `preferred`-flavored text that resembles a blocker but isn't. Every clean posting gets 1–2.

- [x] **2.4 — Contradiction builder.** The hard cases: title says "Remote", body says "3 days onsite in Austin". Also scoped negation — "sponsorship available for some roles, but not this one."

- [x] **2.5 — `src/injector/generate.py`.** Seeded. Emits the 24-posting corpus per `plan.md` §4 plus `labels.yaml`.

```bash
python -m src.injector.generate --seed 42 --out data/corpus
```

- [x] **2.6 — Verify determinism.** Generate twice into separate directories, diff them.

**Done when:** two runs at seed 42 are byte-identical, and you have spot-read 3 postings and agreed with their labels by eye.

---

## Phase 3 — Scoring harness (1.5h)

Built **before** the baseline, so both systems are scored by identical code.

- [x] **3.1 — Prediction schema.** Every system — baseline and agent alike — emits the same JSON: `verdict`, `blockers[]` with `type` + `evidence` (a quoted string), `caveats[]`.

- [x] **3.2 — `src/eval/match.py`.** The fiddly part. **`EVAL.md` §3 is authoritative** — implement it exactly. In short:
  1. Normalize whitespace on both sides; substring search is case-insensitive.
  2. **Detection matches on `type` only, one-to-one.** Walk predictions in order; each matches the first not-yet-matched gold blocker of the same type on that posting. Unmatched prediction → FP. Unmatched gold → FN.
  3. **Evidence is scored separately, over the TPs.** Locate the quote: not found → hallucinated; found → correct if its span overlaps the gold span.
  4. Hallucination rate is computed over *all* predictions, not just TPs, so fabricated quotes inside false positives are counted.

  Keep detection and evidence as separate metrics. Collapsing them hides which one an iteration improved — and iteration 3 is specifically expected to move evidence while leaving detection flat.

- [x] **3.3 — `src/eval/metrics.py`.** Per-posting TP/FP/FN → corpus-level recall, false-alarm rate, F1, decision accuracy, evidence accuracy, hallucination rate. Emits a markdown table for direct paste into the changelog.

- [x] **3.4 — Sanity-test the scorer.** Feed it three hand-written prediction files: a perfect one (expect F1 = 1.0), an empty one (expect recall 0, false alarms 0), and a flag-everything one (expect recall 1.0, false-alarm rate near 1.0). **A scorer you haven't tested will silently invalidate every number downstream.**

**Done when:** all three sanity predictions produce exactly the expected metrics.

> **→ actual.** F1 1.000 / 0.000 / 0.102. Fixtures committed to `tests/fixtures/` so a judge
> can rerun the check. This step also exposed that `EVAL.md` §4's zero-denominator
> conventions gave a *perfect* F1 on an empty run; `aggregate()` now refuses one.

---

## Phase 4 — Baseline (1h)

- [X] **4.1 — `src/baseline/run.py`.** One prompt: posting + profile → "Should I apply?" No tools, no taxonomy, no evidence requirement. A thin parse layer maps its freeform answer into the shared schema — do not improve the baseline's *reasoning* to make parsing easier; that would inflate it and make the comparison unfair.

- [x] **4.2 — Trajectory logging.** Write every run to `runs/<timestamp>/` — prompts, raw responses, token counts, cost, wall time. Build this now, in the baseline, so it's inherited by everything after and the trajectories deliverable costs nothing at the end.

- [x] **4.3 — Run and record.**

```bash
# → actual: producing predictions and scoring them are separate commands
python -m src.baseline.run --out results/baseline-run1
python -m src.eval.run --predictions results/baseline-run1/predictions.json \
    --out results/baseline-run1 --label "Baseline (run 1)"
```

- [X] **4.4 — Write the baseline changelog entry immediately**, with its numbers, into `CHANGELOG.md`.

**Done when:** `results/baseline/metrics.md` exists and the changelog's first row is filled in with real values.

> If the baseline scores well, don't quietly move on. Harden the corpus (more indirect and footer-displaced phrasings) and re-baseline — then report both numbers. A weak baseline that was never stress-tested is the easiest thing for a judge to attack.

> **→ actual.** The baseline scored **much** better than predicted: F1 0.789 median over three
> runs, with **100% of verdicts correct**. The corpus was *not* hardened — that note was
> written to guard against a weak baseline, and here the failures were specific and
> mechanistic (every false positive was one of two confusable pairs), so hardening would have
> been moving the goalposts. `plan.md`'s prediction that it would be agreeable and miss footer
> blockers was wrong, and is left in place as written.

---

## Phase 5 — Iterations (7h, ~1.5h each)

Same loop every time: **implement → run → record → decide.** Write the changelog entry before starting the next iteration; retroactive changelogs read as fiction.

- [x] **5.1 — Iteration 1: structured output + taxonomy in context.** Give the model the blocker taxonomy and require the JSON schema. *Hypothesis: some misses are vagueness — naming the categories gives it targets.*

  > **→ actual: definitions only, no structured output.** The baseline already had 0% parse
  > failures, so a JSON schema had nothing to fix and would only have confounded attribution.
  > **F1 0.789 → 0.914 (+0.125).** A later ablation (6.5) showed the descriptions alone did
  > all of it — the profile-field naming I claimed was load-bearing contributed nothing.

- [x] **5.2 — Iteration 2: per-category decomposition.** One independent check per taxonomy group (legal / logistics / credentials / terms), results merged. *Hypothesis: a single pass anchors on the first blocker and stops looking.* Watch the multi-blocker stress cases here specifically.

  > **→ actual: hypothesis confirmed, change removed.** Recall rose exactly as predicted
  > (0.889 → 0.944) and precision fell three times as far. **F1 0.914 → 0.850**, at 2.5× the
  > cost. Isolating a category removed the competition *between* categories that had been
  > suppressing weak claims. **Removed.**

- [x] **5.3 — Iteration 3: evidence spans + verification pass.** Every claim must quote the posting; a second pass verifies each quote exists and actually supports the claimed blocker, and can only **reject** claims, never add them. *Hypothesis: this is the big false-alarm cut.* Expect the largest single gain here.

  > **→ actual: split in two, and the hypothesis was wrong.** Evidence went here; verification
  > moved to 5.4. Requiring a quote took **evidence coverage 0% → 100%** and did *not* cut
  > false alarms — the model supplied a quote anyway, once citing back my own definition text.
  > An isolation run (`iter3s`) then showed decomposition was contributing nothing, so it was
  > removed. Not the largest gain; that was 5.1.

- [x] **5.4 — Iteration 4: contradiction resolution.** Explicit reconciliation across title / body / footer with a stated precedence rule. *Hypothesis: targets the 4 contradictory cases, which earlier iterations likely still miss.*

  > **→ actual: not needed, replaced by verification.** The contradiction bucket was already at
  > **4/4** by iteration 3s, so this step had no target. Built the reject-only verification
  > pass instead. It reached **precision 1.000** and rejected two real blockers, dropping
  > decision accuracy 100% → 91.7%. The free half — a mechanical check that the quote exists
  > in the posting — was kept and is in the final system.

- [x] **5.5 — The removal candidate: two-agent reviewer + challenger debate.** Run it honestly. Prediction: added cost and latency, no gain over 5.3's verification pass. If it loses, it earns a changelog entry on what it taught. If it wins, it stays — the brief wants a removed experiment, but a *fabricated* one is worse than none.

  > **→ actual: debate never run; a better removal experiment presented itself.** By this point
  > two variants had already been removed with data, so a third contrived one would have added
  > nothing. Instead: fixed iteration 4's verifier by giving it the profile field it was
  > missing. Recall recovered only partially (0.833 → 0.889) and decision accuracy stayed
  > below the single pass's 100%, so verification was **removed** on the criterion set before
  > running it. Its last wrong rejection was arguably *correct* — it caught an inconsistency
  > in `taxonomy.yaml` itself.

For each: `python -m src.eval.run --system agent --variant iterN --out results/iterN`

**Done when:** each iteration has a metrics file, a changelog entry citing it, and an explicit kept / revised / removed decision.

> **→ actual.** Seven variants run (`iter1`, `iter2`, `iter3`, `iter3s`, `iter4`, `iter5`,
> `iter1-nofield`), of which **three were removed** and one was an ablation. All remain
> runnable via `--variant`; none were deleted.

---

## Phase 6 — Final comparison (1h)

- [X] **6.1 — Assemble the final variant** from what actually won. Re-run on the full corpus.
- [X] **6.2 — Human time per task.** Stopwatch: triage 10 postings manually, then 10 by reviewing agent output. Report as n=1 self-timed — state that limitation plainly rather than dressing it up.
- [X] **6.3 — Cost per task** from the logged token counts.
- [x] **6.4 — Baseline vs. final table** in the `EVAL.md` format. → `results/COMPARISON.md`, generated from the metrics files rather than typed.
- [x] **6.5 — Identify the single largest contributor** across iterations. The brief asks for this explicitly.

  > **→ actual.** Iteration 1's definitions: **+0.130 of the +0.155 total**, 96% of the gain.
  > An ablation was run rather than asserting it, and it **overturned my stated mechanism** —
  > the profile-field naming contributed nothing; the one-line descriptions did everything.
  > The original claim is struck through in `CHANGELOG.md`, not deleted.

**Done when:** one table shows baseline → final on every frozen metric, and you can name the change that mattered most. ✅

> **Headline:** F1 0.789 → 0.944 (+0.155, 2.6× the 0.061 noise floor), evidence 0% → 100%,
> human time 96.9s → 14.0s per posting, cost $0.0049 → $0.0044. The baseline and final
> distributions **do not overlap** — the worst final run beats the best baseline run.

---

## Phase 7 — Deliverables (3h)

- [x] **7.1 — `README.md`.** The user and their bottleneck, why it's worth solving, how to run it, then the labeled **Improvement Changelog**. Close with the dominant failure mode and the hot take. State plainly that the repo began empty.
- [x] **7.2 — `REPRODUCE.md`.** Written for a clean machine: setup, exact commands for corpus / baseline / each variant / comparison, required data, expected output, versions, approximate runtime and cost. **Test it by wiping `.venv` and following your own instructions literally.**
- [x] **7.3 — Trajectories.** Curate representative runs from `runs/` — one baseline failure, one final success, one case where verification rejected a claim. Add a short index explaining what each shows.
- [x] **7.4 — Polish the verdict output.** This is the 20-point End-to-End Quality deliverable. It must read like something you'd paste into your own job-search notes — evidence quoted inline, scannable, not a JSON dump and not obviously LLM-generated prose.
- [ ] **7.5 — Video (≤5 min).** Problem → baseline confidently missing a footer blocker → one full real run → comparison table → changelog highlights → the removed experiment.

  > Script, run-sheet and a numbers table are in `video.md` (excluded from git via
  > `.git/info/exclude`). **The only outstanding deliverable.**

- [x] **7.6 — Coding-agent disclosure and development traces.** *Not in the original plan.*
  Added after reading the HackerEarth challenge page, which requires disclosing the coding
  agents used and submitting their trajectories — a **qualification gate** item, checked
  before rubric scoring. README now states that every line was written by Claude Opus 5 in
  Claude Code across 115 human turns and 288 tool calls. `runs/agent-traces/` holds the
  redacted session transcript and `human-checkpoints.md`. Submitted alongside
  `runs/curated/` because the deliverable is ambiguous between the agent used to build and
  the agent that was built.

**Done when:** a stranger could clone, follow `REPRODUCE.md`, and reach your headline number. ✅
*(Verified: extracted the tracked tree with `git archive` into an empty directory, built a
fresh venv, and ran every documented command.)*

---

## If you fall behind

Cut from the end of Phase 5, never from Phases 3, 4, or 7. Priority order when time is short:

1. Working baseline + harness + honest numbers
2. Two solid iterations with evidence
3. Complete deliverables
4. More iterations

Two iterations with a tested reproduction guide outscore five iterations with none — Reproducibility is 15 points and Measured Improvement is 15, while iteration *count* is worth nothing on its own.

---

## Running checklist

| Phase | Output | Est. | Status |
|---|---|---|---|
| 0 | Repo, env, secrets handled | 0.5h | ✅ |
| 1 | Taxonomy, profile, frozen `EVAL.md` | 2h | ✅ |
| 2 | Seeded 24-posting corpus + labels | 3h | ✅ |
| 3 | Tested scoring harness | 1.5h | ✅ |
| 4 | Baseline + first changelog row | 1h | ✅ |
| 5 | 4 iterations + 1 removal | 7h | ✅ 7 variants, 3 removed |
| 6 | Final comparison table | 1h | ✅ |
| 7 | README, REPRODUCE, trajectories, video | 3h | ⬜ video only |

### Submission checklist (HackerEarth requirements)

| Required | Status |
|---|---|
| Solution code + Improvement Changelog | ✅ `README.md`, `CHANGELOG.md` |
| Reproduction guide | ✅ `REPRODUCE.md`, tested from a clean clone |
| Baseline **and** advanced solution | ✅ 3 runs each, distributions do not overlap |
| Agent trajectories | ✅ `runs/curated/` + `runs/agent-traces/` |
| Coding-agent disclosure | ✅ `README.md` |
| Solution video ≤5 min | ⬜ **outstanding** — script in `video.md` |
| Register on HackerEarth | ⬜ **outstanding** — accepts the Participation Agreement |

**Deadline: 2026-08-31 18:00 UTC.**
