# Reproducing these results

Written for someone starting from a clean machine with nothing installed but Python.

**Total cost to reproduce the headline claim: ~$0.67. Total time: ~15 minutes**, most of it
waiting on API calls.

You can verify a substantial amount **without spending anything** — see
[Verify for free](#verify-for-free) below.

---

## 0. Prerequisites

| | |
|---|---|
| Python | 3.11 or newer (developed on **3.14.0**, macOS arm64) |
| An Anthropic API key | [console.anthropic.com](https://console.anthropic.com) — needs credit; a Claude subscription does **not** include API access |
| Approximate spend | $0.67 for the full comparison |

Pinned package versions are in `requirements.txt`; `requirements.lock.txt` holds the full
transitive tree as resolved on 2026-08-30 if you want a byte-identical environment.

---

## 1. Setup

```bash
git clone <this repository>
cd micro1

python3 -m venv .venv
.venv/bin/pip install -r requirements.txt      # anthropic 1.2.0, PyYAML 6.0.3, pytest 9.1.1

cp .env.example .env
```

Edit `.env` and set `ANTHROPIC_API_KEY`. Leave `MODEL_ID=claude-sonnet-5` and
`EFFORT=medium` unchanged — the comparison is only fair if the baseline and the final
system run under identical settings (`EVAL.md` §9).

Load it into your shell. **Every command below assumes you have done this:**

```bash
set -a; source .env; set +a
```

> **If you get `400 anthropic-workspace-id is required`:** your key is identity-linked
> (organisation-scoped) rather than tied to one workspace. Either set
> `ANTHROPIC_WORKSPACE_ID` in `.env`, or create a new key scoped to a specific workspace on
> the API Keys page — the latter is fewer clicks.

---

## 2. Verify for free

Nothing in this section calls the API or costs anything.

**Run the test suite** (~2 seconds, 1,217 tests):

```bash
.venv/bin/python -m pytest -q
```

**Regenerate the corpus and confirm it is byte-identical to the committed one:**

```bash
.venv/bin/python -m src.injector.generate --seed 42 --out /tmp/corpus-check
diff -r /tmp/corpus-check data/corpus     # only difference should be .gitkeep
```

Expected: `24 postings`, split `16 SKIP / 8 APPLY`. The corpus is deterministic from the
seed, so this is what a judge gets too.

**Check the scoring harness can tell good from bad** — three deliberately broken systems,
scored by the real harness:

```bash
.venv/bin/python -m src.eval.run --predictions tests/fixtures/sanity_perfect.json
.venv/bin/python -m src.eval.run --predictions tests/fixtures/sanity_silent.json
.venv/bin/python -m src.eval.run --predictions tests/fixtures/sanity_flag_everything.json
```

Expected:

| Fixture | F1 | Recall | What it proves |
|---|---|---|---|
| `sanity_perfect` | **1.000** | 1.000 | The answer key can score itself |
| `sanity_silent` | 0.000 | 0.000 | Finding nothing scores nothing (precision 1.000 — it claimed nothing wrongly) |
| `sanity_flag_everything` | **0.102** | **1.000** | **Perfect recall, terrible F1** — why the primary metric is F1 |

**Read the corpus against its answer key:**

```bash
.venv/bin/python -m src.injector.audit            # all 24, headers and injected spans
.venv/bin/python -m src.injector.audit --id jd_16 --full
```

---

## 3. Reproduce the headline comparison

Three baseline runs and three final runs, per `EVAL.md` §8 — the model has no temperature
control, so single runs cannot distinguish an improvement from variance.

```bash
for i in 1 2 3; do
  .venv/bin/python -m src.baseline.run --out results/repro-baseline-$i
  .venv/bin/python -m src.eval.run \
      --predictions results/repro-baseline-$i/predictions.json \
      --out results/repro-baseline-$i --label "Baseline (run $i)"
done

for i in 1 2 3; do
  .venv/bin/python -m src.agent.run --variant final --out results/repro-final-$i
  .venv/bin/python -m src.eval.run \
      --predictions results/repro-final-$i/predictions.json \
      --out results/repro-final-$i --label "Final (run $i)"
done

.venv/bin/python -m src.eval.run --compare results/repro-baseline-1 results/repro-final-1
```

**Cost: ~$0.67. Runtime: ~9 minutes.** Each run prints per-posting progress and a running
cost total.

### What you should see

Exact numbers will not match — the model is not deterministic, which is the whole reason
for three runs. What should hold:

| | Expected | Ours |
|---|---|---|
| Baseline F1 | 0.78–0.86 | 0.789 / 0.850 / 0.789 |
| **Final F1** | **0.91–0.98** | 0.919 / 0.971 / 0.944 |
| Baseline evidence-correct | 0% | 0% |
| **Final evidence-correct** | **100%** | 100% |
| Decision accuracy, both | 100% | 100% |
| Clean-posting false alarms | 0/8 | 0/8 |
| Parse failures | 0% | 0% |

**The claim to check is that the ranges do not overlap** — every final run should beat every
baseline run. That is a stronger statement than comparing medians, and it is what makes the
+0.155 gain robust to which runs you happen to draw.

If a final run lands below 0.91, please say so in your notes rather than re-rolling. Our
sample is three runs; a wider spread than we measured is a real finding about the result's
stability.

---

## 4. Reproduce any individual iteration

Every variant, including the four that were removed, is runnable:

```bash
.venv/bin/python -m src.agent.run --variant iter1  --out results/x   # definitions
.venv/bin/python -m src.agent.run --variant iter2  --out results/x   # decomposition (removed)
.venv/bin/python -m src.agent.run --variant iter3  --out results/x   # decomp + evidence (removed)
.venv/bin/python -m src.agent.run --variant iter3s --out results/x   # evidence, single pass
.venv/bin/python -m src.agent.run --variant iter4  --out results/x   # verification (removed)
.venv/bin/python -m src.agent.run --variant iter5  --out results/x   # profile-aware verify (removed)
.venv/bin/python -m src.agent.run --variant iter1-nofield --out results/x  # the ablation
.venv/bin/python -m src.agent.run --variant final  --out results/x
```

Each costs $0.10–$0.30 for 24 postings. Add `--dry-run` to print the prompt and spend
nothing, or `--limit 3` for a cheap smoke test.

> **`--limit` is for smoke tests, not for scoring.** A limited run leaves the other postings
> with no prediction, and the harness counts those as misses rather than dropping them from
> the denominator — deliberately, so a system that crashes on the hard postings cannot score
> well on the ones it survived. A `--limit 3` run therefore scores around F1 0.19 no matter
> how good it is. Use it to check that commands work and output parses, then run the full 24
> for any number you intend to quote.

---

## 5. Reproduce the human-time measurement

This one needs a person and a stopwatch, and it is the only number here that cannot be
regenerated by running code.

```bash
open results/human-time/manual.md      # jd_01-jd_10, no answers shown
open results/human-time/assisted.md    # jd_11-jd_20, the tool's output
```

Time each pass separately. Ours: **969 s manual, 140 s assisted** — 96.9 s vs 14.0 s per
posting. Note that our reviewer already knew the corpus; a first-time reader will be slower
on both, and the ratio is the part worth comparing.

---

## What the data is

- **All postings are synthetic.** No real job posting is stored in this repository, and the
  candidate profile is invented. Nothing here depends on private data.
- **The corpus is generated, not curated.** `src/injector/` plants each blocker into a clean
  base posting and records the exact character span, so the answer key is a fact about an
  edit rather than a judgment about a document.
- **Regenerating it is free** — no API calls — so you can inspect and re-derive the ground
  truth without spending anything.

## Versions and environment

```
Python              3.14.0 (macOS 15, arm64)
anthropic           1.2.0
PyYAML              6.0.3
pytest              9.1.1
model               claude-sonnet-5
effort              medium
corpus seed         42
corpus digest       541aee87b742624b
```

Check the digest matches:

```bash
.venv/bin/python -c "from src.trajectory import corpus_digest; from pathlib import Path; \
print(corpus_digest(Path('data/corpus')))"
```

Every run writes its own manifest (`runs/<timestamp>_<variant>/manifest.json`) recording the
model, effort, git commit, Python version and corpus digest, so a result can never be
misattributed to a corpus that has since changed.

## Cost and runtime summary

| What | Cost | Time |
|---|---|---|
| Test suite, corpus regeneration, sanity fixtures, audit | **$0.00** | ~1 min |
| One variant over 24 postings | $0.10–$0.30 | 1–5 min |
| **Headline comparison (3 baseline + 3 final)** | **$0.67** | **~9 min** |
| Everything we ran, including all removed variants | $1.67 | 23 min |

Per-run detail: `results/cost-summary.json`.
