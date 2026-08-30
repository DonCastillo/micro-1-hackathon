# Hard Blocker Detector — Project Plan

**micro1 Agentic Workflows Hackathon**
Status: planning · Budget: one weekend (~16–20 working hours)

---

## 1. The problem

**User:** an active software-engineering job applicant. (Me — which is why the eval cases are real frustrations, not invented ones.)

**Bottleneck:** a tailored application costs 30–40 minutes — reading the posting, adjusting the résumé, writing the cover note, filling the ATS form. A meaningful share of that work is spent on postings the applicant was *never eligible for*, because a disqualifying requirement was stated once, indirectly, in a place that's easy to skim past:

- "This role is not eligible for visa sponsorship" — in the benefits footer
- "Candidates must reside within commuting distance of our Austin office" — while the title says Remote
- "US Persons only per ITAR"
- "Active TS/SCI required"

The applicant discovers the blocker after investing the time, or never — they just get auto-rejected and learn nothing. At 10–15 applications a week, even a 20% hard-blocker rate is several hours a week burned.

**Why solving it is valuable:** it converts wasted effort into either saved time or more applications sent to roles the applicant can actually win. The value is measurable in minutes, and the decision it supports (apply / skip) is binary and checkable.

**Scope boundary:** this tool decides *whether the posting is worth the applicant's time*. It does not evaluate the candidate, score their fit, or rank them — that is the employer-side problem from the brief's appendix, and it is explicitly out of scope.

---

## 2. What the system does

Input: a job posting (raw text) + a structured candidate profile.
Output: a verdict with cited evidence.

```
VERDICT: SKIP
BLOCKERS:
  - type: work_authorization
    severity: hard
    evidence: "We are unable to provide visa sponsorship for this position."
    location: benefits section, line 47
CAVEATS:
  - type: years_of_experience
    severity: soft
    evidence: "8+ years preferred"   # preferred, not required — not a blocker
```

Three possible verdicts: **APPLY**, **APPLY_WITH_CAVEAT**, **SKIP**.

The human always makes the final call. The tool never auto-submits, auto-rejects, or contacts an employer.

---

## 3. Blocker taxonomy

The ruleset the agent checks against. Grouped, because the grouping drives the per-category decomposition in Iteration 2.

| Group | Blocker types |
|---|---|
| **Legal / eligibility** | work authorization & sponsorship, citizenship (ITAR/US Persons), security clearance, professional licensure |
| **Logistics** | onsite/hybrid location, relocation requirement, time-zone overlap, travel percentage, shift/on-call |
| **Credentials** | mandatory degree, mandatory certification, hard years-of-experience floor |
| **Terms** | employment type (W2 / C2C / contract-only), compensation floor below candidate minimum |

**The hard part — and the reason this needs an agent:**

1. **Indirect phrasing.** "US Persons only" never uses the word *citizenship*.
2. **Displacement.** The blocker often sits in boilerplate far from the requirements section.
3. **Contradiction.** Title says Remote; paragraph nine says three days onsite. Which governs?
4. **Hard vs. soft.** "8+ years required" blocks. "8+ years preferred" does not. Conflating them is the dominant source of false alarms.
5. **Scoped negation.** "Sponsorship is available for some roles, but not this one."

---

## 4. Data strategy

Fully **synthetic corpus**, committed to the repo. This satisfies the ground rules (public/synthetic data, no private information), keeps the benchmark reproducible from a seed, and sidesteps the copyright question of committing scraped postings.

Real postings appear only in the video demo, live — never in the repo.

### Corpus: 24 postings

| Bucket | Count | Purpose |
|---|---|---|
| Injected — single blocker | 10 | Core recall. Varied types + phrasing (explicit / indirect / footer-displaced) |
| Clean with near-miss distractors | 8 | **False-alarm measurement.** Contains "preferred" qualifications engineered to look blocking |
| Contradictory | 4 | The hard cases: title/body conflicts, scoped negation |
| Multi-blocker stress | 2 | Does it find blocker #2 after finding #1? |

Exceeds the brief's 10-case minimum with room for the required challenging case.

### The injector

`src/injector/` takes a clean base posting and inserts a blocker with a known type, phrasing style, and character span. Because insertion is programmatic, **ground truth is exact and free** — no labeling pass, and a judge can regenerate the entire corpus from a fixed seed.

Label format per posting:

```yaml
posting_id: jd_014
expected_verdict: SKIP
blockers:
  - type: work_authorization
    evidence_span: [1893, 1954]
    phrasing: indirect
distractors:
  - type: years_of_experience   # "preferred" — must NOT be flagged
```

### Candidate profile

One structured YAML: work auth status, citizenship, location, relocation willingness, time zone, years of experience, degree, certifications, clearance status, comp floor, employment-type preferences, travel tolerance. Synthetic but realistic.

---

## 5. Baseline

A single direct prompt — the reasonable basic approach a person would actually try:

> Here is a job posting and my background. Should I apply?

No tools, no structure, no taxonomy, no evidence requirement. Same model, same postings, same candidate profile as the final solution.

**Predicted failure mode** (to be confirmed, not assumed): one-shot prompts are agreeable and single-pass. They return an encouraging "you look like a strong fit!" while missing a blocker buried in the footer, and they conflate *preferred* with *required* in the other direction. If the baseline turns out to be strong, that is a finding worth reporting honestly — and a signal to make the corpus harder.

---

## 6. Evaluation

Defined **before** any agent is built.

### Primary metric

**Blocker detection F1** — recall paired with false-alarm rate.

Recall alone is gameable: an agent that flags everything scores 100% and is worthless to the user, because it sends them back to reading every posting by hand. The pairing is what makes the metric honest, and the near-miss distractor bucket is what makes false alarms measurable.

### Secondary metrics

| Metric | How measured |
|---|---|
| **Decision accuracy** | Correct APPLY / APPLY_WITH_CAVEAT / SKIP verdict |
| **Evidence accuracy** | Does the cited span actually contain the blocker? (Serves ground rule #9 — every claim tied to evidence) |
| **Human time per task** | Timed manual triage of N postings vs. reviewing agent output |
| **Cost per task** | API cost per posting, logged per run |

### What a good final result looks like

Stated up front so it can't drift: **catches every hard blocker in the corpus, flags no more than one clean posting, and cites a correct evidence span for every blocker it reports.** Anything less means the applicant either still wastes time or stops trusting the tool.

### Determinism

Temperature 0, pinned model ID, fixed corpus seed, versions and runtime recorded per run.

---

## 7. Agent design & planned iterations

This doubles as the **Improvement Changelog** roadmap. Each entry is a hypothesis with a predicted mechanism — the actual results get filled in as they land, including the ones that fail.

| Stage | Change | Hypothesis |
|---|---|---|
| **Baseline** | One prompt, freeform verdict | Establishes the starting point |
| **Iter 1** | Structured output + explicit blocker taxonomy in context | Misses are partly vagueness; naming the categories gives it targets |
| **Iter 2** | Decompose: one independent check per category group | Single-pass anchors on the first blocker and stops looking |
| **Iter 3** | Require an evidence span per claim + verification pass rejecting unsupported claims | Forces grounding; should cut false alarms sharply |
| **Iter 4** | Explicit contradiction resolution across title / body / footer | Targets the hard cases specifically |
| **Final** | Combine what worked | Identify the single largest contributor |

**One experiment planned as a likely removal:** a two-agent "reviewer + challenger" debate pass. Plausible on paper, and I expect it to add latency and cost without beating the Iteration 3 verification pass. If that's what happens, it gets its own changelog entry explaining what it taught. If it *wins*, it stays — the point is to run it honestly, not to script the outcome.

**Trajectory capture is built in from the first commit.** Every run writes its full trace — instructions, tool calls, responses, retries — to `runs/<timestamp>/`. This makes the required trajectories deliverable a byproduct rather than a Sunday-night reconstruction.

---

## 8. Repository layout

```
plan/plan.md              # this file
README.md                 # user, bottleneck, value + Improvement Changelog
REPRODUCE.md              # clean-environment guide
data/
  profile/                # candidate profile (synthetic)
  corpus/                 # generated postings + labels
src/
  injector/               # corpus generation, seeded
  baseline/               # single-prompt baseline
  agent/                  # the solution
  eval/                   # scoring harness, metric computation
runs/                     # auto-written trajectories
results/                  # per-iteration metric tables
```

---

## 9. Weekend timeline

| Block | Hours | Output |
|---|---|---|
| Taxonomy + candidate profile + eval spec | 2 | Metrics frozen before any agent exists |
| Injector + 24-posting corpus + labels | 3 | Ground truth, regenerable from seed |
| Scoring harness | 1.5 | Reusable across every iteration |
| Baseline + first measurement | 1 | The number everything else is compared to |
| Iterations 1–4 | 7 | Four changelog entries with evidence |
| Final comparison + README + changelog | 2 | Measured Improvement deliverable |
| REPRODUCE.md | 1 | Reproducibility deliverable |
| Video (5 min) | 1.5 | Problem → baseline failure → run → comparison |

**Order matters:** the scoring harness comes *before* the baseline, and the baseline before any agent work. If time runs short, iterations get cut from the end — the baseline, the eval, and the deliverables never do. A project with two solid iterations and complete deliverables outscores one with five iterations and no reproduction guide.

---

## 10. Deliverables → rubric mapping

| Deliverable | Covers | Pts |
|---|---|---|
| Solution code + Improvement Changelog | Engineering, Measured Improvement | 45 |
| REPRODUCE.md, seeded corpus, pinned versions | Reproducibility | 15 |
| README: user, bottleneck, value | Problem & User Value | 15 |
| Polished verdict output a real applicant would use | End-to-End Quality | 20 |
| Hot take on the dominant failure mode | Insights | 5 |

**End-to-End Quality (20 pts) is where this is won or lost.** The verdict output has to look like something a person would actually paste into their job-search notes — clean, scannable, with the evidence quoted inline. Not a JSON dump, and not obviously LLM-generated prose.

---

## 11. Ground rules compliance

- **Synthetic data throughout** — no private information, no scraped postings committed
- **No consequential actions** — advisory only; never submits, never contacts an employer
- **Human decides** — the applicant makes the final apply/skip call
- **Every claim tied to evidence** — the evidence-span requirement is enforced by the agent design and scored by the eval
- **Pre-existing vs. new** — the repo starts empty; everything here is built during the competition, and the README will say so

---

## 12. Risks

| Risk | Mitigation |
|---|---|
| Baseline performs better than expected, shrinking the improvement story | Harden the corpus with more indirect/displaced phrasings; report the honest number either way |
| Synthetic postings are unrealistically easy | Base them on the structure and boilerplate of real postings; include the footer-displacement pattern that causes real misses |
| Topic reads as adjacent to the brief's hiring example | Keep the framing rigorously applicant-side; never score the candidate |
| Deliverables squeezed at the end | Trajectory logging built in from commit one; changelog written per iteration, not retroactively |

---

## 13. Open decisions

- Model: default to `claude-sonnet-5` for eval volume, temperature 0, pinned. Spot-check the final configuration on `claude-opus-5`.
- Whether the candidate profile becomes a tool the agent queries, or stays in context — worth testing as its own iteration if time allows.
- How many real postings to demo live in the video (3–5 feels right).

---

## 14. The hot take (to be written)

Reserved. The expected shape, based on the predicted failure mode: *agreeableness is the dominant failure mode in advisory agents — a single-pass model asked "should I?" is structurally biased toward yes, and the fix is not a better prompt but a separate verification step that can only reject.* To be confirmed or overturned by what the runs actually show.
