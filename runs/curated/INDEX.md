# Curated agent trajectories

Seven traces, chosen to show what each variant actually did rather than what it scored.
Every one is a verbatim copy of a real run — prompts, model output, token counts, timing,
and the events that shaped the next step. Nothing here is reconstructed.

Trajectory capture was built into the baseline before the first API call
(`src/trajectory.py`), and the recorder wraps `llm.call` rather than sitting beside it, so
a variant physically cannot make an unrecorded request.

Full traces for every posting in every run are under `runs/<timestamp>_<variant>/`, which is
gitignored because it is large and regenerable. These seven are committed.

---

## The story in three traces

**[01 — baseline on `jd_16`](01-baseline-jd_16-right-answer-wrong-reason.md)**
*The dominant failure mode.* The posting has two blockers: an ITAR citizenship bar and a
professional licensure requirement. The baseline reports `work_authorization` — neither of
them — and returns **SKIP**, which is the correct verdict.

Right answer, wrong reason, no citation. A metric watching only the verdict calls this a
success. In practice it sends the applicant looking for a visa sponsor for a role where no
sponsor can help, because the bar is citizenship.

**[02 — final system on `jd_16`](02-final-jd_16-with-evidence.md)**
The same posting. Finds the ITAR bar correctly and quotes the sentence that states it.

It still misses the licensure requirement — the footer phrasing *"Licensure will be verified
with the state board prior to an offer being extended"*, which states no requirement, only
that one will be checked. That was flagged as a suspected corpus defect during the step 2.6
audit, **before any system had been measured against it**, and it has been missed by every
variant in every run. It is reported as an open question rather than counted as a system
failure.

**[03 — final system on `jd_11`](03-final-jd_11-contradiction-caught.md)**
A deliberately hard case. The header says `Remote (United States)`; the body requires
residence within commuting distance of an Austin office. Caught, with the contradicting
sentence quoted — which is what makes the verdict checkable in about two seconds.

---

## The filters, and what they cost

**[04 — grounding rejects a fabrication](04-final-jd_18-grounding-rejects-a-fabrication.md)**
The model claimed a blocker and produced a quote to justify it. The quote is not in the
posting. A string search dropped the claim, with no API call and no judgment involved.

This is the one filter that survived, and the reason is visible here: it cannot be wrong
about *meaning*. A sentence is either present or it is not.

**[06 — verification rejects a real blocker](06-iter4-jd_15-verifier-rejects-a-real-blocker.md)**
Why model verification was removed. The verifier is shown the condition
*"the posted band falls below the candidate's minimum"* and the quote *"The salary range for
this position is $85,000 - $120,000 annually"*, and asked whether it disqualifies.

It said no — reasonably, since it was never shown that the candidate's floor is $140,000.
**A verifier cannot check a relational condition from one side of the relation.**

**[07 — the verifier was right and the data was wrong](07-iter5-jd_18-the-verifier-was-right.md)**
The most instructive trace here. Iteration 5 fixed the missing-profile problem, and this
rejection survived:

```
condition shown:  "...required at time of application"
quote shown:      "...requires an active Secret clearance before your start date"
verdict:          REJECT
```

Those are genuinely different requirements, so the rejection is defensible. The fault is in
`data/taxonomy.yaml`: its `security_clearance` description is narrower than the
`blocks_when` rule it describes. **The system under test found a defect in the benchmark.**

Logged in `EVAL.md` §10 rather than quietly patched — editing the corpus after four variants
had been measured against it would invalidate every earlier number.

---

## A removed branch, in full

**[05 — decomposition on `jd_04`](05-iter2-jd_04-decomposition-removed.md)**
Four calls instead of one, each shown a single taxonomy group:

```
check_legal        4 conditions  →  citizenship_required
check_logistics    5 conditions  →  NONE
check_credentials  3 conditions  →  NONE
check_terms        2 conditions  →  employment_type
                                    merge → SKIP, both blockers
```

This is the success case it was built for: the single pass found the ITAR bar and stopped;
asked separately, `check_terms` found the W2-contract bar too.

It was still removed. Narrowing each question also removed the competition *between*
categories that had been suppressing weak claims, so precision fell nearly three times as
far as recall rose — and the single-call variant reached the same recall for a quarter of
the cost.

---

## Reading a trace

Each file is: a one-line note on what it shows, its source path, then the run itself.

- **numbered sections** are model calls, with the exact system and user prompts sent and the
  raw text returned
- ***(event)*** sections are things that happened between calls — a rejection, a merge, a
  parse failure. Deliverable 4 asks for the feedback that shaped each next step, and a list
  of prompts alone does not explain why the second one differed from the first
- **Result** is the parsed prediction the scorer received
