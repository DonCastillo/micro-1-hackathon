# Hard Blocker Detector — Execution Steps

Companion to `plan.md`. That file is *what and why*; this one is *do this, then this*.
Work top to bottom. Every step has a **Done when** — don't advance until it's true.

Time estimates in parentheses. Total ≈ 18h.

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

---

## Phase 4 — Baseline (1h)

- [X] **4.1 — `src/baseline/run.py`.** One prompt: posting + profile → "Should I apply?" No tools, no taxonomy, no evidence requirement. A thin parse layer maps its freeform answer into the shared schema — do not improve the baseline's *reasoning* to make parsing easier; that would inflate it and make the comparison unfair.

- [x] **4.2 — Trajectory logging.** Write every run to `runs/<timestamp>/` — prompts, raw responses, token counts, cost, wall time. Build this now, in the baseline, so it's inherited by everything after and the trajectories deliverable costs nothing at the end.

- [x] **4.3 — Run and record.**

```bash
python -m src.eval.run --system baseline --corpus data/corpus --out results/baseline
```

- [X] **4.4 — Write the baseline changelog entry immediately**, with its numbers, into `CHANGELOG.md`.

**Done when:** `results/baseline/metrics.md` exists and the changelog's first row is filled in with real values.

> If the baseline scores well, don't quietly move on. Harden the corpus (more indirect and footer-displaced phrasings) and re-baseline — then report both numbers. A weak baseline that was never stress-tested is the easiest thing for a judge to attack.

---

## Phase 5 — Iterations (7h, ~1.5h each)

Same loop every time: **implement → run → record → decide.** Write the changelog entry before starting the next iteration; retroactive changelogs read as fiction.

- [X] **5.1 — Iteration 1: structured output + taxonomy in context.** Give the model the blocker taxonomy and require the JSON schema. *Hypothesis: some misses are vagueness — naming the categories gives it targets.*

- [x] **5.2 — Iteration 2: per-category decomposition.** One independent check per taxonomy group (legal / logistics / credentials / terms), results merged. *Hypothesis: a single pass anchors on the first blocker and stops looking.* Watch the multi-blocker stress cases here specifically.

- [X] **5.3 — Iteration 3: evidence spans + verification pass.** Every claim must quote the posting; a second pass verifies each quote exists and actually supports the claimed blocker, and can only **reject** claims, never add them. *Hypothesis: this is the big false-alarm cut.* Expect the largest single gain here.

- [x] **5.4 — Iteration 4: contradiction resolution.** Explicit reconciliation across title / body / footer with a stated precedence rule. *Hypothesis: targets the 4 contradictory cases, which earlier iterations likely still miss.*

- [x] **5.5 — The removal candidate: two-agent reviewer + challenger debate.** Run it honestly. Prediction: added cost and latency, no gain over 5.3's verification pass. If it loses, it earns a changelog entry on what it taught. If it wins, it stays — the brief wants a removed experiment, but a *fabricated* one is worse than none.

For each: `python -m src.eval.run --system agent --variant iterN --out results/iterN`

**Done when:** each iteration has a metrics file, a changelog entry citing it, and an explicit kept / revised / removed decision.

---

## Phase 6 — Final comparison (1h)

- [ ] **6.1 — Assemble the final variant** from what actually won. Re-run on the full corpus.
- [ ] **6.2 — Human time per task.** Stopwatch: triage 10 postings manually, then 10 by reviewing agent output. Report as n=1 self-timed — state that limitation plainly rather than dressing it up.
- [ ] **6.3 — Cost per task** from the logged token counts.
- [ ] **6.4 — Baseline vs. final table** in the `EVAL.md` format.
- [ ] **6.5 — Identify the single largest contributor** across iterations. The brief asks for this explicitly.

**Done when:** one table shows baseline → final on every frozen metric, and you can name the change that mattered most.

---

## Phase 7 — Deliverables (3h)

- [ ] **7.1 — `README.md`.** The user and their bottleneck, why it's worth solving, how to run it, then the labeled **Improvement Changelog**. Close with the dominant failure mode and the hot take. State plainly that the repo began empty.
- [ ] **7.2 — `REPRODUCE.md`.** Written for a clean machine: setup, exact commands for corpus / baseline / each variant / comparison, required data, expected output, versions, approximate runtime and cost. **Test it by wiping `.venv` and following your own instructions literally.**
- [ ] **7.3 — Trajectories.** Curate representative runs from `runs/` — one baseline failure, one final success, one case where verification rejected a claim. Add a short index explaining what each shows.
- [ ] **7.4 — Polish the verdict output.** This is the 20-point End-to-End Quality deliverable. It must read like something you'd paste into your own job-search notes — evidence quoted inline, scannable, not a JSON dump and not obviously LLM-generated prose.
- [ ] **7.5 — Video (≤5 min).** Problem → baseline confidently missing a footer blocker → one full real run → comparison table → changelog highlights → the removed experiment.

**Done when:** a stranger could clone, follow `REPRODUCE.md`, and reach your headline number.

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

| Phase | Output | Est. |
|---|---|---|
| 0 | Repo, env, secrets handled | 0.5h |
| 1 | Taxonomy, profile, frozen `EVAL.md` | 2h |
| 2 | Seeded 24-posting corpus + labels | 3h |
| 3 | Tested scoring harness | 1.5h |
| 4 | Baseline + first changelog row | 1h |
| 5 | 4 iterations + 1 removal | 7h |
| 6 | Final comparison table | 1h |
| 7 | README, REPRODUCE, trajectories, video | 3h |
