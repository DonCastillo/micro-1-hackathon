# Base postings

Twelve clean job postings. Every posting in the corpus is derived from one of
these, so **anything present here appears in the derived postings too.**

## The invariant

A base contains **zero blockers and zero distractors** relative to
`data/profile/candidate.yaml`.

An accidental blocker here is worse than an ordinary bug. The injector would
add nothing, label the posting `APPLY`, and the true verdict would be `SKIP` —
so an agent that correctly spots the blocker gets marked **wrong**. Nothing
errors; the corpus generates, the eval runs, and one row of the score is
inverted.

## Authoring rule

Bases may mention taxonomy-adjacent facts **only where they clearly do not
block**:

- Years of experience at or below the candidate's (currently 5+ maximum)
- Location: `Remote (United States)` or `Los Angeles, CA` only

Everything else the taxonomy touches is **omitted entirely**, so the injector
has sole control over what a posting claims: sponsorship, citizenship,
clearance, licensure, relocation, travel, shift work, degrees, certifications,
employment type, and salary.

Ordinary technical nice-to-haves ("Familiarity with Terraform preferred") are
fine and add realism. Eligibility nice-to-haves ("Advanced degree a plus") are
distractors and belong to step 2.3.

## Required structure

The injector places text by section, so each base must contain:

| Section | Injection style it receives |
|---|---|
| Line 2 — location | contradiction cases (title says Remote, body says onsite) |
| `## Requirements` | `explicit` |
| body prose | `indirect` |
| `## Benefits` / `## Equal opportunity` | `footer` |

## Before adding or editing a base

Run `pytest tests/test_bases_are_clean.py`. It checks forbidden topics, years
figures above the candidate's experience, salary figures, the location line,
the required sections, and verbatim taxonomy text. It will not catch a novel
phrasing that blocks in a way the keyword list misses — read your own posting
against `data/taxonomy.yaml` as well.
