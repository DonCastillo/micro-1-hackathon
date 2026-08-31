"""Agent variants. Each one changes exactly one thing from the one before it.

Holding everything else constant is what lets the changelog attribute a gain to
a cause. A variant that changes the prompt *and* the output format *and* the
number of passes produces a number nobody can explain.

**Leakage rule, enforced by tests.** `data/taxonomy.yaml` holds the exact
sentences the injector plants in the corpus. A variant may show the model a
blocker's `id`, its `description`, and which profile field it is checked
against. It must never show `phrasings` or `distractors` — those are the test
paper, and a model given them would string-match its way to a high score that
means nothing.
"""

from __future__ import annotations

from typing import Any, Protocol

import yaml

from src.baseline.run import SYSTEM as BASELINE_SYSTEM
from src.baseline.run import extract_declared_blockers, parse_baseline_output
from src.schema import Claim, Prediction, parse_claims_json
from src.trajectory import Trajectory


class Variant(Protocol):
    name: str
    description: str

    def predict(
        self, posting: str, profile: dict[str, Any], taxonomy: dict[str, Any], traj: Trajectory
    ) -> Prediction: ...


def blocker_definitions(taxonomy: dict[str, Any]) -> str:
    """What each id means and which profile field decides it.

    Deliberately excludes phrasings and distractors (see the leakage rule).
    The profile field is the load-bearing part: it is what separates
    `citizenship_required` (checks `citizenship`) from `work_authorization`
    (checks `work_auth`), which the baseline conflated 9 times in 3 runs.
    """
    lines = []
    for blocker in taxonomy["blockers"]:
        lines.append(
            f"- {blocker['id']} ({blocker['group']}): {blocker['description']} "
            f"Decided by the profile field `{blocker['profile_field']}`."
        )
    return "\n".join(lines)


ITER1_PROMPT = """\
Here is my background:

{profile}

Here is a job posting:

{posting}

Should I apply? If anything in this posting disqualifies me, tell me what.

These are the disqualifying conditions, what each one means, and which part of
my background decides it:

{definitions}

A condition only disqualifies me if the posting makes it a firm requirement and
my background fails it. A preference is not a requirement.

End your answer with two lines exactly:

VERDICT: APPLY or SKIP
BLOCKERS: comma-separated ids from the list above, or NONE
"""


class Iteration1:
    """Taxonomy definitions instead of bare ids.

    Hypothesis, from the baseline failure analysis: every false positive was
    one of two confusable pairs — ITAR citizenship read as visa sponsorship,
    and "must reside within commuting distance" read as relocation. If that is
    a vocabulary problem, telling the model what each id means and which
    profile field decides it should raise precision and leave recall roughly
    flat. If precision does not move, the confusion is not about vocabulary
    and iteration 2 must target something else.
    """

    name = "iter1"
    description = "taxonomy definitions in context (output format unchanged)"

    def predict(
        self, posting: str, profile: dict[str, Any], taxonomy: dict[str, Any], traj: Trajectory
    ) -> Prediction:
        prompt = ITER1_PROMPT.format(
            profile=yaml.safe_dump(profile, sort_keys=False).strip(),
            posting=posting.strip(),
            definitions=blocker_definitions(taxonomy),
        )
        response = traj.call("ask", BASELINE_SYSTEM, prompt)

        ids = [b["id"] for b in taxonomy["blockers"]]
        try:
            return parse_baseline_output(response.text, ids)
        except Exception as exc:  # noqa: BLE001 - recorded, not swallowed
            traj.note("parse_failure", f"could not read a verdict: {exc}")
            return Prediction.unparseable(str(exc))


ITER2_GROUP_PROMPT = """\
Here is my background:

{profile}

Here is a job posting:

{posting}

Check this posting for {group} disqualifiers only. Ignore every other kind of
problem — other checks cover those.

The {group} conditions, and which part of my background decides each one:

{definitions}

A condition only disqualifies me if the posting makes it a firm requirement and
my background fails it. A preference is not a requirement.

End your answer with one line exactly:

BLOCKERS: comma-separated ids from the list above, or NONE
"""


class Iteration2:
    """One independent check per taxonomy group, merged.

    Hypothesis, from iteration 1's remaining errors: both misses were on
    multi-blocker postings where the model named one blocker and stopped
    looking. If a single pass anchors on the first thing it finds, asking four
    narrower questions should recover the second blocker.

    Predicted: recall rises on the `multi` bucket specifically; precision flat
    or slightly down, since four independent chances to claim something is four
    chances to claim something wrong. Cost roughly doubles.

    The verdict is computed rather than asked for — no single call sees the
    whole posting's verdict, and SKIP-iff-any-blocker is how the gold labels are
    defined anyway. Decision accuracy was already 100% for the baseline and
    iteration 1, so this cannot flatter the result.
    """

    name = "iter2"
    description = "per-group decomposition: four independent checks, merged"

    def predict(
        self, posting: str, profile: dict[str, Any], taxonomy: dict[str, Any], traj: Trajectory
    ) -> Prediction:
        profile_text = yaml.safe_dump(profile, sort_keys=False).strip()
        found: list[Any] = []
        seen: set[str] = set()

        for group in taxonomy["groups"]:
            members = [b for b in taxonomy["blockers"] if b["group"] == group]
            prompt = ITER2_GROUP_PROMPT.format(
                profile=profile_text,
                posting=posting.strip(),
                group=group,
                definitions=blocker_definitions({"blockers": members}),
            )
            response = traj.call(f"check_{group}", BASELINE_SYSTEM, prompt)

            claims = extract_declared_blockers(response.text, [b["id"] for b in members])
            for claim in claims:
                if claim.type not in seen:
                    seen.add(claim.type)
                    found.append(claim)

        traj.note(
            "merge",
            f"merged {len(taxonomy['groups'])} group checks -> "
            f"{sorted(seen) if seen else 'no blockers'}",
        )
        return Prediction(verdict="SKIP" if found else "APPLY", blockers=found)


ITER3_GROUP_PROMPT = """\
Here is my background:

{profile}

Here is a job posting:

{posting}

Check this posting for {group} disqualifiers only. Ignore every other kind of
problem — other checks cover those.

The {group} conditions, and which part of my background decides each one:

{definitions}

A condition only disqualifies me if the posting makes it a firm requirement and
my background fails it. A preference is not a requirement.

For every disqualifier you report, quote the sentence from the posting that
states it. Copy that sentence exactly as it appears — do not paraphrase,
shorten, or join two sentences together. If you cannot find a sentence that
states the condition, do not report it.

Reply with only this JSON object and nothing else:

{{"blockers": [{{"type": "<id from the list above>", "evidence": "<exact sentence from the posting>"}}]}}

Use an empty list if nothing in this group disqualifies me.
"""


class Iteration3:
    """Decomposition, plus every claim must quote the posting.

    Hypothesis, from iteration 2's regression: its four new false positives
    were all claims with nothing in the posting to support them — there is no
    sentence in jd_03 denying sponsorship, because the bar there is ITAR
    citizenship. Requiring a verbatim quote should make an unsupportable claim
    harder to make, because the model has to produce the sentence before it can
    report the finding.

    Predicted: precision recovers toward iteration 1's 0.941 while keeping
    iteration 2's recall; evidence-correct rate rises from 0% to something
    meaningful for the first time.

    The output format changes to JSON here, which is a second change bundled
    into one iteration. It is forced rather than chosen: a quoted sentence does
    not fit on a comma-separated line. The changelog says so rather than
    claiming a clean single-variable test.
    """

    name = "iter3"
    description = "decomposition + verbatim evidence required for every claim"

    def predict(
        self, posting: str, profile: dict[str, Any], taxonomy: dict[str, Any], traj: Trajectory
    ) -> Prediction:
        profile_text = yaml.safe_dump(profile, sort_keys=False).strip()
        found: list[Claim] = []
        seen: set[str] = set()

        for group in taxonomy["groups"]:
            members = [b for b in taxonomy["blockers"] if b["group"] == group]
            allowed = {b["id"] for b in members}
            prompt = ITER3_GROUP_PROMPT.format(
                profile=profile_text,
                posting=posting.strip(),
                group=group,
                definitions=blocker_definitions({"blockers": members}),
            )
            response = traj.call(f"check_{group}", BASELINE_SYSTEM, prompt)

            for claim in parse_claims_json(response.text):
                if claim.type in allowed and claim.type not in seen:
                    seen.add(claim.type)
                    found.append(claim)

        traj.note(
            "merge",
            f"merged {len(taxonomy['groups'])} group checks -> "
            f"{sorted(seen) if seen else 'no blockers'}",
        )
        return Prediction(verdict="SKIP" if found else "APPLY", blockers=found)


ITER3S_PROMPT = """\
Here is my background:

{profile}

Here is a job posting:

{posting}

Should I apply? Report every condition in this posting that disqualifies me.

These are the disqualifying conditions, what each one means, and which part of
my background decides it:

{definitions}

A condition only disqualifies me if the posting makes it a firm requirement and
my background fails it. A preference is not a requirement.

For every disqualifier you report, quote the sentence from the posting that
states it. Copy that sentence exactly as it appears — do not paraphrase,
shorten, or join two sentences together. If you cannot find a sentence that
states the condition, do not report it.

Reply with only this JSON object and nothing else:

{{"blockers": [{{"type": "<id from the list above>", "evidence": "<exact sentence from the posting>"}}]}}

Use an empty list if nothing here disqualifies me.
"""


class Iteration3Single:
    """The same evidence requirement, without decomposition.

    The removal test. Iteration 3 scored F1 0.865 against iteration 1's 0.914 —
    a 0.049 gap, below the 0.061 noise floor, so the two are indistinguishable
    on detection while iteration 3 costs twice as much. That leaves the
    question of whether decomposition is contributing anything at all, or
    whether the evidence requirement is doing all the work.

    One call, all fourteen conditions, quote required. If this matches
    iteration 3's evidence coverage at iteration 1's F1 and half the cost,
    decomposition is removed.
    """

    name = "iter3s"
    description = "single pass + verbatim evidence (decomposition removed)"

    def predict(
        self, posting: str, profile: dict[str, Any], taxonomy: dict[str, Any], traj: Trajectory
    ) -> Prediction:
        prompt = ITER3S_PROMPT.format(
            profile=yaml.safe_dump(profile, sort_keys=False).strip(),
            posting=posting.strip(),
            definitions=blocker_definitions(taxonomy),
        )
        response = traj.call("ask", BASELINE_SYSTEM, prompt)

        allowed = {b["id"] for b in taxonomy["blockers"]}
        found = [c for c in parse_claims_json(response.text) if c.type in allowed]
        return Prediction(verdict="SKIP" if found else "APPLY", blockers=found)


VARIANTS: dict[str, Variant] = {
    "iter1": Iteration1(),
    "iter2": Iteration2(),
    "iter3": Iteration3(),
    "iter3s": Iteration3Single(),
}
